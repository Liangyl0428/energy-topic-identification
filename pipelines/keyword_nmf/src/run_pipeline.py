#!/usr/bin/env python3
"""Fit, evaluate, select, and deploy an OpenAlex-keyword TF-IDF + NMF model."""

from __future__ import annotations

import argparse
import json
import time
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.decomposition import MiniBatchNMF
from sklearn.exceptions import ConvergenceWarning

from components import (
    candidate_metrics,
    component_stability,
    embedding_centroids,
    hard_assign,
    nearest_centroid_assign,
)


SOURCE_ROOT = Path(__file__).resolve().parents[4]
REPOSITORY = Path(__file__).resolve().parents[3]
KEYWORD_ROOT = SOURCE_ROOT / "aaaa/openalex_keywords_nmf"
PAPER_EMBEDDING_ROOT = SOURCE_ROOT / "aaaa/bge_m3/models"
PAPER_DATA_ROOT = SOURCE_ROOT / "aaaa/data"
TRANSFER_ROOT = SOURCE_ROOT / "bbbb"
DEFAULT_OUTPUT = REPOSITORY / "pipelines/keyword_nmf/results"
SPLITS = ("train", "validation", "replay")
METADATA_FILES = {
    "train": "development_train.parquet",
    "validation": "validation.parquet",
    "replay": "replay_evolution.parquet",
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )


def json_ready(value: object) -> object:
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if not np.isfinite(value) else float(value)
    return value


class DataBundle:
    def __init__(self) -> None:
        self.x = {
            split: sparse.load_npz(KEYWORD_ROOT / f"models/{split}_scored.npz")
            for split in SPLITS
        }
        self.embeddings = {
            split: np.load(
                PAPER_EMBEDDING_ROOT / f"bge_{split}.npy", mmap_mode="r"
            )
            for split in SPLITS
        }
        self.metadata = {
            split: pd.read_parquet(PAPER_DATA_ROOT / METADATA_FILES[split])
            for split in SPLITS
        }
        self.vocabulary = pd.read_csv(KEYWORD_ROOT / "vocabulary.csv")
        for split in SPLITS:
            expected = self.x[split].shape[0]
            if len(self.embeddings[split]) != expected or len(self.metadata[split]) != expected:
                raise ValueError(f"Misaligned inputs for {split}")


def fit_model(
    x_train: sparse.csr_matrix,
    k: int,
    seed: int,
    max_iter: int,
    batch_size: int,
    keep: np.ndarray | None = None,
) -> tuple[MiniBatchNMF, np.ndarray, list[str], float]:
    if keep is None:
        keep = x_train.getnnz(axis=1) > 0
    started = time.time()
    model = MiniBatchNMF(
        n_components=k,
        init="nndsvdar",
        random_state=seed,
        batch_size=batch_size,
        max_iter=max_iter,
        tol=1e-4,
        max_no_improvement=15,
        fresh_restarts=False,
        fresh_restarts_max_iter=5,
        beta_loss="frobenius",
        alpha_W=0.0,
        alpha_H="same",
        l1_ratio=0.0,
        transform_max_iter=200,
    )
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        fitted = model.fit_transform(x_train[keep]).astype(np.float32)
    messages = [str(item.message) for item in caught]
    weights = np.zeros((x_train.shape[0], k), dtype=np.float32)
    weights[keep] = fitted
    return model, weights, messages, time.time() - started


def transform(model: MiniBatchNMF, matrix: sparse.csr_matrix) -> np.ndarray:
    has_keywords = matrix.getnnz(axis=1) > 0
    weights = np.zeros((matrix.shape[0], model.n_components), dtype=np.float32)
    if has_keywords.any():
        weights[has_keywords] = model.transform(matrix[has_keywords]).astype(np.float32)
    return weights


def topic_keywords(
    components: np.ndarray, vocabulary: pd.DataFrame, top_n: int = 15
) -> pd.DataFrame:
    order = np.argsort(components, axis=1)[:, -top_n:][:, ::-1]
    records = []
    for topic_id, columns in enumerate(order):
        records.append(
            {
                "topic_id": topic_id,
                "top_keywords": " | ".join(vocabulary.display_name.iloc[columns]),
                "top_keyword_ids": " | ".join(vocabulary.keyword_id.iloc[columns]),
                "top_keyword_weights": " | ".join(
                    f"{components[topic_id, column]:.6g}" for column in columns
                ),
            }
        )
    return pd.DataFrame(records)


def run_candidate(
    data: DataBundle,
    output: Path,
    k: int,
    seed: int,
    max_iter: int,
    batch_size: int,
    overwrite: bool = False,
) -> dict[str, object]:
    candidate_dir = output / "candidates" / f"k{k}"
    metrics_path = candidate_dir / "metrics.json"
    if metrics_path.exists() and not overwrite:
        return json.loads(metrics_path.read_text(encoding="utf-8"))
    candidate_dir.mkdir(parents=True, exist_ok=True)
    print(f"START candidate k={k}", flush=True)
    model, train_weights, messages, seconds = fit_model(
        data.x["train"], k, seed, max_iter, batch_size
    )
    train_labels = hard_assign(train_weights)
    validation_weights = transform(model, data.x["validation"])
    validation_labels = hard_assign(validation_weights)
    centroids, counts = embedding_centroids(
        data.embeddings["train"], train_labels, k
    )
    train_norm = float(
        np.sqrt(data.x["train"].multiply(data.x["train"]).sum())
    )
    values = candidate_metrics(
        requested_k=k,
        train_labels=train_labels,
        validation_labels=validation_labels,
        train_centroids=centroids,
        train_counts=counts,
        validation_embeddings=data.embeddings["validation"],
        validation_has_keywords=data.x["validation"].getnnz(axis=1) > 0,
        reconstruction_error=model.reconstruction_err_,
        relative_reconstruction_error=model.reconstruction_err_ / train_norm,
    )
    values.update(
        {
            "algorithm": "score-weighted OpenAlex keyword TF-IDF + MiniBatchNMF",
            "seed": seed,
            "max_iter": max_iter,
            "n_iter": int(model.n_iter_),
            "batch_size": batch_size,
            "fit_seconds": seconds,
            "convergence_warnings": messages,
        }
    )
    joblib.dump(model, candidate_dir / "nmf.joblib", compress=1)
    np.save(candidate_dir / "components.npy", model.components_.astype(np.float32))
    np.save(candidate_dir / "train_centroids.npy", centroids)
    np.save(candidate_dir / "train_labels.npy", train_labels)
    train_top1 = train_weights.max(axis=1)
    train_top2 = np.partition(train_weights, -2, axis=1)[:, -2]
    np.save(
        candidate_dir / "train_assignment_strength.npy",
        np.column_stack([train_top1, train_top1 - train_top2]).astype(np.float32),
    )
    np.save(candidate_dir / "validation_labels.npy", validation_labels)
    topic_keywords(model.components_, data.vocabulary).assign(
        train_documents=counts
    ).to_csv(candidate_dir / "topics.csv", index=False)
    ready = json_ready(values)
    write_json(metrics_path, ready)
    print(
        f"DONE candidate k={k} active={values['active_topics']} "
        f"sil={values['sampled_cosine_silhouette']:.4f} "
        f"db={values['davies_bouldin']:.4f} seconds={seconds:.1f}",
        flush=True,
    )
    return ready


def select_candidate(metrics: pd.DataFrame) -> tuple[int, pd.DataFrame]:
    """Rank the preferred 450--550 window; 400/600 are boundary diagnostics."""
    scored = metrics.copy()
    admissible = scored.requested_k.between(450, 550)
    if not admissible.any():
        raise ValueError(
            "Candidate selection needs at least one K in the eligible 450--550 window"
        )
    directions = {
        "sampled_cosine_silhouette": False,
        "simplified_silhouette_mean": False,
        "davies_bouldin": True,
        "nearest_center_cosine_mean": True,
        "empty_topic_fraction": True,
        "keyword_embedding_ari": False,
    }
    rank_columns = []
    for column, ascending in directions.items():
        rank_column = f"rank_{column}"
        scored.loc[admissible, rank_column] = scored.loc[admissible, column].rank(
            method="average", ascending=ascending
        )
        rank_columns.append(rank_column)
    scored.loc[admissible, "mean_metric_rank"] = scored.loc[
        admissible, rank_columns
    ].mean(axis=1)
    scored.loc[admissible, "selection_score"] = scored.loc[
        admissible, "mean_metric_rank"
    ] + 0.15 * (scored.loc[admissible, "requested_k"] - 500).abs() / 50
    best_score = float(scored.loc[admissible, "selection_score"].min())
    practically_tied = admissible & (
        scored.selection_score <= best_score + 0.05
    )
    selected = int(
        scored.loc[practically_tied]
        .assign(distance_to_500=lambda frame: (frame.requested_k - 500).abs())
        .sort_values(["distance_to_500", "selection_score", "requested_k"])
        .iloc[0]
        .requested_k
    )
    scored["within_practical_tie"] = practically_tied
    scored["selection_eligible"] = admissible
    scored["selected"] = scored.requested_k == selected
    return selected, scored


def run_grid(args: argparse.Namespace, data: DataBundle) -> int:
    args.output.mkdir(parents=True, exist_ok=True)
    rows = [
        run_candidate(
            data,
            args.output,
            k,
            args.seed,
            args.max_iter,
            args.batch_size,
            args.overwrite,
        )
        for k in args.k
    ]
    metrics = pd.DataFrame(rows).sort_values("requested_k")
    if not metrics.requested_k.between(450, 550).any():
        metrics.to_csv(args.output / "candidate_metrics_partial.csv", index=False)
        print("GRID PARTIAL: no candidate in the 450--550 selection window", flush=True)
        return -1
    selected, ranked = select_candidate(metrics)
    ranked.to_csv(args.output / "candidate_metrics.csv", index=False)
    selected_row = ranked.loc[ranked.selected].iloc[0].to_dict()
    write_json(
        args.output / "selection.json",
        json_ready(
            {
                "selected_k": selected,
                "eligible_window": [450, 550],
                "boundary_diagnostics": [400, 600],
                "method": "mean rank of six validation/structure metrics plus a small distance-to-500 penalty; candidates within 0.05 score are treated as practically tied and the closest to 500 is selected",
                "selected_metrics": selected_row,
            }
        ),
    )
    print(f"SELECTED k={selected}", flush=True)
    return selected


def assign_all_papers(
    data: DataBundle,
    model: MiniBatchNMF,
    fitted_train_labels: np.ndarray,
    fitted_train_strength: np.ndarray,
) -> tuple[
    pd.DataFrame, np.ndarray, np.ndarray, dict[str, np.ndarray], np.ndarray
]:
    weights_by_split = {
        split: transform(model, data.x[split])
        for split in ("validation", "replay")
    }
    raw_train_labels = np.asarray(fitted_train_labels, dtype=np.int32)
    train_counts = np.bincount(
        raw_train_labels[raw_train_labels >= 0], minlength=model.n_components
    )
    active_topics = np.flatnonzero(train_counts > 0).astype(np.int32)
    frames = []
    labels_by_split = {}
    all_embeddings = []
    all_labels = []
    for split in SPLITS:
        if split == "train":
            labels = raw_train_labels.copy()
            best_weight = fitted_train_strength[:, 0]
            weight_margin = fitted_train_strength[:, 1]
        else:
            weights = weights_by_split[split]
            has_keywords = weights.sum(axis=1) > 1e-12
            labels = np.full(len(weights), -1, dtype=np.int32)
            labels[has_keywords] = active_topics[
                np.argmax(weights[has_keywords][:, active_topics], axis=1)
            ]
            best_weight = np.where(labels >= 0, weights.max(axis=1), 0.0)
            second_weight = np.partition(weights, -2, axis=1)[:, -2]
            weight_margin = best_weight - second_weight
        labels_by_split[split] = labels
        frame = data.metadata[split][["work_id", "model_date", "quarter"]].copy()
        frame.insert(1, "split", split)
        frame["topic_id"] = labels
        frame["nmf_top1_weight"] = best_weight
        frame["nmf_top1_top2_margin"] = weight_margin
        frames.append(frame)
        all_embeddings.append(np.asarray(data.embeddings[split]))
        all_labels.append(labels)
    embeddings = np.concatenate(all_embeddings)
    labels = np.concatenate(all_labels)
    return (
        pd.concat(frames, ignore_index=True),
        embeddings,
        labels,
        labels_by_split,
        active_topics,
    )


def run_stability(
    args: argparse.Namespace,
    data: DataBundle,
    selected_k: int,
    base_model: MiniBatchNMF,
    base_validation_labels: np.ndarray,
) -> pd.DataFrame:
    rows = []
    variants = [
        ("seed29", 29, None),
        (
            "subsample80",
            args.seed,
            (data.x["train"].getnnz(axis=1) > 0)
            & (np.random.default_rng(903).random(data.x["train"].shape[0]) < 0.8),
        ),
    ]
    for name, seed, keep in variants:
        print(f"START stability {name}", flush=True)
        model, _, messages, seconds = fit_model(
            data.x["train"],
            selected_k,
            seed,
            args.max_iter,
            args.batch_size,
            keep,
        )
        labels = hard_assign(transform(model, data.x["validation"]))
        result = component_stability(
            base_model.components_, model.components_, base_validation_labels, labels
        )
        rows.append(
            {
                "variant": name,
                "seed": seed,
                "fit_documents": int(
                    keep.sum()
                    if keep is not None
                    else (data.x["train"].getnnz(axis=1) > 0).sum()
                ),
                "fit_seconds": seconds,
                "matched_topics": result.matched_topics,
                "component_cosine_mean": result.component_cosine_mean,
                "component_cosine_p10": result.component_cosine_p10,
                "validation_ari": result.validation_ari,
                "convergence_warnings": " | ".join(messages),
            }
        )
        print(
            f"DONE stability {name} component_cos={result.component_cosine_mean:.4f} "
            f"ARI={result.validation_ari:.4f}",
            flush=True,
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(args.output / "stability_metrics.csv", index=False)
    return frame


def run_final(args: argparse.Namespace, data: DataBundle, selected_k: int) -> None:
    candidate_dir = args.output / "candidates" / f"k{selected_k}"
    model: MiniBatchNMF = joblib.load(candidate_dir / "nmf.joblib")
    (
        paper_assignments,
        paper_embeddings,
        paper_labels,
        labels_by_split,
        active,
    ) = assign_all_papers(
        data,
        model,
        np.load(candidate_dir / "train_labels.npy"),
        np.load(candidate_dir / "train_assignment_strength.npy"),
    )
    centroids, counts = embedding_centroids(
        paper_embeddings, paper_labels, selected_k
    )
    centroids[np.setdiff1d(np.arange(selected_k), active)] = 0
    np.save(args.output / "topic_centroids.npy", centroids)
    paper_assignments.to_parquet(args.output / "paper_assignments.parquet", index=False)

    catalog = topic_keywords(model.components_, data.vocabulary)
    catalog["active"] = np.isin(np.arange(selected_k), active)
    catalog["paper_documents"] = counts
    for split in SPLITS:
        catalog[f"{split}_documents"] = np.bincount(
            labels_by_split[split][labels_by_split[split] >= 0], minlength=selected_k
        )
    catalog.to_csv(args.output / "topic_catalog.csv", index=False)
    joblib.dump(model, args.output / "selected_nmf.joblib", compress=1)

    # Thresholds are calibrated without leakage: validation documents against train-only centers.
    train_centroids = np.load(candidate_dir / "train_centroids.npy")
    validation_ids, validation_scores = nearest_centroid_assign(
        data.embeddings["validation"], train_centroids, active, top_n=2
    )
    valid = data.x["validation"].getnnz(axis=1) > 0
    thresholds = {
        "cosine_p10": float(np.quantile(validation_scores[valid, 0], 0.1)),
        "margin_p10": float(
            np.quantile(
                validation_scores[valid, 0] - validation_scores[valid, 1], 0.1
            )
        ),
        "calibration_documents": int(valid.sum()),
        "calibration": "2024 validation papers vs train-only topic centroids",
    }
    write_json(args.output / "confidence_thresholds.json", thresholds)

    corpus = pd.read_parquet(TRANSFER_ROOT / "data/model_corpus.parquet")
    transfer_mask = corpus.source.isin(["patent", "policy"]).to_numpy()
    transfer = corpus.loc[
        transfer_mask,
        ["doc_id", "source", "title", "date", "split", "origin", "language", "title_only"],
    ].reset_index(drop=True)
    transfer_embeddings = np.load(
        TRANSFER_ROOT / "models/embeddings.npy", mmap_mode="r"
    )[transfer_mask]
    topic_ids, scores = nearest_centroid_assign(
        transfer_embeddings, centroids, active, top_n=3
    )
    for rank in range(topic_ids.shape[1]):
        transfer[f"topic_{rank + 1}_id"] = topic_ids[:, rank]
        transfer[f"topic_{rank + 1}_cosine"] = scores[:, rank]
    transfer["top1_top2_margin"] = scores[:, 0] - scores[:, 1]
    transfer["low_cosine"] = scores[:, 0] < thresholds["cosine_p10"]
    transfer["low_margin"] = transfer.top1_top2_margin < thresholds["margin_p10"]
    transfer["needs_review"] = transfer.low_cosine | transfer.low_margin
    transfer.to_parquet(
        args.output / "patent_policy_assignments.parquet", index=False
    )

    stability_path = args.output / "stability_metrics.csv"
    if stability_path.exists() and not args.overwrite:
        stability = pd.read_csv(stability_path)
    else:
        stability = run_stability(
            args,
            data,
            selected_k,
            model,
            labels_by_split["validation"],
        )
    summary_by_source = (
        transfer.groupby("source")
        .agg(
            documents=("doc_id", "size"),
            top1_cosine_mean=("topic_1_cosine", "mean"),
            top1_cosine_median=("topic_1_cosine", "median"),
            margin_mean=("top1_top2_margin", "mean"),
            needs_review_fraction=("needs_review", "mean"),
        )
        .reset_index()
    )
    summary_by_source.to_csv(args.output / "transfer_summary.csv", index=False)
    selected_metrics = json.loads(
        (candidate_dir / "metrics.json").read_text(encoding="utf-8")
    )
    candidate_comparison = pd.read_csv(args.output / "candidate_metrics.csv")
    candidate_comparison = candidate_comparison[
        [
            "requested_k",
            "active_topics",
            "sampled_cosine_silhouette",
            "simplified_silhouette_mean",
            "davies_bouldin",
            "nearest_center_cosine_mean",
            "keyword_embedding_ari",
            "nmf_relative_reconstruction_error",
            "selected",
        ]
    ]
    report = f"""# OpenAlex keyword TF-IDF + NMF report

## Selection

- Selected nominal K: {selected_k}
- Active paper topics: {int((counts > 0).sum())}
- Candidate window: 400, 450, 500, 550, 600; selection was restricted to 450--550.
- Sampled validation cosine silhouette: {selected_metrics['sampled_cosine_silhouette']:.6f}
- Simplified validation silhouette: {selected_metrics['simplified_silhouette_mean']:.6f}
- Davies--Bouldin: {selected_metrics['davies_bouldin']:.6f}
- Mean nearest-center cosine: {selected_metrics['nearest_center_cosine_mean']:.6f}
- Keyword-label/embedding-nearest-center ARI: {selected_metrics['keyword_embedding_ari']:.6f}

NMF was fitted only on score-weighted OpenAlex keyword TF-IDF from training papers. Patent and policy text never entered NMF fitting or candidate selection.

### Candidate comparison

{candidate_comparison.to_markdown(index=False)}

## Transfer confidence

- Validation cosine p10 threshold: {thresholds['cosine_p10']:.6f}
- Validation top1--top2 margin p10 threshold: {thresholds['margin_p10']:.6f}
- A patent/policy record is marked `needs_review` when either threshold is missed.

{summary_by_source.to_markdown(index=False)}

## Stability

{stability.to_markdown(index=False)}

## Interpretation limits

Silhouette and Davies--Bouldin quantify geometry in the BGE-M3 embedding space; they are not expert-label accuracy. OpenAlex keyword assignment and BGE-M3 each introduce model/platform preferences. Low-confidence transfer records should not be treated as reliably classified without review.
"""
    (args.output / "REPORT.md").write_text(report, encoding="utf-8")
    print(
        f"FINAL active={len(active)} transfer={len(transfer)} "
        f"review={transfer.needs_review.mean():.3f}",
        flush=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["grid", "final", "all"])
    parser.add_argument("--k", nargs="+", type=int, default=[400, 450, 500, 550, 600])
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--max-iter", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output = args.output.resolve()
    data = DataBundle()
    if args.action in {"grid", "all"}:
        selected = run_grid(args, data)
    else:
        selected = int(
            json.loads((args.output / "selection.json").read_text(encoding="utf-8"))[
                "selected_k"
            ]
        )
    if args.action in {"final", "all"}:
        run_final(args, data, selected)


if __name__ == "__main__":
    main()
