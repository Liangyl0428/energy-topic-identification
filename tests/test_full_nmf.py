"""Full-population coverage and centroid semantics on a small constructed corpus."""
from pathlib import Path
import importlib.util
import json
import sys
import numpy as np
import pandas as pd
import pytest

SRC=Path(__file__).resolve().parents[1]/'pipelines/full_nmf'


def module(name):
    sys.path.insert(0,str(SRC))
    spec=importlib.util.spec_from_file_location('full_'+name,SRC/(name+'.py'))
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


def test_keywords_preserve_phrases_and_do_not_invent_scores():
    parse=module('prepare').parse_keywords
    got=parse(json.dumps([{'id':'k1','display_name':'thermal energy storage','score':.8},
        {'id':'k2','display_name':'missing score'},{'id':'k3','display_name':'invalid','score':float('nan')}]),'')
    assert got['k1']==('thermal energy storage',.8)
    assert got['k2'][1]==got['k3'][1]==0
    assert parse('invalid json','whole phrase;second phrase')['label:whole phrase']==('whole phrase',0)


def test_finalization_counts_every_record_and_uses_papers_only(tmp_path,monkeypatch):
    f=module('finalize'); monkeypatch.setattr(f,'RUN',tmp_path)
    corpus=tmp_path/'corpus';corpus.mkdir()
    for folder in ['paper_assignments','embeddings']:(tmp_path/folder).mkdir()
    for marker in ['PREPARE_COMPLETE','TRAINING_COMPLETE','INFERENCE_COMPLETE','ENCODING_COMPLETE']:
        (tmp_path/(marker+'.json')).write_text(json.dumps({'paper_count':5,'papers':5,'documents':9}))
    (tmp_path/'selected_nmf.joblib').write_bytes(b'test model identity')
    sources=['paper']*5+['patent']*2+['policy']*2
    data=pd.DataFrame({'row_id':range(9),'doc_id':[f'{s}:{i}' for i,s in enumerate(sources)],'source':sources,
        'date':'2026-01-01','title':'example','title_only':False,'retracted':False,'template_record':False,
        'usable':[True]*8+[False]})
    p=corpus/'part-00000.parquet';data.to_parquet(p,index=False)
    monkeypatch.setattr(f,'parts',lambda:[p]);monkeypatch.setattr(f,'CORPUS',corpus)
    vectors=np.zeros((9,1024),np.float32)
    vectors[0,0]=1;vectors[1,:2]=[.6,.8];vectors[2,1]=1;vectors[3,2]=1
    vectors[4,3]=1;vectors[5,0]=1;vectors[6,2]=1;vectors[7,1]=1
    np.save(tmp_path/'embeddings/part-00000.npy',vectors)
    pd.DataFrame({'row_id':range(5),'topic_id':[0,0,1,2,-1],
        'assignment_status':['keyword_nmf_assigned']*4+['missing_scored_in_vocabulary_keywords'],
        'nmf_relative_top1':[1]*5,'nmf_relative_margin':[1]*5}).to_parquet(tmp_path/'paper_assignments/part-00000.parquet',index=False)
    pd.DataFrame({'topic_id':range(500),'category_id':[f'F{i+1:04d}' for i in range(500)]}).to_csv(tmp_path/'topic_catalog.csv',index=False)
    f.main()
    summary=json.loads((tmp_path/'SUMMARY.json').read_text())
    assert summary['population_records']==9
    assert summary['papers']==5 and summary['patents']==summary['policies']==2
    assert summary['assigned_records']==7 and summary['unassigned_records']==2
    centers=np.load(tmp_path/'topic_centroids.npy')
    np.testing.assert_allclose(centers[0,:2],[1.6/np.sqrt(3.2),.8/np.sqrt(3.2)],atol=1e-6)
    assert np.load(tmp_path/'topic_centroid_counts.npy')[:3].tolist()==[2,1,1]
    assignments=pd.read_parquet(tmp_path/'assignments/part-00000.parquet')
    assert assignments.topic_id.tolist()==[0,0,1,2,-1,0,2,1,-1]
    assert (tmp_path/'COMPLETE.json').exists()


def test_incomplete_population_cannot_be_finalized(tmp_path,monkeypatch):
    f=module('finalize');monkeypatch.setattr(f,'RUN',tmp_path)
    with pytest.raises(RuntimeError,match='Missing full stage'):
        f.main()


def test_cached_fixed_h_updates_match_sklearn():
    import copy
    from scipy import sparse
    from sklearn.decomposition import MiniBatchNMF
    sys.path.insert(0,str(SRC))
    from fast_nmf import CachedMiniBatchNMF
    rng=np.random.default_rng(17)
    x=sparse.csr_matrix(rng.random((30,18),dtype=np.float32))
    original=MiniBatchNMF(n_components=5,init='random',random_state=17,transform_max_iter=50)
    original.partial_fit(x)
    fast=copy.deepcopy(original);fast.__class__=CachedMiniBatchNMF
    np.testing.assert_allclose(fast.transform(x),original.transform(x),rtol=1e-6,atol=1e-7)
    fast.partial_fit(x);original.partial_fit(x)
    np.testing.assert_allclose(fast.components_,original.components_,rtol=1e-6,atol=1e-7)


def test_gpu_multiplicative_updates_match_cpu():
    cp=pytest.importorskip('cupy')
    try:
        cp.zeros(1)
    except Exception:
        pytest.skip('CUDA runtime unavailable')
    import copy
    from scipy import sparse
    from sklearn.decomposition import MiniBatchNMF
    sys.path.insert(0,str(SRC))
    from fast_nmf import GpuMiniBatchNMF
    rng=np.random.default_rng(29)
    x=sparse.csr_matrix(rng.random((60,40),dtype=np.float32)*(rng.random((60,40))>.7))
    x=x.astype(np.float32)
    model=MiniBatchNMF(n_components=8,init='random',random_state=17,transform_max_iter=60,forget_factor=1)
    model.partial_fit(x)
    gpu=copy.deepcopy(model);gpu.__class__=GpuMiniBatchNMF
    np.testing.assert_allclose(gpu.transform(x),model.transform(x),rtol=5e-4,atol=2e-6)
    model.partial_fit(x);gpu.partial_fit(x)
    np.testing.assert_allclose(gpu.components_,model.components_,rtol=5e-4,atol=2e-6)
