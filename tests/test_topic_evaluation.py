from pathlib import Path
import sys
import numpy as np
import pytest
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipelines/full_nmf'))
from evaluate_topics import Geometry, unit, dense_geometry, sampled_silhouette, identity_hash, agreement
from evaluate_coherence import keyword_quality
from scipy import sparse


def fixture():
    rng=np.random.default_rng(17)
    y=np.repeat([0,3,8],[13,20,27])
    centers=rng.normal(size=(9,7))
    return unit(centers[y]+rng.normal(size=(60,7))*.2),y


def test_full_geometry_matches_sklearn():
    x,y=fixture();r=dense_geometry(x,y)
    assert r['calinski_harabasz']==pytest.approx(calinski_harabasz_score(x,y),rel=1e-10)
    assert r['davies_bouldin']==pytest.approx(davies_bouldin_score(x,y),rel=1e-10)
    assert r['documents']==60 and r['active_topics']==3


def test_streamed_geometry_matches_dense():
    x,y=fixture();g=Geometry(9,7)
    for ix in np.array_split(np.arange(60),7):g.add(x[ix],y[ix])
    for ix in np.array_split(np.arange(60),11):g.add_scatter(x[ix],y[ix])
    expected=dense_geometry(x,y)
    for k,v in g.finish().items():assert v==pytest.approx(expected[k],rel=1e-10)


def test_silhouette_uses_same_ids_and_is_label_permutation_invariant():
    x,y=fixture();ids=np.arange(60)*7
    rows=sampled_silhouette(x,{'a':y,'b':100-y},ids,limit=40)
    for a,b in zip(rows[::2],rows[1::2]):
        assert a['sample_ids_sha256']==b['sample_ids_sha256']
        assert a['cosine_silhouette']==pytest.approx(b['cosine_silhouette'])
    assert len({r['sample_ids_sha256'] for r in rows})==3
    assert agreement(y,100-y)=={'ARI':1.,'NMI':1.}


def test_invalid_vectors_and_degenerate_geometry_rejected():
    for x in [np.zeros((2,3)),np.array([[np.nan,1]])]:
        with pytest.raises(ValueError):unit(x)
    with pytest.raises(ValueError):dense_geometry(np.eye(3),np.zeros(3,dtype=int))
    assert identity_hash([1,2])!=identity_hash([2,1])


def test_keyword_coherence_identical_pairs_and_zero_cooccurrence():
    x=sparse.csr_matrix([[1.,1.,0.,0.],[1.,1.,0.,0.],[0.,0.,1.,1.],[0.,0.,1.,1.]])
    df=np.asarray(x.sum(0)).ravel();cooc=(x.T@x).tocsr()
    r=keyword_quality(x,np.array([0,0,1,1]),cooc,df,4)
    assert r['npmi_macro']==pytest.approx(1.)
    assert r['topic_keyword_diversity']==1.
    mixed=keyword_quality(x,np.array([0,1,0,1]),cooc,df,4)
    assert mixed['npmi_macro']==pytest.approx(-1/3)
    assert mixed['topic_keyword_diversity']==.5
