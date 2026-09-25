from merge_common import *
import argparse
import pandas as pd, pyarrow.parquet as pq
p=argparse.ArgumentParser();p.add_argument('clusters',nargs='+',type=int);p.add_argument('--chars',type=int,default=420);p.add_argument('--tag',required=True);a=p.parse_args()
t=pd.read_csv(RAW/'results/topics1000_with_comparison.csv').fillna('')
e=pq.read_table(RAW/'evidence/review_documents.parquet').to_pandas()
records=[];lines=[]
for i in a.clusters:
 r=t[t.cluster==i].iloc[0];v=e[e.cluster==i]
 dominant=max([('paper',r.papers),('patent',r.patents_2026),('policy',r.policies)],key=lambda p:p[1])[0]
 lines.append(f"T{i:04d} n={r.documents} papers={r.papers} patents={r.patents_2026} policies={r.policies} {r.keywords}")
 selected=[]
 for source in ['paper','patent','policy']:
  roles=['center:1','center:2','random:1','random:2','boundary:1'] if source==dominant else ['center:1']
  for role in roles:
   z=v[(v.source==source)&v.selection_roles.str.split('|').apply(lambda q:role in q)]
   if len(z):selected.append(int(z.iloc[0].row_id))
 for rid in dict.fromkeys(selected):
  q=v[v.row_id==rid].iloc[0];body=str(q.body)[:a.chars]
  item={k:(int(q[k]) if k in ['row_id','cluster'] else str(q[k])) for k in ['row_id','cluster','topic_id','source','title','selection_roles','body_sha256','source_part','doc_id']}
  item.update(body_excerpt=body,body_characters_shown=len(body),full_body_characters=len(str(q.body)),title_shown_in_full=True)
  records.append(item)
  lines.append(f"  row={rid} {q.source} {q.selection_roles} {q.title}\n    {body.replace(chr(10),' ')}")
 lines.append('')
dump(BASE/f'evidence/packet_{a.tag}.json',{'packet':a.tag,'created_utc':now(),'topics':a.clusters,'review_scope':'full titles and the recorded leading body excerpts; no independent experts or whole-corpus manual review','records':records})
text='\n'.join(lines);(BASE/f'evidence/packet_{a.tag}.txt').write_text(text+'\n');print(text)
