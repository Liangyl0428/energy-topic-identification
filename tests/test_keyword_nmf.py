import sys
from pathlib import Path

import numpy as np


SRC = Path(__file__).resolve().parents[1] / "pipelines/keyword_nmf/src"
sys.path.insert(0, str(SRC))

from components import (  # noqa: E402
    component_stability,
    embedding_centroids,
    hard_assign,
    nearest_centroid_assign,
    simplified_silhouette,
)


def test_hard_assign_marks_zero_rows_unassigned():
    weights = np.array([[0.1, 0.9], [0.0, 0.0], [0.7, 0.3]])
    assert hard_assign(weights).tolist() == [1, -1, 0]


def test_centroids_and_nearest_assignment_use_cosine():
    embeddings = np.array([[1.0, 0.0], [0.8, 0.2], [0.0, 1.0]], dtype=np.float32)
    labels = np.array([0, 0, 1])
    centroids, counts = embedding_centroids(embeddings, labels, 3)
    assert counts.tolist() == [2, 1, 0]
    ids, scores = nearest_centroid_assign(embeddings, centroids, top_n=2)
    assert ids[:, 0].tolist() == [0, 0, 1]
    assert np.all(scores[:, 0] >= scores[:, 1])


def test_simplified_silhouette_is_positive_for_separated_points():
    embeddings = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0], [0.1, 0.9]])
    labels = np.array([0, 0, 1, 1])
    centroids, _ = embedding_centroids(embeddings, labels, 2)
    values, alternatives = simplified_silhouette(embeddings, labels, centroids)
    assert np.all(values > 0.9)
    assert alternatives.tolist() == [1, 1, 0, 0]


def test_component_stability_recovers_permutation():
    base = np.eye(3, dtype=np.float32)
    comparison = base[[2, 0, 1]]
    base_labels = np.array([0, 1, 2, 0, 1, 2])
    comparison_labels = np.array([1, 2, 0, 1, 2, 0])
    result = component_stability(base, comparison, base_labels, comparison_labels)
    assert result.component_cosine_mean == 1.0
    assert result.validation_ari == 1.0


def test_actual_selection_preference_and_metric_ablation():
    import pandas as pd
    from selection_experiments import choose
    repo = Path(__file__).resolve().parents[1]
    frame = pd.read_csv(repo / 'assets/nmf500/candidate_metrics.csv')
    assert choose(frame) == 500
    assert choose(frame, tolerance=0) == 450
    assert choose(frame, omit='davies_bouldin') == 450
