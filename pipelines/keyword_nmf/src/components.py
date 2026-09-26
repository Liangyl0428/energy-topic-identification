"""Reusable metrics and assignment helpers for the keyword-NMF pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import adjusted_rand_score, davies_bouldin_score, silhouette_score


EPS = 1e-12
ASSIGNMENT_METHOD = "fixed-H-l2-contribution-v2"


def contribution_weights(weights: np.ndarray, components: np.ndarray) -> np.ndarray:
    """Contribution to unit-norm topics; invariant to reciprocal W/H scaling.

    These nonnegative contributions are not posterior topic probabilities.
    """
    weights = np.asarray(weights)
    components = np.asarray(components)
    if weights.ndim != 2 or components.ndim != 2 or weights.shape[1] != len(components):
        raise ValueError("Incompatible NMF weights/components")
    if not np.isfinite(weights).all() or not np.isfinite(components).all() or (weights < 0).any() or (components < 0).any():
        raise ValueError("NMF values must be finite and nonnegative")
    return weights * np.linalg.norm(components, axis=1)


def infer_contributions(model, matrix, batch_size=4096):
    """Use the same fixed-H transform and batch size for every time split."""
    if type(batch_size) is not int or batch_size <= 0:
        raise ValueError("batch_size must be positive")
    result = np.zeros((matrix.shape[0], model.n_components), dtype=np.float32)
    rows = np.flatnonzero(matrix.getnnz(axis=1) > 0)
    for start in range(0, len(rows), batch_size):
        selected = rows[start:start + batch_size]
        result[selected] = contribution_weights(model.transform(matrix[selected]), model.components_)
    return result


def l2_normalize(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return values / np.maximum(norms, EPS)


def hard_assign(weights: np.ndarray, minimum_mass: float = EPS) -> np.ndarray:
    """Return the maximum-weight component, or -1 for empty representations."""
    weights = np.asarray(weights)
    if weights.ndim != 2 or weights.shape[1] == 0 or not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError("Expected finite nonnegative topic weights")
    labels = np.argmax(weights, axis=1).astype(np.int32)
    labels[np.asarray(weights.sum(axis=1)).ravel() <= minimum_mass] = -1
    return labels


def embedding_centroids(
    embeddings: np.ndarray, labels: np.ndarray, n_topics: int
) -> tuple[np.ndarray, np.ndarray]:
    """Compute L2-normalized embedding means and document counts per topic."""
    embeddings = np.asarray(embeddings, dtype=np.float32)
    labels = np.asarray(labels)
    sums = np.zeros((n_topics, embeddings.shape[1]), dtype=np.float64)
    valid = (labels >= 0) & (labels < n_topics)
    np.add.at(sums, labels[valid], embeddings[valid])
    counts = np.bincount(labels[valid], minlength=n_topics).astype(np.int64)
    centroids = l2_normalize(sums.astype(np.float32))
    centroids[counts == 0] = 0
    return centroids, counts


def nearest_centroid_assign(
    embeddings: np.ndarray,
    centroids: np.ndarray,
    active_topics: np.ndarray | None = None,
    batch_size: int = 4096,
    top_n: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """Cosine-nearest topic IDs and scores, evaluated in bounded-size batches."""
    embeddings = np.asarray(embeddings)
    centroids = np.asarray(centroids)
    if embeddings.ndim != 2 or centroids.ndim != 2 or embeddings.shape[1] != centroids.shape[1]:
        raise ValueError("Incompatible embedding dimensions")
    if not np.isfinite(embeddings).all() or not np.isfinite(centroids).all():
        raise ValueError("Non-finite embeddings")
    if (np.linalg.norm(embeddings, axis=1) <= EPS).any():
        raise ValueError("Zero embedding cannot receive a cosine topic")
    if type(batch_size) is not int or batch_size <= 0 or type(top_n) is not int or top_n <= 0:
        raise ValueError("Positive batch_size and top_n required")
    embeddings = l2_normalize(embeddings)
    centroids = l2_normalize(centroids)
    if active_topics is None:
        active_topics = np.flatnonzero(np.linalg.norm(centroids, axis=1) > EPS)
    active_topics = np.asarray(active_topics, dtype=np.int32)
    if len(np.unique(active_topics)) != len(active_topics) or (active_topics < 0).any() or (active_topics >= len(centroids)).any():
        raise ValueError("Invalid active topic IDs")
    active_topics = np.sort(active_topics)
    if (np.linalg.norm(centroids[active_topics], axis=1) <= EPS).any():
        raise ValueError("Inactive centroid selected")
    if not len(active_topics):
        raise ValueError("No active topic centroids")
    top_n = min(int(top_n), len(active_topics))
    topic_ids = np.empty((len(embeddings), top_n), dtype=np.int32)
    scores = np.empty((len(embeddings), top_n), dtype=np.float32)
    active_centroids = centroids[active_topics]
    for start in range(0, len(embeddings), batch_size):
        stop = min(start + batch_size, len(embeddings))
        similarity = embeddings[start:stop] @ active_centroids.T
        local = np.argsort(-similarity, axis=1, kind="stable")[:, :top_n]
        topic_ids[start:stop] = active_topics[local]
        scores[start:stop] = np.take_along_axis(similarity, local, axis=1)
    return topic_ids, scores


def simplified_silhouette(
    embeddings: np.ndarray,
    labels: np.ndarray,
    centroids: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Centroid approximation to cosine silhouette and nearest alternative topic."""
    embeddings = l2_normalize(embeddings)
    centroids = l2_normalize(centroids)
    labels = np.asarray(labels)
    active = np.flatnonzero(np.linalg.norm(centroids, axis=1) > EPS)
    valid = (labels >= 0) & np.isin(labels, active)
    values = np.full(len(labels), np.nan, dtype=np.float32)
    alternatives = np.full(len(labels), -1, dtype=np.int32)
    if not valid.any() or len(active) < 2:
        return values, alternatives

    rows = np.flatnonzero(valid)
    similarities = embeddings[rows] @ centroids[active].T
    active_lookup = {int(topic): i for i, topic in enumerate(active)}
    assigned_columns = np.fromiter(
        (active_lookup[int(topic)] for topic in labels[rows]), dtype=np.int32
    )
    assigned_similarity = similarities[np.arange(len(rows)), assigned_columns]
    similarities[np.arange(len(rows)), assigned_columns] = -np.inf
    alternative_columns = np.argmax(similarities, axis=1)
    alternative_similarity = similarities[np.arange(len(rows)), alternative_columns]
    a = 1.0 - assigned_similarity
    b = 1.0 - alternative_similarity
    values[rows] = (b - a) / np.maximum(np.maximum(a, b), EPS)
    alternatives[rows] = active[alternative_columns]
    return values, alternatives


def gini(values: Iterable[int]) -> float:
    values = np.asarray(list(values), dtype=np.float64)
    values = values[values >= 0]
    if not len(values) or values.sum() <= 0:
        return 0.0
    values.sort()
    n = len(values)
    return float((2 * np.dot(np.arange(1, n + 1), values) / values.sum() - n - 1) / n)


def effective_topic_count(counts: np.ndarray) -> float:
    probabilities = np.asarray(counts, dtype=np.float64)
    probabilities = probabilities[probabilities > 0]
    probabilities /= probabilities.sum()
    return float(np.exp(-(probabilities * np.log(probabilities)).sum()))


def nearest_center_separation(centroids: np.ndarray, counts: np.ndarray) -> dict[str, float]:
    active = np.flatnonzero(np.asarray(counts) > 0)
    if len(active) < 2:
        return {
            "nearest_center_cosine_mean": float("nan"),
            "nearest_center_cosine_p90": float("nan"),
            "nearest_center_cosine_max": float("nan"),
        }
    normalized = l2_normalize(centroids[active])
    similarity = normalized @ normalized.T
    np.fill_diagonal(similarity, -np.inf)
    nearest = similarity.max(axis=1)
    return {
        "nearest_center_cosine_mean": float(nearest.mean()),
        "nearest_center_cosine_p90": float(np.quantile(nearest, 0.9)),
        "nearest_center_cosine_max": float(nearest.max()),
    }


def candidate_metrics(
    *,
    requested_k: int,
    train_labels: np.ndarray,
    validation_labels: np.ndarray,
    train_centroids: np.ndarray,
    train_counts: np.ndarray,
    validation_embeddings: np.ndarray,
    validation_has_keywords: np.ndarray,
    reconstruction_error: float,
    relative_reconstruction_error: float,
    random_state: int = 311,
    silhouette_sample_size: int = 6000,
) -> dict[str, float | int]:
    """Compute independent-validation geometry and cluster-size diagnostics."""
    counts = np.asarray(train_counts)
    active = counts > 0
    active_counts = counts[active]
    valid = (
        np.asarray(validation_has_keywords, dtype=bool)
        & (validation_labels >= 0)
        & active[np.clip(validation_labels, 0, requested_k - 1)]
    )
    valid_rows = np.flatnonzero(valid)
    valid_labels = validation_labels[valid_rows]
    valid_embeddings = np.asarray(validation_embeddings[valid_rows], dtype=np.float32)

    rng = np.random.default_rng(random_state)
    sampled_rows = valid_rows
    if len(sampled_rows) > silhouette_sample_size:
        sampled_rows = np.sort(
            rng.choice(sampled_rows, silhouette_sample_size, replace=False)
        )
    sampled_labels = validation_labels[sampled_rows]
    if 1 < len(np.unique(sampled_labels)) < len(sampled_rows):
        sampled_silhouette = float(
            silhouette_score(
                np.asarray(validation_embeddings[sampled_rows], dtype=np.float32),
                sampled_labels,
                metric="cosine",
            )
        )
    else:
        sampled_silhouette = float("nan")

    simplified, _ = simplified_silhouette(
        validation_embeddings, validation_labels, train_centroids
    )
    simplified_valid = simplified[np.isfinite(simplified)]

    if 1 < len(np.unique(valid_labels)) < len(valid_labels):
        db = float(davies_bouldin_score(valid_embeddings, valid_labels))
    else:
        db = float("nan")

    nearest_ids, nearest_scores = nearest_centroid_assign(
        validation_embeddings, train_centroids, np.flatnonzero(active), top_n=2
    )
    agreement_rows = valid & (nearest_ids[:, 0] >= 0)
    agreement = float(
        np.mean(nearest_ids[agreement_rows, 0] == validation_labels[agreement_rows])
    )
    ari = float(
        adjusted_rand_score(
            validation_labels[agreement_rows], nearest_ids[agreement_rows, 0]
        )
    )

    result: dict[str, float | int] = {
        "requested_k": int(requested_k),
        "active_topics": int(active.sum()),
        "empty_topics": int((~active).sum()),
        "empty_topic_fraction": float((~active).mean()),
        "train_documents_assigned": int((train_labels >= 0).sum()),
        "train_topic_size_min": int(active_counts.min()) if len(active_counts) else 0,
        "train_topic_size_p10": float(np.quantile(active_counts, 0.1)) if len(active_counts) else 0,
        "train_topic_size_median": float(np.median(active_counts)) if len(active_counts) else 0,
        "train_topic_size_p90": float(np.quantile(active_counts, 0.9)) if len(active_counts) else 0,
        "train_topics_below_20": int((active_counts < 20).sum()),
        "train_topic_size_gini": gini(active_counts),
        "effective_topic_count": effective_topic_count(active_counts),
        "validation_keyword_coverage": float(np.mean(validation_has_keywords)),
        "validation_active_topic_coverage": float(valid.mean()),
        "sampled_cosine_silhouette": sampled_silhouette,
        "sampled_silhouette_n": int(len(sampled_rows)),
        "simplified_silhouette_mean": float(np.mean(simplified_valid)),
        "simplified_silhouette_negative_fraction": float(
            np.mean(simplified_valid < 0)
        ),
        "davies_bouldin": db,
        "keyword_embedding_top1_agreement": agreement,
        "keyword_embedding_ari": ari,
        "validation_nearest_centroid_cosine_mean": float(nearest_scores[valid, 0].mean()),
        "validation_nearest_centroid_margin_mean": float(
            (nearest_scores[valid, 0] - nearest_scores[valid, 1]).mean()
        ),
        "nmf_reconstruction_error": float(reconstruction_error),
        "nmf_relative_reconstruction_error": float(relative_reconstruction_error),
    }
    result.update(nearest_center_separation(train_centroids, counts))
    return result


@dataclass(frozen=True)
class StabilityResult:
    matched_topics: int
    component_cosine_mean: float
    component_cosine_p10: float
    validation_ari: float


def component_stability(
    base_components: np.ndarray,
    comparison_components: np.ndarray,
    base_validation_labels: np.ndarray,
    comparison_validation_labels: np.ndarray,
) -> StabilityResult:
    base = l2_normalize(base_components)
    comparison = l2_normalize(comparison_components)
    similarities = base @ comparison.T
    base_ids, comparison_ids = linear_sum_assignment(-similarities)
    mapping = np.full(comparison.shape[0], -1, dtype=np.int32)
    mapping[comparison_ids] = base_ids
    mapped = np.where(
        comparison_validation_labels >= 0,
        mapping[np.clip(comparison_validation_labels, 0, len(mapping) - 1)],
        -1,
    )
    common = (base_validation_labels >= 0) & (mapped >= 0)
    matched = similarities[base_ids, comparison_ids]
    return StabilityResult(
        matched_topics=int(len(matched)),
        component_cosine_mean=float(matched.mean()),
        component_cosine_p10=float(np.quantile(matched, 0.1)),
        validation_ari=float(
            adjusted_rand_score(base_validation_labels[common], mapped[common])
        ),
    )
