"""Auditable semantic transfer of paper topic contributions to other sources.

This is a weighted nearest-paper projection, NOT a patent/policy NMF fit. The
paper reference and diagnostic cohorts are disjoint by record ID. Diagnostics
measure reproduction of paper NMF memberships, not semantic accuracy.
"""
from run import *
import pyarrow.parquet as pq
from sklearn.preprocessing import normalize

OLD = ROOT / 'work/nmf_keyword_control_20261019'
DIR = OUT / 'transfer'
DIR.mkdir(exist_ok=True)
NEIGHBORS = [5, 10, 20]
TEMPERATURE = .05
SIMILARITY_GATE = .55


def prepare_reference_text():
    if (DIR/'REFERENCE_TEXT_COMPLETE.json').exists():
        return
    ids = np.load(OLD/'train_row_ids.npy')
    assert len(ids) == 200000 and len(np.intersect1d(ids, np.load(OLD/'test_row_ids.npy'))) == 0
    embedding = np.lib.format.open_memmap(DIR/'reference_embeddings.npy', mode='w+', dtype='float32', shape=(len(ids), 1024))
    frames = []
    for i, f in enumerate(sorted(CORPUS.glob('part-*.parquet'))):
        meta = pd.read_parquet(f, columns=['row_id','doc_id','title','body','date','source','title_only','usable','retracted','template_record','url'])
        select = meta.row_id.isin(ids).to_numpy()
        if not select.any():
            continue
        selected = meta[select].copy()
        pos = np.searchsorted(ids, selected.row_id)
        assert np.array_equal(ids[pos], selected.row_id)
        e = np.load(FROZEN/'embeddings'/(f.stem+'.npy'), mmap_mode='r')
        embedding[pos] = e[select]
        selected['body_excerpt'] = selected.body.fillna('').str[:2000]
        frames.append(selected.drop(columns='body'))
        if i % 50 == 0:
            print('REFERENCE_TEXT', i, flush=True)
    embedding.flush()
    meta = pd.concat(frames).sort_values('row_id').reset_index(drop=True)
    assert np.array_equal(meta.row_id, ids)
    meta.to_parquet(DIR/'reference_metadata.parquet', index=False)
    write(DIR/'REFERENCE_TEXT_COMPLETE.json', {'records':len(meta), 'overlap_with_diagnostics':0})


def reference_contributions():
    if (DIR/'REFERENCE_COMPLETE.json').exists():
        return
    model = joblib.load(OUT/'full_model/model.joblib')
    mask = np.load(OUT/'broad_mask.npy')
    p = base.infer(model, base.clean(sparse.load_npz(OLD/'train.npz'), mask))
    truth = base.infer(model, base.clean(sparse.load_npz(OLD/'heldout.npz'), mask))
    meta = pd.read_parquet(DIR/'reference_metadata.parquet')
    emb = np.load(DIR/'reference_embeddings.npy', mmap_mode='r')
    valid = (p.sum(1)>0) & (np.linalg.norm(emb,axis=1)>0) & meta.usable.to_numpy() & ~meta.retracted.to_numpy() & ~meta.template_record.to_numpy()
    np.save(DIR/'reference_contributions.npy',p)
    np.save(DIR/'reference_valid.npy',valid)
    np.save(DIR/'diagnostic_nmf_contributions.npy',truth)
    write(DIR/'REFERENCE_COMPLETE.json',{'reference_records':int(valid.sum()),'reference_pool':len(meta),
        'diagnostic_records':len(truth),'contribution_model_sha256':sha(OUT/'full_model/components.npy'),
        'diagnostic_boundary':'The full NMF model saw these papers. Only semantic neighbor transfer is evaluated on disjoint references; this is not an unseen NMF test.'})


class NeighborProjector:
    def __init__(self):
        import cupy as cp
        self.cp = cp
        self.positions = np.flatnonzero(np.load(DIR/'reference_valid.npy'))
        emb = np.load(DIR/'reference_embeddings.npy',mmap_mode='r')
        self.emb = cp.asarray(normalize(np.asarray(emb[self.positions]),copy=True))
        self.p = np.load(DIR/'reference_contributions.npy',mmap_mode='r')

    def nearest(self, query):
        cp = self.cp
        query = normalize(np.asarray(query,dtype='float32'),copy=True)
        idx, vals = [], []
        for lo in range(0,len(query),256):
            sim = cp.asarray(query[lo:lo+256]) @ self.emb.T
            pick = cp.argpartition(-sim,19,axis=1)[:,:20]
            score = cp.take_along_axis(sim,pick,axis=1)
            order = cp.argsort(-score,axis=1)
            pick = cp.take_along_axis(pick,order,axis=1)
            score = cp.take_along_axis(score,order,axis=1)
            idx.append(self.positions[cp.asnumpy(pick)])
            vals.append(cp.asnumpy(score))
        return np.concatenate(idx), np.concatenate(vals)

    def contributions(self, idx, sim, neighbors):
        weight = np.exp((sim[:,:neighbors]-sim[:,[0]])/TEMPERATURE)
        weight /= weight.sum(1,keepdims=True)
        p = np.zeros((len(idx), K),dtype='float32')
        for lo in range(0,len(idx),1024):
            p[lo:lo+1024] = np.einsum('ij,ijk->ik',weight[lo:lo+1024],self.p[idx[lo:lo+1024,:neighbors]])
        assert np.isfinite(p).all() and np.allclose(p.sum(1),1,atol=2e-5)
        return p


def diagnose(projector):
    if (DIR/'TRANSFER_SELECTION.json').exists():
        return base.read(DIR/'TRANSFER_SELECTION.json')
    e = np.load(OLD/'heldout_embeddings.npy',mmap_mode='r')
    truth = np.load(DIR/'diagnostic_nmf_contributions.npy',mmap_mode='r')
    valid = (truth.sum(1)>0) & (np.linalg.norm(e,axis=1)>0)
    # Fixed hash split: first half selects neighbor count, second half reports it.
    population = np.flatnonzero(valid)
    rng = np.random.default_rng(2026101909)
    rng.shuffle(population)
    ids = population[:20000]
    idx, sim = projector.nearest(e[ids])
    np.save(DIR/'diagnostic_row_positions.npy',ids)
    np.save(DIR/'diagnostic_neighbor_positions.npy',idx)
    np.save(DIR/'diagnostic_neighbor_cosines.npy',sim)
    rows = []
    for n in NEIGHBORS:
        predicted = projector.contributions(idx,sim,n)
        for split, positions in [('selection',np.arange(10000)),('confirmation',np.arange(10000,len(ids)))]:
            for gate in [.0,.45,.50,.55,.60,.65]:
                chosen = positions[sim[positions,0]>=gate]
                for threshold in [.05,.10,.15]:
                    actual = truth[ids[chosen]]>=threshold
                    pred = predicted[chosen]>=threshold
                    tp = int((actual&pred).sum()); fp=int((~actual&pred).sum()); fn=int((actual&~pred).sum())
                    precision=tp/max(tp+fp,1); recall=tp/max(tp+fn,1)
                    rows.append({'neighbors':n,'split':split,'similarity_gate':gate,'threshold':threshold,
                        'records':len(chosen),'coverage':len(chosen)/len(positions),
                        'membership_precision_against_nmf':precision,'membership_recall_against_nmf':recall,
                        'membership_f1_against_nmf':2*tp/max(2*tp+fp+fn,1),
                        'top1_agreement_against_nmf':float((predicted[chosen].argmax(1)==truth[ids[chosen]].argmax(1)).mean()) if len(chosen) else None})
    table=pd.DataFrame(rows);table.to_csv(DIR/'projection_diagnostics.csv',index=False)
    candidates=table[(table.split=='selection')&(table.similarity_gate==SIMILARITY_GATE)&(table.threshold==.10)]
    winner=candidates.sort_values(['membership_f1_against_nmf','neighbors'],ascending=[False,True]).iloc[0]
    decision={'neighbors':int(winner.neighbors),'temperature':TEMPERATURE,'similarity_gate':SIMILARITY_GATE,
        'similarity_gate_status':'Provisional conservative support gate, not calibrated semantic precision.',
        'neighbor_selection':'Highest membership F1 vs NMF on the first 10000 disjoint-reference paper diagnostics, threshold .10 and gate .55. Other 10000 reported separately.',
        'source_semantics':'Semantic transfer of paper NMF contributions; not direct NMF inference or probability.',
        'all_patent_policy_assignments_require_semantic_review':True,
        'uncovered_directions':'Topics absent from the paper model cannot be discovered by transfer; keep abstained and scope-review records for later discovery.'}
    write(DIR/'TRANSFER_SELECTION.json',decision)
    return decision


def export_transfer(projector, selection):
    if (DIR/'EXPORT_COMPLETE.json').exists():
        return
    assign=DIR/'assignments';edges=DIR/'contribution_edges_ge_005'
    assign.mkdir(exist_ok=True);edges.mkdir(exist_ok=True)
    sums=[];sens=[];review=[]
    reference=pd.read_parquet(DIR/'reference_metadata.parquet')
    for f in sorted(CORPUS.glob('part-*.parquet')):
        meta=pd.read_parquet(f)
        rows=np.flatnonzero(meta.source.ne('paper').to_numpy())
        if not len(rows):continue
        em=np.load(FROZEN/'embeddings'/(f.stem+'.npy'),mmap_mode='r')
        m=meta.iloc[rows].reset_index(drop=True)
        usable=(np.linalg.norm(em[rows],axis=1)>0)&m.usable.to_numpy()&~m.template_record.to_numpy()&~m.retracted.to_numpy()
        q=np.zeros((len(m),K),np.float32);best_sim=np.zeros(len(m),np.float32)
        ref_ids=[[] for _ in range(len(m))];ref_sims=[[] for _ in range(len(m))]
        if usable.any():
            idx, sim=projector.nearest(em[rows[usable]])
            q[usable]=projector.contributions(idx,sim,selection['neighbors'])
            best_sim[usable]=sim[:,0]
            for j,loc in enumerate(np.flatnonzero(usable)):
                ref_ids[loc]=reference.doc_id.iloc[idx[j,:selection['neighbors']]].tolist()
                ref_sims[loc]=sim[j,:selection['neighbors']].astype(float).tolist()
        qualified=usable&(best_sim>=selection['similarity_gate'])
        accepted=(q>=.10)&qualified[:,None];n=accepted.sum(1)
        ids_list=[];contrib_list=[]
        for j in range(len(m)):
            c=np.flatnonzero(accepted[j]);c=c[np.argsort(-q[j,c],kind='stable')]
            ids_list.append(c.astype(int).tolist());contrib_list.append(q[j,c].astype(float).tolist())
        out=m[['row_id','doc_id','source','title','date','title_only','usable','retracted','template_record']].copy()
        out['topic_ids']=ids_list;out['topic_contributions']=contrib_list;out['topic_count']=n
        out['nearest_paper_cosine']=best_sim;out['quality_gate_pass']=qualified
        out['neighbor_doc_ids']=ref_ids;out['neighbor_cosines']=ref_sims
        out['score_kind']='semantic_neighbor_transfer_contribution'
        out['assignment_status']=np.where(~usable,'unusable_text',np.where(~qualified,'below_similarity_gate',np.where(n==0,'below_contribution_threshold','assigned_candidate')))
        out['requires_semantic_review']=True
        out.to_parquet(assign/f.name,index=False)
        rr,cc=np.nonzero(q>=.05)
        pd.DataFrame({'row_id':m.row_id.to_numpy()[rr],'topic_id':cc.astype('int32'),'relative_contribution':q[rr,cc],
            'quality_gate_pass':qualified[rr],'nearest_paper_cosine':best_sim[rr]}).to_parquet(edges/f.name,index=False)
        for source,g in m.groupby('source'):
            ix=g.index.to_numpy()
            sums.append({'source':source,'records':len(ix),'usable':int(usable[ix].sum()),'gate_pass':int(qualified[ix].sum()),
                'assigned':int((n[ix]>0).sum()),'multilabel':int((n[ix]>1).sum()),'edges_default':int(n[ix].sum())})
            for t in [.05,.10,.15]:
                counts=((q[ix]>=t)&qualified[ix,None]).sum(1)
                sens.append({'source':source,'threshold':t,'records':len(ix),'assigned':int((counts>0).sum()),
                    'multilabel':int((counts>1).sum()),'edges':int(counts.sum()),'gate_pass':int(qualified[ix].sum())})
            # Preserve both supported and abstained examples for actual content inspection.
            for status in out.assignment_status.unique():
                eligible=out.index[(out.source==source)&(out.assignment_status==status)]
                for j in np.random.default_rng(20261019).choice(eligible,size=min(6,len(eligible)),replace=False):
                    row=out.iloc[j].to_dict();row['body_excerpt']=str(m.body.iloc[j] or '')[:2000]
                    review.append(row)
        print('TRANSFER',f.stem,'records',len(m),'qualified',int(qualified.sum()),flush=True)
    pd.DataFrame(sums).groupby('source',as_index=False).sum().to_csv(DIR/'coverage.csv',index=False)
    pd.DataFrame(sens).groupby(['source','threshold'],as_index=False).sum().to_csv(DIR/'threshold_sensitivity.csv',index=False)
    pd.DataFrame(review).to_parquet(DIR/'review_samples.parquet',index=False)
    write(DIR/'EXPORT_COMPLETE.json',{'completed_at':base.stamp(),'records':int(pd.DataFrame(sums).records.sum()),
        'sources':['patent','policy'],'selection':selection,'raw_transfer_edges_preserved_even_if_gate_fails':True})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','run']);args=parser.parse_args()
    with threadpool_limits(limits=4):
        prepare_reference_text()
        if args.stage=='run':
            reference_contributions()
            projector=NeighborProjector()
            selected=diagnose(projector)
            export_transfer(projector,selected)


if __name__=='__main__':main()
