from merge_common import *
import numpy as np,pandas as pd,pyarrow.parquet as pq,pyarrow as pa
proposed=[[130,939],[142,177],[174,580],[264,864],[308,866],[393,498],[619,651],[772,785]]
y=np.load(RAW/'results/raw_labels.npy',mmap_mode='r')
old=set(pq.read_table(RAW/'evidence/review_documents.parquet',columns=['row_id'])['row_id'].to_pylist())
rng=np.random.default_rng(20260925);chosen={}
for i in sorted({i for g in proposed for i in g}):
 ids=np.flatnonzero(y==i);ids=ids[~np.isin(ids,np.array(sorted(old)))]
 for rid in rng.choice(ids,size=min(6,len(ids)),replace=False):chosen[int(rid)]=i
records=[]
for p in read(CORPUS/'data/INPUT_MANIFEST.json')['parts']:
 ids=[r for r in chosen if p['first_row']<=r<p['first_row']+p['n']]
 if not ids:continue
 t=pq.read_table(CORPUS/p['file'],columns=['row_id','doc_id','source','title','body','url','title_only','quality_note'])
 for r in t.take(pa.array([i-p['first_row'] for i in ids])).to_pylist():
  body=r.pop('body') or '';i=chosen[r['row_id']]
  r.update(cluster=i,topic_id=f'T{i:04d}',selection_roles='fresh_random:seed20260925',body_excerpt=body[:220],body_characters_shown=len(body[:220]),full_body_characters=len(body),body_sha256=hashlib.sha256(body.encode()).hexdigest(),source_part=p['file'],title_shown_in_full=True)
  records.append(r)
records.sort(key=lambda r:(r['cluster'],r['row_id']))
dump(BASE/'evidence/fresh_random_audit.json',{'created_utc':now(),'proposed_groups':proposed,'seed':20260925,'samples_per_raw_topic':6,'review_scope':'additional random sample excluding all existing saved review rows; titles and first220 body chars; no population accuracy estimate','records':records})
print('saved',len(records),'fresh sample records')
