"""Exact textual marker census in seven suspected non-topic clusters.

Markers identify known text patterns, not automatic judgments of document value.
"""
from audit_metrics import *
import pyarrow as pa
import re
from collections import Counter

def main():
    ts=pd.read_csv(BASE/'results/final_topics.csv').set_index('final_topic_id')
    selected=[205,316,568,576,700,888,952]
    lut={int(ts.loc[f'S{i:04d}'].final_topic_index):f'S{i:04d}' for i in selected}
    y=np.load(BASE/'results/final_labels.npy',mmap_mode='r')
    counts={tid:Counter() for tid in lut.values()}
    bodies={tid:Counter() for tid in lut.values()}
    hits=[]
    for n,p in enumerate(read(CORPUS/'data/INPUT_MANIFEST.json')['parts']):
        sub=y[p['first_row']:p['first_row']+p['n']]
        take=np.flatnonzero(np.isin(sub,list(lut)))
        if not len(take):continue
        t=pq.read_table(CORPUS/p['file'],columns=['row_id','title','body','title_only','template_record'])
        for r in t.take(pa.array(take)).to_pylist():
            tid=lut[int(y[r['row_id']])]; c=counts[tid]
            title=r['title'] or ''; body=r['body'] or ''; b=body.lower()
            flags={
                'doi_only_title':bool(re.fullmatch(r'(?:https?://(?:dx\.)?doi\.org/)?10\.\d{4,9}/\S+',title.strip(),flags=re.I)),
                'sigma_publisher_template':'wydawnictwo sigma-not wydaje czasopisma fachowe' in b,
                'cheminform_template':'cheminform is a weekly abstracting service' in b,
                'editorial_title_marker':bool(re.search(r'graphical abstract|issue cover|cover picture|foreword|preface|nominations for|^editorial\b',title,re.I)),
                'empty_body':not body.strip(),
                'existing_template_flag':bool(r['template_record']),
                'title_only':bool(r['title_only']),
            }
            c['documents']+=1
            for k,v in flags.items():c[k]+=int(v)
            if body.strip():bodies[tid][body]+=1
            if any(flags[k] for k in ['doi_only_title','sigma_publisher_template','cheminform_template','editorial_title_marker']):
                hits.append(dict(row_id=r['row_id'],topic_id=tid,title=title,**flags))
        if (n+1)%50==0:print('quality census parts',n+1,flush=True)
    out=[]
    for tid,c in counts.items():
        assert c['documents']==int(ts.loc[tid].documents)
        common=bodies[tid].most_common(1)
        out.append(dict(topic_id=tid,**c,most_common_nonempty_body_count=common[0][1] if common else 0,
            most_common_nonempty_body_excerpt=common[0][0][:400] if common else ''))
    pd.DataFrame(out).to_csv(AUDIT/'results/quality_marker_census.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(hits).to_parquet(AUDIT/'results/quality_marker_records.parquet',index=False)
    dump(AUDIT/'results/QUALITY_CENSUS.json',dict(created_utc=now(),topics=out,records_with_markers=len(hits),
        note='Full-record census in these seven classes only. Exact patterns are diagnostic; no claim that all marked documents are invalid, and no changes to source labels.'))
    print(pd.DataFrame(out).drop(columns=['most_common_nonempty_body_excerpt']).to_string(index=False))

if __name__=='__main__':main()
