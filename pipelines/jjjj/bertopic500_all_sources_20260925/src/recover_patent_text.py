from common import *
import sqlite3, shutil, collections, pyarrow as pa, pyarrow.parquet as pq

manifest_path = BASE/'data/INPUT_MANIFEST.json'
manifest = json.loads(manifest_path.read_text())
assert not (BASE/'data/PATENT_TEXT_RECOVERY.json').exists()
original = BASE/'data/before_claim_recovery'; original.mkdir(exist_ok=True)
shutil.copyfile(manifest_path, original/'INPUT_MANIFEST.json')
db = sqlite3.connect('file:'+str(ROOT/'data/patent_v3/state.sqlite3')+'?mode=ro',uri=True,timeout=30)
changes = []; candidates=0; changed_parts=[]

def extract(value):
    if isinstance(value,str): return clean(value)
    if isinstance(value,dict):
        for k in ['zhName','zhText','zhContent','enName','enText','enContent','text','content']:
            if value.get(k): return clean(value[k])
    return ''

for record in manifest['parts']:
    part=BASE/record['file']; table=pq.read_table(part)
    if table.column('source')[0].as_py()!='patent': continue
    assert not (BASE/'models/embeddings'/(part.stem+'.npy')).exists(), 'Patent embeddings already made; use a new version instead'
    rows=table.to_pylist(); altered=False
    for r in rows:
        if r['body']: continue
        candidates+=1
        raw=db.execute('SELECT detail FROM records WHERE pub=?',(r['source_identifier'],)).fetchone()
        d=json.loads(raw[0]) if raw and raw[0] else {}
        body='';basis=''
        claims=d.get('claims') or []
        if not isinstance(claims,list): claims=[claims]
        for claim in claims:
            t=extract(claim)
            if len(t)>=40:
                body=t;basis='first_available_claim';break
        if not body:
            desc=d.get('descriptions') or []
            if not isinstance(desc,list): desc=[desc]
            body='\n'.join(extract(x) for x in desc if extract(x))
            if len(body)>=40:basis='available_description'
            else:body=''
        if not body:continue
        r['body']=body;r['title_only']=False;r['usable']=len(r['title']+body)>=4 and any(x.isalpha() for x in r['title']+body)
        r['quality_note']+=';abstract_missing;body_from_'+basis
        changes.append({'row_id':r['row_id'],'doc_id':r['doc_id'],'publication_number':r['source_identifier'],'basis':basis,'characters':len(body),'title_was_empty':not bool(r['title'])})
        altered=True
    if altered:
        shutil.copyfile(part,original/part.name)
        tmp=part.with_suffix('.recovered.parquet');pq.write_table(pa.Table.from_pylist(rows,schema=table.schema),tmp,compression='zstd');tmp.replace(part)
        record['sha256']=sha(part);changed_parts.append(part.name)
    print('RECOVERY',part.stem,len(changes),flush=True)
db.close()
quality=collections.Counter()
for record in manifest['parts']:
    table=pq.read_table(BASE/record['file'],columns=['source','usable','title_only','retracted','template_record']).to_pydict()
    for source in set(table['source']):
        for key in ['usable','title_only','retracted','template_record']:
            n=sum(bool(v) for s,v in zip(table['source'],table[key]) if s==source)
            if n:quality[source+':'+key]+=n
manifest['quality_counts']=dict(quality)
audit={'candidates_missing_abstract':candidates,'recovered':len(changes),'recovered_title_also_missing':sum(x['title_was_empty'] for x in changes),'basis_counts':dict(collections.Counter(x['basis'] for x in changes)),'changed_parts':changed_parts,'created_utc':now(),'rule':'if abstract absent, use first available claim in full; if no claim, use available description; no fabricated title; original parts retained; all patent embeddings and lexical counts must use enriched inputs'}
manifest['patent_text_recovery']=audit
dump(BASE/'data/PATENT_TEXT_RECOVERY.json',audit)
pq.write_table(pa.Table.from_pylist(changes),BASE/'data/patent_text_recovery_ledger.parquet',compression='zstd')
dump(manifest_path,manifest)
print('RECOVERY_COMPLETE',audit,flush=True)
