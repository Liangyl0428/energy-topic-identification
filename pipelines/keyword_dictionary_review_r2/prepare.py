from common import *

def main():
    if (WORK/'PREPARED.json').exists():
        print((WORK/'PREPARED.json').read_text());return
    c=connect()
    source_path=str(FROZEN/'keywords.duckdb').replace("'","''")
    c.execute(f"ATTACH '{source_path}' AS original (READ_ONLY)")
    print('Reading all unfiltered keyword observations',flush=True)
    c.execute('CREATE TABLE IF NOT EXISTS observations AS SELECT row_id,keyword_id,score FROM read_parquet(?)',[str(FROZEN/'keyword_parts/*.parquet')])
    print('Extracting original display names from source keyword JSON',flush=True)
    c.execute('CREATE TABLE IF NOT EXISTS alias_fragments (batch_id INTEGER,keyword_id VARCHAR,raw_name VARCHAR,occurrences BIGINT)')
    c.execute('CREATE TABLE IF NOT EXISTS alias_progress (batch_id INTEGER)')
    done={r[0] for r in c.execute('SELECT batch_id FROM alias_progress').fetchall()}
    for batch,lo in enumerate(range(0,4831088,100000)):
        if batch in done:continue
        c.execute('BEGIN TRANSACTION')
        c.execute("""INSERT INTO alias_fragments
            SELECT ?,coalesce(nullif(json_extract_string(j.value,'$.id'),''),
                   'label:'||lower(trim(json_extract_string(j.value,'$.display_name')))) keyword_id,
                   trim(json_extract_string(j.value,'$.display_name')) raw_name,count(*) occurrences
            FROM (SELECT raw_keywords FROM original.chosen WHERE row_id>=? AND row_id<?) d,
                 json_each(CASE WHEN json_valid(d.raw_keywords)
                 AND json_type(d.raw_keywords)='ARRAY' THEN d.raw_keywords ELSE '[]' END) j
            WHERE json_type(j.value)='OBJECT' AND length(trim(coalesce(json_extract_string(j.value,'$.display_name'),'')))>0
            GROUP BY ALL""",[batch,lo,lo+100000])
        c.execute('INSERT INTO alias_progress VALUES (?)',[batch]);c.execute('COMMIT')
        print('ALIASES',batch+1,'/49',flush=True)
    c.execute('CREATE OR REPLACE TABLE raw_aliases AS SELECT keyword_id,raw_name,sum(occurrences)::BIGINT occurrences FROM alias_fragments GROUP BY ALL')
    aliases=c.execute('select * from raw_aliases order by keyword_id,occurrences desc,raw_name').df()
    names=aliases.drop_duplicates('keyword_id')[['keyword_id','raw_name']]
    freq=c.execute('SELECT keyword_id,count(DISTINCT row_id) document_frequency,count(*) observations FROM observations GROUP BY keyword_id ORDER BY document_frequency DESC,keyword_id').df()
    vocab=freq.merge(names,on='keyword_id',how='left',validate='one_to_one')
    fallback=vocab.raw_name.isna() & vocab.keyword_id.str.startswith('label:')
    vocab.loc[fallback,'raw_name']=vocab.loc[fallback,'keyword_id'].str.removeprefix('label:')
    assert vocab.raw_name.notna().all(),vocab[vocab.raw_name.isna()]
    vocab['normalized_name']=vocab.raw_name.map(normalize)
    aliases['normalized_name']=aliases.raw_name.map(normalize)
    vocab.to_csv(WORK/'all_raw_keywords.csv',index=False,encoding='utf-8-sig')
    aliases.to_parquet(WORK/'raw_name_aliases.parquet',index=False)
    c.register('vocab_frame',vocab)
    c.execute('CREATE OR REPLACE TABLE raw_vocabulary AS SELECT * FROM vocab_frame')
    c.execute('''CREATE OR REPLACE TABLE papers AS SELECT row_id,doc_id,date,language,title_only,
        retracted,template_record,usable FROM read_parquet(?) WHERE source='paper' ''',[str(CORPUS/'*.parquet')])
    counts=c.execute('SELECT count(*),count(DISTINCT row_id),count(DISTINCT doc_id) FROM papers').fetchone()
    assert counts==(4831088,4831088,4831088),counts
    orphan=c.execute('SELECT count(*) FROM observations ANTI JOIN papers USING(row_id)').fetchone()[0]
    dup=c.execute('SELECT count(*) FROM (SELECT row_id,keyword_id,count(*) n FROM observations GROUP BY ALL HAVING n>1)').fetchone()[0]
    assert orphan==0 and dup==0,(orphan,dup)
    summary={'papers':counts[0],'raw_keyword_ids':len(vocab),'normalized_names':int(vocab.normalized_name.nunique()),
        'observations':int(freq.observations.sum()),'papers_with_keywords':c.execute('select count(distinct row_id) from observations').fetchone()[0],
        'source_paths':['data/article','data/preprints'],'source_selection':'Reuse canonical raw-keyword snapshot for each frozen paper: valid presence, latest update, deterministic tie break. No union of obsolete duplicate versions.',
        'unfiltered':True,'no_minimum_document_frequency':True,'keyword_score_not_a_membership_threshold':True,
        'all_raw_keywords_sha256':sha(WORK/'all_raw_keywords.csv'),'raw_keyword_selection_manifest_sha256':sha(FROZEN/'CANONICAL_COMPLETE.json'),
        'input_extraction_manifest_sha256':sha(FROZEN/'EXTRACTION_COMPLETE.json'),
        'source_dictionary_status':'All observed keyword IDs retained, including low-frequency and zero-score/fallback observations. No keyword inferred from a title at this stage.',
        'identity_checks':{'complete_unique_papers':True,'no_orphan_keywords':True,'no_duplicate_document_keyword':True}}
    write(WORK/'PREPARED.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
