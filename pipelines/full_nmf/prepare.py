"""Extract keywords from every frozen source and fit full-corpus TF-IDF."""
from common import *
import concurrent.futures
import time
import collections
import math

import duckdb
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.csv as ac
import pyarrow.parquet as pq
from scipy import sparse
from sklearn.preprocessing import normalize


def extract(row):
    source = Path(row['path'])
    key = hashlib.sha256(str(source).encode()).hexdigest()[:20]
    target = RUN / 'raw_keywords' / (key + '.parquet')
    audit = target.with_suffix('.json')
    stat = source.stat()
    if stat.st_size != row['bytes'] or stat.st_mtime_ns != row['mtime_ns']:
        raise ValueError('Frozen source changed: ' + str(source))
    if target.exists() and audit.exists():
        return json.loads(audit.read_text())
    fields = ['openalex_id', 'raw_keywords', 'keywords', 'raw_updated_date']
    reader = ac.open_csv(source,
        read_options=ac.ReadOptions(block_size=8*1024**2, use_threads=False),
        parse_options=ac.ParseOptions(newlines_in_values=True),
        convert_options=ac.ConvertOptions(include_columns=fields,
            include_missing_columns=True, column_types={x: pa.string() for x in fields},
            strings_can_be_null=False))
    tmp = target.with_suffix('.partial')
    writer = None
    count = 0
    try:
        for batch in reader:
            table = pa.Table.from_batches([batch])
            table = table.append_column('source_file', pa.array([str(source.relative_to(ROOT))]*len(table)))
            if writer is None:
                writer = pq.ParquetWriter(tmp, table.schema, compression='zstd')
            writer.write_table(table)
            count += len(table)
    finally:
        if writer is not None:
            writer.close()
    if writer is None:
        pq.write_table(pa.table({x: pa.array([], type=pa.string()) for x in fields+['source_file']}), tmp)
    tmp.replace(target)
    result = {'path': str(source), 'bytes': stat.st_size, 'mtime_ns': stat.st_mtime_ns, 'rows': count}
    dump(audit, result)
    return result


def parse_keywords(raw, flat):
    try:
        values = json.loads(raw) if raw else []
    except (ValueError, TypeError):
        values = []
    found = {}
    for v in values if isinstance(values, list) else []:
        if not isinstance(v, dict):
            continue
        name = str(v.get('display_name') or '').strip()
        if not name:
            continue
        key = str(v.get('id') or ('label:' + name.casefold()))
        score = v.get('score')
        score = float(score) if isinstance(score, (int, float)) and math.isfinite(score) and 0 <= score <= 1 else 0.0
        found[key] = (name, score)
    if not found and flat:
        for name in flat.split(';'):
            name = name.strip()
            if name:
                found['label:' + name.casefold()] = (name, 0.0)
    return found


def main():
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN/'raw_keywords').mkdir(exist_ok=True)
    (RUN/'keyword_parts').mkdir(exist_ok=True)
    (RUN/'matrices').mkdir(exist_ok=True)
    inventory = json.loads((ROOT/'aaaa/openalex_keywords_nmf/verified_sources.json').read_text())
    start = time.time()
    if not (RUN/'EXTRACTION_COMPLETE.json').exists():
        totals = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
            for i, result in enumerate(pool.map(extract, inventory), 1):
                totals.append(result)
                if i % 50 == 0:
                    print('EXTRACT', i, '/', len(inventory), 'seconds', round(time.time()-start), flush=True)
                    dump(RUN/'PREPARE_PROGRESS.json', {'stage':'extract', 'files':i, 'total_files':len(inventory)})
        dump(RUN/'EXTRACTION_COMPLETE.json', {'files':len(totals), 'raw_rows':sum(r['rows'] for r in totals), 'sources':totals})
    con = duckdb.connect(str(RUN/'keywords.duckdb'))
    con.execute("SET threads=4; SET memory_limit='8GB'")
    if not (RUN/'CANONICAL_COMPLETE.json').exists():
        con.execute(f"CREATE OR REPLACE TABLE paper_ids AS SELECT row_id, replace(doc_id,'paper:','') work_id FROM read_parquet('{CORPUS}/*.parquet') WHERE source='paper'")
        con.execute(f"""CREATE OR REPLACE TABLE chosen AS
          SELECT p.row_id, p.work_id, r.raw_keywords, r.keywords, r.raw_updated_date, r.source_file
          FROM read_parquet('{RUN}/raw_keywords/*.parquet') r
          JOIN paper_ids p ON regexp_extract(r.openalex_id, '(W[0-9]+)$', 1)=p.work_id
          QUALIFY row_number() OVER (PARTITION BY p.work_id ORDER BY
            (CASE WHEN json_valid(r.raw_keywords) THEN coalesce(json_array_length(r.raw_keywords),0)>0 ELSE false END OR length(coalesce(r.keywords,''))>0) DESC,
            coalesce(r.raw_updated_date,'') DESC, r.source_file, r.raw_keywords)=1""")
        count = con.sql('SELECT count(*) FROM chosen').fetchone()[0]
        dump(RUN/'CANONICAL_COMPLETE.json', {'matched_papers':count, 'selection':'valid keyword presence; latest update; lexicographic source and raw snapshot; no duplicate union'})
        print('CANONICAL', count, flush=True)
    if not (RUN/'VOCABULARY_COMPLETE.json').exists():
        frequencies = collections.Counter()
        names = {}
        n_papers = 0
        for p in parts():
            meta = pq.read_table(p, columns=['row_id','source']).to_pandas()
            ids = meta.loc[meta.source.eq('paper'),'row_id']
            if not len(ids):
                continue
            n_papers += len(ids)
            frame = con.sql(f'SELECT row_id,raw_keywords,keywords FROM chosen WHERE row_id BETWEEN {int(ids.min())} AND {int(ids.max())} ORDER BY row_id').df()
            records = []
            for row in frame.itertuples():
                terms = parse_keywords(row.raw_keywords, row.keywords)
                frequencies.update(terms.keys())
                for key,(name,score) in terms.items():
                    names.setdefault(key,name)
                    records.append((row.row_id,key,score))
            pd.DataFrame(records, columns=['row_id','keyword_id','score']).to_parquet(RUN/'keyword_parts'/p.name,index=False)
            if int(p.stem.split('-')[1]) % 10 == 0:
                print('VOCAB', p.stem, n_papers, len(frequencies), flush=True)
        keys = sorted(k for k,v in frequencies.items() if 10 <= v <= .5*n_papers)
        vocab = pd.DataFrame({'keyword_id':keys,'display_name':[names[k] for k in keys], 'document_frequency':[frequencies[k] for k in keys]})
        vocab['idf'] = np.log((1+n_papers)/(1+vocab.document_frequency)) + 1
        vocab.to_csv(RUN/'vocabulary.csv', index=False)
        dump(RUN/'VOCABULARY_COMPLETE.json', {'papers':n_papers,'vocabulary':len(keys),'min_df':10,'max_df_fraction':.5,'idf_fit':'all frozen papers, binary keyword presence','missing_score':'zero; not invented','source_vocabulary':len(frequencies)})
    vocab = pd.read_csv(RUN/'vocabulary.csv')
    lookup = pd.Series(np.arange(len(vocab)), index=vocab.keyword_id)
    stats = []
    for p in parts():
        output = RUN/'matrices'/(p.stem+'.npz')
        audit = output.with_suffix('.json')
        if output.exists() and audit.exists():
            stats.append(json.loads(audit.read_text()))
            continue
        meta = pq.read_table(p,columns=['row_id','source']).to_pandas()
        ids = meta.row_id[meta.source.eq('paper')].to_numpy()
        if not len(ids):
            continue
        values = pd.read_parquet(RUN/'keyword_parts'/p.name)
        cols = values.keyword_id.map(lookup)
        valid = cols.notna() & values.score.gt(0)
        rows = np.searchsorted(ids, values.row_id[valid].to_numpy())
        cs = cols[valid].to_numpy(dtype=np.int32)
        weights = values.score[valid].to_numpy(dtype=np.float32) * vocab.idf.to_numpy(dtype=np.float32)[cs]
        matrix = normalize(sparse.csr_matrix((weights,(rows,cs)),shape=(len(ids),len(vocab))),copy=False)
        sparse.save_npz(output,matrix)
        np.save(output.with_suffix('.rows.npy'),ids)
        result={'part':p.stem,'papers':len(ids),'nonzero_papers':int((matrix.getnnz(1)>0).sum()),'nnz':matrix.nnz}
        dump(audit,result); stats.append(result)
    dump(RUN/'PREPARE_COMPLETE.json',{'paper_count':sum(r['papers'] for r in stats),'nonzero_papers':sum(r['nonzero_papers'] for r in stats),'vocabulary':len(vocab),'parts':stats})
    print('PREPARE COMPLETE',flush=True)


if __name__=='__main__':
    main()
