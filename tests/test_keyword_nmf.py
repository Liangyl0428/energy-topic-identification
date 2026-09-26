import sys
from pathlib import Path

import numpy as np
import pytest


SRC = Path(__file__).resolve().parents[1] / "pipelines/keyword_nmf/src"
sys.path.insert(0, str(SRC))

from components import (  # noqa: E402
    component_stability,
    embedding_centroids,
    hard_assign,
    nearest_centroid_assign,
    simplified_silhouette,
    contribution_weights,
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


def test_topic_assignment_is_invariant_to_equivalent_nmf_factorizations():
    w = np.array([[.9, .6], [.1, .8]])
    h = np.array([[1., 0.], [0., 2.]])
    scale = np.array([100., .01])
    np.testing.assert_allclose(w @ h, (w / scale) @ (h * scale[:, None]))
    a = contribution_weights(w, h)
    b = contribution_weights(w / scale, h * scale[:, None])
    np.testing.assert_allclose(a, b)
    assert hard_assign(a).tolist() == hard_assign(b).tolist() == [1, 1]


def test_same_document_uses_same_inference_across_time_splits():
    from types import SimpleNamespace
    from scipy import sparse
    import pandas as pd
    from run_pipeline import assign_all_papers

    class FrozenModel:
        n_components = 2
        components_ = np.eye(2)
        def transform(self, matrix):
            return matrix.toarray()

    splits = ['train', 'validation', 'replay']
    matrix = sparse.csr_matrix([[1., 2.], [3., 1.], [0., 0.]])
    data = SimpleNamespace(x={s: matrix for s in splits},
        embeddings={s: np.eye(3) for s in splits},
        metadata={s: pd.DataFrame({'work_id': ['a', 'b', 'c'], 'model_date': ['2024-01-01'] * 3,
                                  'quarter': ['2024Q1'] * 3}) for s in splits})
    _, _, _, labels, _ = assign_all_papers(data, FrozenModel(), np.array([0, 0, 0]), np.zeros((3, 2)))
    for split in splits:
        assert labels[split].tolist() == [1, 0, -1]


def test_later_top1_is_not_forced_into_a_different_training_topic():
    from types import SimpleNamespace
    from scipy import sparse
    import pandas as pd
    from run_pipeline import assign_all_papers

    class FrozenModel:
        n_components = 2
        components_ = np.eye(2)
        def transform(self, matrix):
            return matrix.toarray()

    values = {'train': [[1., 0.]], 'validation': [[0., 2.]], 'replay': [[0., 3.]]}
    data = SimpleNamespace(x={s: sparse.csr_matrix(v) for s, v in values.items()},
        embeddings={s: np.ones((1, 2)) for s in values},
        metadata={s: pd.DataFrame({'work_id': [s], 'model_date': ['2024-01-01'],
                                  'quarter': ['2024Q1']}) for s in values})
    _, _, _, labels, active = assign_all_papers(data, FrozenModel())
    assert [labels[s][0] for s in values] == [0, 1, 1]
    assert active.tolist() == [0, 1]


@pytest.mark.parametrize('bad', [[[0., 0.]], [[np.nan, 1.]], [[np.inf, 1.]]])
def test_invalid_embedding_cannot_receive_topic(bad):
    with pytest.raises(ValueError):
        nearest_centroid_assign(np.array(bad), np.eye(2))


def test_cosine_ties_use_topic_id_independent_of_active_order():
    ids, _ = nearest_centroid_assign(np.array([[1., 1.]]), np.eye(2), np.array([1, 0]))
    assert ids.tolist() == [[0, 1]]


@pytest.mark.parametrize('mutation', ['nan', 'inf', 'duplicate', 'empty'])
def test_selection_rejects_invalid_candidate_metrics(mutation):
    import pandas as pd
    from selection_experiments import choose
    from run_pipeline import select_candidate
    repo = Path(__file__).resolve().parents[1]
    frame = pd.read_csv(repo / 'assets/nmf500/candidate_metrics.csv')
    if mutation in {'nan', 'inf'}:
        frame.loc[frame.requested_k.eq(500), 'davies_bouldin'] = float(mutation)
    elif mutation == 'duplicate':
        frame = pd.concat([frame, frame[frame.requested_k.eq(500)]], ignore_index=True)
    else:
        frame = frame.iloc[:0]
    for select in [choose, select_candidate]:
        with pytest.raises(ValueError):
            select(frame)


def test_selection_experiment_rejects_invalid_controls():
    import pandas as pd
    from selection_experiments import choose
    repo = Path(__file__).resolve().parents[1]
    frame = pd.read_csv(repo / 'assets/nmf500/candidate_metrics.csv')
    for options in [{'penalty': np.nan}, {'tolerance': np.inf}, {'omit': 'typo'}]:
        with pytest.raises(ValueError):
            choose(frame, **options)


def test_current_snapshot_keeps_inactive_component_and_audit_accounting():
    import json
    import pandas as pd
    snapshot = Path(__file__).resolve().parents[1] / 'assets/nmf500'
    catalog = pd.read_csv(snapshot/'current_topic_catalog.csv')
    assert catalog.topic_id.tolist() == list(range(500))
    assert catalog.active.equals(catalog.paper_documents.gt(0))
    assert catalog.loc[~catalog.active, 'category_id'].tolist() == ['N0069']
    assert (catalog[['train_documents', 'validation_documents', 'replay_documents']].sum(axis=1)
            == catalog.paper_documents).all()
    audit = json.loads((snapshot/'CURRENT_INFERENCE_AUDIT.json').read_text())
    changes = pd.read_csv(snapshot/'assignment_changes_v021.csv')
    assert changes['size'].sum() == audit['papers'] == 142000
    assert changes['sum'].sum() == audit['changed_from_v020'] == 30359
    assert not audit['semantic_accuracy_measured']
