from common import *
import sqlite3,shutil,collections
import pyarrow as pa,pyarrow.parquet as pq

manifest_path=BASE/'data/INPUT_MANIFEST.json';m=json.loads(manifest_path.read_text())
audit_path=BASE/'data/PATENT_ARCHIVE_ACCOUNTING.json';a=json.loads(audit_path.read_text())
assert not (BASE/'data/DATE_NORMALIZATION_FIX.json').exists()
backup=BASE/'data/before_date_normalization';backup.mkdir(exist_ok=True)
shutil.copyfile(manifest_path,backup/manifest_path.name);shutil.copyfile(audit_path,backup/audit_path.name)
shutil.copyfile(BASE/'data/patent_publication_ledger.parquet',backup/'patent_publication_ledger.parquet')
ledger=pq.read_table(BASE/'data/patent_publication_ledger.parquet').to_pylist()
existing={r['doc_id']:r['selected_publication'] for r in ledger}
db=sqlite3.connect('file:'+str(ROOT/'data/patent_v3/state.sqlite3')+'?mode=ro',uri=True)
new_rows=[];fixes=[]
for record in a['excluded_invalid_2026_date']:
    pub=record['pub'];raw=db.execute('SELECT summary,detail FROM records WHERE pub=?',(pub,)).fetchone()
    s=json.loads(raw[0]);d=json.loads(raw[1]) if raw[1] else {}
    date=normalize_date(d.get('publicationDate') or s.get('publicationDate'))
    assert date.startswith('2026-')
    app=clean(d.get('applicationNumber') or s.get('applicationNumber'));country=clean(d.get('countryCode') or s.get('countryCode'))
    key=country+':'+re.sub(r'[^A-Za-z0-9]','',app) if app else 'PUB:'+pub
    doc_id='patent26:'+digest(key)[:24]
    is_new=doc_id not in existing
    selected=existing.get(doc_id,pub)
    ledger.append({'publication_number':pub,'doc_id':doc_id,'date':date,'selected_publication':selected,'application':app,'country':country})
    if is_new:
        title=clean(d.get('zhName') or s.get('zhName') or d.get('enName') or s.get('enName'))
        body=clean(d.get('zhAbstract') or s.get('zhAbstract') or d.get('enAbstract') or s.get('enAbstract'))
        new_rows.append(dict(row_id=m['documents']+len(new_rows),doc_id=doc_id,source='patent',title=title,body=body,date=date,language='zh' if re.search(r'[\u4e00-\u9fff]',title+body) else '',url='https://patents.google.com/patent/'+pub,source_identifier=pub,title_only=not bool(body),retracted=False,template_record=False,usable=len(title+body)>=4 and any(x.isalpha() for x in title+body),publisher='',quality_note='application_dedup_within_country;not_international_family_dedup;normalized_YYYYMMDD_publication_date'))
        existing[doc_id]=pub
    fixes.append({'publication_number':pub,'original_date':record['publication_date'],'normalized_date':date,'new_document':is_new,'doc_id':doc_id})
db.close()
if new_rows:
    part=BASE/'data/corpus'/f'part-{len(m["parts"]):05d}.parquet'
    schema=pq.read_schema(BASE/m['parts'][0]['file'])
    pq.write_table(pa.Table.from_pylist(new_rows,schema=schema),part,compression='zstd')
    m['parts'].append({'file':str(part.relative_to(BASE)),'n':len(new_rows),'first_row':new_rows[0]['row_id'],'sha256':sha(part)})
    m['documents']+=len(new_rows);m['source_counts']['patent']+=len(new_rows);m['patent_application_documents']+=len(new_rows)
    for field in ['usable','title_only','retracted','template_record']:
        n=sum(x[field] for x in new_rows)
        if n:m['quality_counts']['patent:'+field]=m['quality_counts'].get('patent:'+field,0)+n
m['patent_publications']=len(ledger)
pq.write_table(pa.Table.from_pylist(ledger),BASE/'data/patent_publication_ledger.parquet',compression='zstd')
fix={'records':fixes,'new_document_count':len(new_rows),'normalized_publication_count':len(fixes),'created_utc':now(),'all_archive_publications_accounted':len(ledger)==a['archive_rows']}
assert fix['all_archive_publications_accounted']
m['publication_date_normalization']=fix
a['normalization_required_2026_dates']=a.pop('excluded_invalid_2026_date');a['excluded_invalid_2026_date']=[];a['normalization_completed']=True
dump(audit_path,a);dump(BASE/'data/DATE_NORMALIZATION_FIX.json',fix);dump(manifest_path,m)
print('DATE_NORMALIZATION_COMPLETE',len(fixes),len(new_rows),m['documents'],m['source_counts'],flush=True)
