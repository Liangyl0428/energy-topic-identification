"""Read actual literature records together with new labels; original corpus stays read-only.

python3 src/read_refined.py --row-id 4006773 --output /tmp/document.json
Use iter_refined_parts() in Python for sequential access to all records.
"""
from refine_common import *
import argparse

def refined_part(part,include_body=True):
    columns=None if include_body else ['row_id','doc_id','source','date','title','url','retracted','usable']
    original=pq.read_table(OLD/part['file'],columns=columns).to_pandas()
    labels=pq.read_table(BASE/'results/assignments'/Path(part['file']).name).to_pandas()
    assert np.array_equal(original.row_id,labels.row_id)
    original=original.rename(columns={'title':'original_title','body':'original_body'})
    result=original.merge(labels,on='row_id',how='inner',validate='one_to_one',suffixes=('_source',''))
    if include_body:
        result['body']=result['original_body']
        f=BASE/'results/text_corrections'/Path(part['file']).name
        if f.exists():
            corr=pq.read_table(f).to_pandas().set_index('row_id')
            mask=result.row_id.isin(corr.index)
            result.loc[mask,'body']=result.loc[mask,'row_id'].map(corr.clean_body)
    return result

def iter_refined_parts(include_body=True):
    for p in read(OLD/'data/INPUT_MANIFEST.json')['parts']:yield refined_part(p,include_body)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--row-id',type=int,required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();parts=read(OLD/'data/INPUT_MANIFEST.json')['parts']
    p=next((p for p in parts if p['first_row']<=args.row_id<p['first_row']+p['n']),None)
    if p is None:raise ValueError('row_id outside corpus')
    df=refined_part(p);r=df.loc[df.row_id.eq(args.row_id)].iloc[0].to_dict()
    for k,v in r.items():
        if isinstance(v,float) and np.isnan(v):r[k]=None
    dump(Path(args.output),r);print(args.output)

if __name__=='__main__':main()
