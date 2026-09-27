"""Train on every nonempty full-corpus row, then use uniform fixed-H inference."""
from common import *
import sys
import time
import warnings
import argparse
import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.decomposition import MiniBatchNMF
from fast_nmf import GpuMiniBatchNMF
from threadpoolctl import threadpool_limits
sys.path.insert(0,str(REPO/'pipelines/keyword_nmf/src'))
from components import infer_contributions, hard_assign, ASSIGNMENT_METHOD


def train(epochs):
    if not (RUN/'PREPARE_COMPLETE.json').exists():
        raise RuntimeError('Full keyword preparation must finish first')
    ready=json.loads((RUN/'PREPARE_COMPLETE.json').read_text())
    configuration={'topics':K,'epochs':epochs,'batch_size':4096,'random_seed':17,'forget_factor':1.0,
        'fit_population':ready['nonzero_papers'],'vocabulary_sha256':sha(RUN/'vocabulary.csv'),
        'assignment':ASSIGNMENT_METHOD,'training':'MiniBatchNMF.partial_fit, each nonempty paper once per epoch; no early stop within epochs'}
    if (RUN/'TRAINING_COMPLETE.json').exists():
        if json.loads((RUN/'TRAINING_COMPLETE.json').read_text())['configuration']!=configuration:
            raise ValueError('Existing model configuration differs')
        return
    paths=sorted((RUN/'matrices').glob('part-*.npz'))
    state_path=RUN/'training_checkpoint.joblib'
    if state_path.exists():
        state=joblib.load(state_path)
        if state['configuration']!=configuration:
            raise ValueError('Checkpoint configuration differs')
        model=state['model']; resume_epoch=state['epoch']; resume_part=state['next_part']; seen=state['seen']
        # Equivalent algebra, including for checkpoints written by vanilla sklearn.
        model.__class__=GpuMiniBatchNMF
    else:
        model=GpuMiniBatchNMF(n_components=K,init='random',random_state=17,batch_size=4096,
            max_iter=1,max_no_improvement=None,tol=1e-4,forget_factor=1.0,fresh_restarts=False,
            transform_max_iter=200)
        resume_epoch=resume_part=seen=0
    history=[]
    start=time.time()
    for epoch in range(resume_epoch,epochs):
        order=np.random.default_rng(1700+epoch).permutation(len(paths))
        lo=resume_part if epoch==resume_epoch else 0
        for j in range(lo,len(order)):
            x=sparse.load_npz(paths[order[j]])
            valid=np.flatnonzero(x.getnnz(1)>0)
            np.random.default_rng(170000+epoch*1000+int(order[j])).shuffle(valid)
            for s in range(0,len(valid),4096):
                rows=valid[s:s+4096]
                model.partial_fit(x[rows]); seen+=len(rows)
            if j%10==0 or j+1==len(order):
                info={'configuration':configuration,'model':model,'epoch':epoch,'next_part':j+1,'seen':seen}
                tmp=state_path.with_suffix('.partial');joblib.dump(info,tmp);tmp.replace(state_path)
                dump(RUN/'TRAINING_PROGRESS.json',{'epoch':epoch+1,'epochs':epochs,'parts_done':j+1,'parts':len(order),'paper_visits':seen,'seconds_process':time.time()-start})
                print('TRAIN',epoch+1,j+1,'/',len(order),'visits',seen,flush=True)
        # A fixed small diagnostic sample, never a substitute for all-row training.
        diagnostic=sparse.load_npz(paths[0])[:1024]
        w=model.transform(diagnostic)
        h=model.components_
        sq=float(diagnostic.multiply(diagnostic).sum())
        cross=float(np.sum(w*(diagnostic@h.T)))
        recon=float(np.sum((w@(h@h.T))*w))
        relative=float(np.sqrt(max(0,sq-2*cross+recon)/max(sq,1e-12)))
        history.append({'epoch':epoch+1,'diagnostic_relative_error':relative,'paper_visits':seen})
        dump(RUN/f'epoch_{epoch+1:02d}.json',history[-1])
    if seen!=epochs*ready['nonzero_papers']:
        raise ValueError('Full training visits do not match population')
    joblib.dump(model,RUN/'selected_nmf.joblib',compress=1)
    np.save(RUN/'components.npy',model.components_)
    dump(RUN/'TRAINING_COMPLETE.json',{'configuration':configuration,'paper_visits':seen,
        'model_sha256':sha(RUN/'selected_nmf.joblib'),'convergence':'fixed full epochs; no claim of global optimum',
        'history':[json.loads(p.read_text()) for p in sorted(RUN.glob('epoch_*.json'))]})


def infer():
    model=joblib.load(RUN/'selected_nmf.joblib')
    out=RUN/'paper_assignments';out.mkdir(exist_ok=True)
    counts=np.zeros(K,np.int64)
    model_hash=sha(RUN/'selected_nmf.joblib')
    total=assigned=0
    for p in sorted((RUN/'matrices').glob('part-*.npz')):
        target=out/(p.stem+'.parquet'); audit=target.with_suffix('.json')
        ids=np.load(p.with_suffix('.rows.npy'))
        if target.exists() and audit.exists():
            if json.loads(audit.read_text())['model_sha256']!=model_hash:
                raise ValueError('Paper assignment cache belongs to another model')
            frame=pd.read_parquet(target)
        else:
            x=sparse.load_npz(p)
            labels=[]; tops=[]; margins=[]
            for s in range(0,len(ids),4096):
                w=infer_contributions(model,x[s:s+4096])
                labels.extend(hard_assign(w))
                mass=np.maximum(w.sum(1),1e-12); best=w.max(1)
                tops.extend(best/mass); margins.extend((best-np.partition(w,-2,axis=1)[:,-2])/mass)
            frame=pd.DataFrame({'row_id':ids,'topic_id':labels,'nmf_relative_top1':tops,'nmf_relative_margin':margins})
            frame['category_id']=[f'F{i+1:04d}' if i>=0 else '' for i in labels]
            frame['assignment_status']=np.where(frame.topic_id.ge(0),'keyword_nmf_assigned','missing_scored_in_vocabulary_keywords')
            frame.to_parquet(target,index=False)
            dump(audit,{'model_sha256':model_hash,'matrix_sha256':sha(p),'assignment_method':ASSIGNMENT_METHOD})
        good=frame.topic_id.ge(0)
        counts+=np.bincount(frame.topic_id[good].to_numpy(),minlength=K)
        total+=len(frame); assigned+=int(good.sum())
        print('INFER',p.stem,total,assigned,flush=True)
    vocab=pd.read_csv(RUN/'vocabulary.csv'); records=[]
    for k,h in enumerate(model.components_):
        top=np.argsort(-h,kind='stable')[:15]
        records.append({'topic_id':k,'category_id':f'F{k+1:04d}','name':' / '.join(vocab.display_name.iloc[top[:3]]),
            'top_keywords':' | '.join(vocab.display_name.iloc[top]),'paper_documents':int(counts[k]),'active':bool(counts[k]),
            'domain':'待主题范围审阅','status':'全量NMF关键词主题','analysis_scope':'待主题范围审阅'})
    pd.DataFrame(records).to_csv(RUN/'topic_catalog.csv',index=False)
    dump(RUN/'INFERENCE_COMPLETE.json',{'papers':total,'assigned_papers':assigned,'unassigned_papers':total-assigned,'active_topics':int((counts>0).sum()),'model_sha256':model_hash})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--epochs',type=int,default=5);args=p.parse_args()
    with threadpool_limits(4):
        train(args.epochs); infer()
