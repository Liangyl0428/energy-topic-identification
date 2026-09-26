"""Audit corrected labels against the frozen v0.2.0 delivery, without refitting H.

Full raw workspace required. Historical K-selection metrics remain historical;
this separately measures the actual v0.2.1 inference used by both downstreams.
"""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from components import ASSIGNMENT_METHOD, candidate_metrics, embedding_centroids

REPO = Path(__file__).resolve().parents[3]
ROOT = REPO.parent


def run():
    out = REPO / 'assets/nmf500'
    output_root = ROOT / 'energy-topic-hotspots/outputs'
    old_path, new_path = output_root / 'nmf500', output_root / 'nmf500_v021'
    old = pd.read_parquet(old_path / 'paper_assignments.parquet')
    new = pd.read_parquet(new_path / 'paper_assignments.parquet')
    if set(old.work_id) != set(new.work_id) or not new.assignment_method.eq(ASSIGNMENT_METHOD).all():
        raise ValueError('Audit requires identical paper IDs and the current inference method')
    comparison = new[['work_id', 'split', 'topic_id']].merge(old[['work_id', 'topic_id']], on='work_id',
        suffixes=('', '_v020'), validate='one_to_one')
    comparison['changed'] = comparison.topic_id.ne(comparison.topic_id_v020)
    changes = comparison.groupby('split').changed.agg(['size', 'sum', 'mean']).reset_index()
    changes.to_csv(out / 'assignment_changes_v021.csv', index=False)
    old_transfer = pd.read_parquet(old_path / 'patent_policy_assignments.parquet')
    new_transfer = pd.read_parquet(new_path / 'patent_policy_assignments.parquet')
    if set(old_transfer.doc_id) != set(new_transfer.doc_id):
        raise ValueError('Audit requires identical transfer document IDs')
    compared = new_transfer[['doc_id', 'source', 'topic_1_id']].merge(
        old_transfer[['doc_id', 'source', 'topic_1_id']], on=['doc_id', 'source'],
        suffixes=('', '_v020'), validate='one_to_one')
    if len(compared) != len(new_transfer):
        raise ValueError('Transfer source labels changed during comparison')
    compared['changed'] = compared.topic_1_id.ne(compared.topic_1_id_v020)
    transfer_changes = compared.groupby('source').changed.agg(['size', 'sum', 'mean'])
    transfer_changes.reset_index().to_csv(out / 'transfer_changes_v021.csv', index=False)
    quality = new.groupby('topic_id').agg(documents=('work_id', 'size'),
        median_relative_contribution=('nmf_relative_top1', 'median'),
        median_relative_margin=('nmf_relative_margin', 'median'),
        margin_below_005_fraction=('nmf_relative_margin', lambda x: float(x.lt(.05).mean()))).reset_index()
    quality.to_csv(out / 'topic_assignment_quality.csv', index=False)
    train = new[new.split.eq('train')]
    validation = new[new.split.eq('validation')]
    train_embeddings = np.load(ROOT / 'aaaa/bge_m3/models/bge_train.npy', mmap_mode='r')
    validation_embeddings = np.load(ROOT / 'aaaa/bge_m3/models/bge_validation.npy', mmap_mode='r')
    centers, counts = embedding_centroids(train_embeddings, train.topic_id.to_numpy(), 500)
    legacy = json.loads((REPO / 'pipelines/keyword_nmf/results/candidates/k500/metrics.json').read_text())
    metrics = candidate_metrics(requested_k=500, train_labels=train.topic_id.to_numpy(),
        validation_labels=validation.topic_id.to_numpy(), train_centroids=centers, train_counts=counts,
        validation_embeddings=validation_embeddings, validation_has_keywords=validation.topic_id.ge(0).to_numpy(),
        reconstruction_error=legacy['nmf_reconstruction_error'],
        relative_reconstruction_error=legacy['nmf_relative_reconstruction_error'])
    pd.DataFrame([{'assignment_method': ASSIGNMENT_METHOD, **metrics}]).to_csv(out / 'current_validation_metrics.csv', index=False)
    model = joblib.load(REPO / 'pipelines/keyword_nmf/results/selected_nmf.joblib')
    norms = np.linalg.norm(model.components_, axis=1)
    audit = dict(version='v0.2.1', assignment_method=ASSIGNMENT_METHOD,
        papers=len(new), changed_from_v020=int(comparison.changed.sum()),
        fraction_changed_from_v020=float(comparison.changed.mean()),
        transfer_changes_from_v020=transfer_changes.to_dict('index'),
        input_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for directory in [old_path, new_path]
                      for p in [directory / 'paper_assignments.parquet', directory / 'patent_policy_assignments.parquet']},
        component_norm_min=float(norms.min()), component_norm_max=float(norms.max()),
        margin_below_005_fraction=float(new.nmf_relative_margin.lt(.05).mean()),
        relative_mass_is_probability=False, semantic_accuracy_measured=False,
        selected_k=500, selection_basis='Fixed business resolution retained; no claim that corrected inference re-optimizes K',
        historical_grid='candidate_metrics.csv and selection experiments describe v0.2.0 fit-W labels only',
        fitted_H_reused=True, actual_inference_metrics=metrics,
        caveats=['BGE geometry is not expert-label accuracy',
                 'Paper similarity quantiles do not calibrate patent/policy precision',
                 'All transfer links require semantic review',
                 'Uniform .05 margin is a sensitivity setting, not calibrated abstention'])
    (out / 'CURRENT_INFERENCE_AUDIT.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    with threadpool_limits(2):
        run()
