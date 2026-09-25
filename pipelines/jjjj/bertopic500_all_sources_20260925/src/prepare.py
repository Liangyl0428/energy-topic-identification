"""Freeze all available texts, retaining identity/quality ledgers and acquisition dates."""
from common import *
import collections, zipfile, sqlite3, time, shutil
import duckdb, pyarrow as pa, pyarrow.parquet as pq

started = now()
OUT = BASE / 'data'
PARTS = OUT / 'corpus'
PARTS.mkdir(exist_ok=True)
assert not (OUT / 'INPUT_MANIFEST.json').exists(), 'Already frozen; do not overwrite'
manifest = {'created_utc': started, 'scope': 'all cached literature, all policy texts, all locally available 2026 patent publications', 'parts': [], 'source_counts': {}, 'quality_counts': {}, 'date_ranges': {}}
prov = json.loads((ROOT / 'aaaa/openalex_keywords_nmf/verified_sources.json').read_text())
changed = []
for z in prov:
    p = Path(z['path']); st = p.stat()
    if st.st_size != z['bytes'] or st.st_mtime_ns != z['mtime_ns']:
        changed.append(str(p))
assert not changed, f'Invalid literature cache: {changed[:5]}'
manifest['literature_cache'] = {'source_files': len(prov), 'source_list_sha256': sha(ROOT / 'aaaa/openalex_keywords_nmf/verified_sources.json'), 'cache_manifest': json.loads((ROOT / 'analyze/data/manifest.json').read_text()), 'no_language_or_date_filter': True}

schema = pa.schema([
    ('row_id', pa.int64()), ('doc_id', pa.string()), ('source', pa.string()),
    ('title', pa.string()), ('body', pa.string()), ('date', pa.string()),
    ('language', pa.string()), ('url', pa.string()), ('source_identifier', pa.string()),
    ('title_only', pa.bool_()), ('retracted', pa.bool_()), ('template_record', pa.bool_()),
    ('usable', pa.bool_()), ('publisher', pa.string()), ('quality_note', pa.string())
])
offset = 0
partno = 0
counts = collections.Counter()
quality = collections.Counter()
dates = collections.defaultdict(list)

def emit(rows):
    global offset, partno
    for r in rows:
        r['row_id'] = offset; offset += 1
        r['usable'] = len(r['title'] + r['body']) >= 4 and any(ch.isalpha() for ch in r['title'] + r['body'])
        counts[r['source']] += 1
        for key in ['usable', 'title_only', 'retracted', 'template_record']:
            if r[key]: quality[r['source'] + ':' + key] += 1
        if r['date']: dates[r['source']].append(r['date'])
    path = PARTS / f'part-{partno:05d}.parquet'
    tmp = path.with_suffix('.partial.parquet')
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), tmp, compression='zstd')
    tmp.replace(path)
    manifest['parts'].append({'file': str(path.relative_to(BASE)), 'n': len(rows), 'first_row': rows[0]['row_id'], 'sha256': sha(path)})
    partno += 1

conn = duckdb.connect(str(ROOT / 'analyze/data/independent_corpus.duckdb'), read_only=True)
conn.execute('SET threads=4'); conn.execute("SET memory_limit='5GB'")
sql = """SELECT work_id,coalesce(clean_title,'') title,coalesce(clean_abstract,'') body,
cast(model_date as varchar) date,coalesce(language,'') AS "language",coalesce(doi,'') doi,
coalesce(is_retracted,false) retracted,coalesce(template_record,false) template_record,
coalesce(title_only,true) title_only FROM works"""
for batch in conn.execute(sql).fetch_record_batch(20000):
    rows = []
    for r in batch.to_pylist():
        rows.append(dict(doc_id='paper:' + r['work_id'], source='paper', title=r['title'], body=r['body'], date=r['date'] or '', language=r['language'], url=r['doi'] or 'https://openalex.org/' + r['work_id'], source_identifier=r['work_id'], title_only=r['title_only'], retracted=r['retracted'], template_record=r['template_record'], publisher='', quality_note=''))
    emit(rows)
    if offset % 200000 == 0: print('PAPERS', offset, now(), flush=True)
conn.close()
print('PAPERS_DONE', offset, flush=True)

# Read the immutable archive and then check rows added since its capture. Short
# SQLite transactions avoid retaining WAL pages needed by the live collector.
archive_root = ROOT / 'data/patent_v3/exports_2026'
pm = json.loads((archive_root / 'manifest.json').read_text())
manifest['patent_archive'] = pm
pubs = {}
patent_raw = 0

def patent_record(raw, origin):
    global patent_raw
    s = raw.get('summary') or {}; d = raw.get('detail') or {}
    if isinstance(s, str): s = json.loads(s)
    if isinstance(d, str): d = json.loads(d)
    date = normalize_date(d.get('publicationDate') or s.get('publicationDate'))
    if not date.startswith('2026-'): return
    pub = raw['pub']; patent_raw += 1
    title = clean(d.get('zhName') or s.get('zhName') or d.get('enName') or s.get('enName'))
    body = clean(d.get('zhAbstract') or s.get('zhAbstract') or d.get('enAbstract') or s.get('enAbstract'))
    app = clean(d.get('applicationNumber') or s.get('applicationNumber'))
    country = clean(d.get('countryCode') or s.get('countryCode'))
    key = country + ':' + re.sub(r'[^A-Za-z0-9]', '', app) if app else 'PUB:' + pub
    pubs[pub] = dict(pub=pub, key=key, title=title, body=body, date=date, origin=origin, country=country, application=app)

for p in pm['parts']:
    path = archive_root / p['file']
    assert sha(path) == p['sha256'], f'Changed archive {path}'
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.endswith('.jsonl'): continue
            with z.open(name) as stream:
                for line in stream:
                    patent_record(json.loads(line), p['file'])
    print('PATENT_ARCHIVE', p['file'], len(pubs), flush=True)

db = sqlite3.connect('file:' + str(ROOT / 'data/patent_v3/state.sqlite3') + '?mode=ro', uri=True, timeout=30)
maxrow = db.execute('SELECT max(rowid) FROM records').fetchone()[0]
cutoff = pm['snapshot_started_at_utc']
# Inserts are timestamped by the collector; verify monotonicity at regularly
# spaced points before binary search for the beginning of the new-record tail.
probes = sorted(set([1, maxrow] + [int(maxrow * i / 64) for i in range(1, 64)]))
observed = []
for rid in probes:
    rec = db.execute('SELECT rowid,created_at FROM records WHERE rowid>=? ORDER BY rowid LIMIT 1', (rid,)).fetchone()
    if rec: observed.append(rec)
assert all(a[1] <= b[1] for a, b in zip(observed, observed[1:])), 'Creation timestamps not monotone; full delta scan needed'
lo, hi = 1, maxrow + 1
while lo < hi:
    mid = (lo + hi) // 2
    rec = db.execute('SELECT rowid,created_at FROM records WHERE rowid>=? ORDER BY rowid LIMIT 1', (mid,)).fetchone()
    if rec is None or rec[1] >= cutoff: hi = mid
    else: lo = rec[0] + 1
first = max(1, lo - 10000)  # overlap covers snapshot scan races and small timestamp irregularities
scanned = 0; delta_n = 0
for begin in range(first, maxrow + 1, 2000):
    batch = db.execute('SELECT pub,summary,detail,detail_status,created_at FROM records WHERE rowid BETWEEN ? AND ?', (begin, min(begin + 1999, maxrow))).fetchall()
    for pub, summary, detail, status, created in batch:
        scanned += 1
        before = len(pubs)
        patent_record(dict(pub=pub, summary=summary, detail=detail, detail_status=status), 'live_delta')
        delta_n += len(pubs) - before
    if scanned % 50000 == 0: print('PATENT_DELTA', scanned, delta_n, flush=True)
# Refresh every archived 2026 record through primary-key lookups. This also
# captures detail improvements and corrected dates without scanning all years.
known = list(pubs)
refreshed = 0; corrected_outside_year = []
for i in range(0, len(known), 500):
    keys = known[i:i+500]
    query = 'SELECT pub,summary,detail,detail_status FROM records WHERE pub IN (' + ','.join('?' for _ in keys) + ')'
    for pub, summary, detail, status in db.execute(query, keys).fetchall():
        s = json.loads(summary); d = json.loads(detail) if detail else {}
        date = normalize_date(d.get('publicationDate') or s.get('publicationDate'))
        if not date.startswith('2026-'):
            corrected_outside_year.append(pub); pubs.pop(pub, None)
        else:
            patent_record(dict(pub=pub, summary=s, detail=d, detail_status=status), 'live_refresh')
        refreshed += 1
    if i % 50000 == 0: print('PATENT_REFRESH', i, flush=True)
db.close()
manifest['patent_live_check'] = {'at_utc': now(), 'snapshot_max_rowid': maxrow, 'delta_start_rowid': first, 'timestamp_monotonic_probes': len(observed), 'delta_scanned': scanned, 'new_2026_publications': delta_n, 'archived_publications_refreshed': refreshed, 'corrected_outside_2026': corrected_outside_year, 'limitation': 'All archived 2026 publications refreshed; new rows through frozen max_rowid checked. Older non-2026 records with subsequently corrected year are not globally rescanned.'}

groups = collections.defaultdict(list)
for rec in pubs.values(): groups[rec['key']].append(rec)
patent_ledger = []
rows = []
for key in sorted(groups):
    group = groups[key]
    best = min(group, key=lambda r: (-len(r['body']), r['date'], r['pub']))
    docid = 'patent26:' + digest(key)[:24]
    for r in group:
        patent_ledger.append({'publication_number': r['pub'], 'doc_id': docid, 'date': r['date'], 'selected_publication': best['pub'], 'application': r['application'], 'country': r['country']})
    rows.append(dict(doc_id=docid, source='patent', title=best['title'], body=best['body'], date=best['date'], language='zh' if re.search(r'[\u4e00-\u9fff]', best['title'] + best['body']) else '', url='https://patents.google.com/patent/' + best['pub'], source_identifier=best['pub'], title_only=not bool(best['body']), retracted=False, template_record=False, publisher='', quality_note='application_dedup_within_country;not_international_family_dedup'))
    if len(rows) == 20000: emit(rows); rows = []
if rows: emit(rows)
pq.write_table(pa.Table.from_pylist(patent_ledger), OUT / 'patent_publication_ledger.parquet', compression='zstd')
manifest['patent_publications'] = len(pubs)
manifest['patent_application_documents'] = len(groups)
del groups, pubs, patent_ledger

policy_source = ROOT / 'data/policy/政策全文.jsonl'
policy_copy = OUT / 'policies_raw_snapshot.jsonl'
shutil.copyfile(policy_source, policy_copy)
policies = collections.defaultdict(list)
raw_policy = []
for line_number, line in enumerate(policy_copy.open(), 1):
    r = json.loads(line)
    title = clean(r.get('title')); body = clean(r.get('text'))
    publisher = clean(r.get('publisher')); date = clean(r.get('publication_date') or r.get('issue_date'))[:10]
    url = clean(r.get('url')); number = clean(r.get('document_number'))
    if url: key = 'url:' + url.split('#')[0]
    elif number and publisher: key = 'document:' + number + '|' + publisher
    else: key = 'metadata:' + title + '|' + date + '|' + publisher + '|' + digest(body)
    raw_policy.append({'raw_line': line_number, 'doc_id': 'policy:' + digest(key)[:24], 'title': title, 'date': date})
    policies[key].append(dict(title=title, body=body, date=date, publisher=publisher, url=url, number=number))
rows = []
for key in sorted(policies):
    best = max(policies[key], key=lambda r: len(r['body']))
    routine = bool(re.search(r'许可公告|电力业务许可|许可证注销|承装.*许可|资质许可|行政许可决定|行政许可结果', best['title']))
    rows.append(dict(doc_id='policy:' + digest(key)[:24], source='policy', title=best['title'], body=best['body'], date=best['date'], language='zh', url=best['url'], source_identifier=best['number'], title_only=not bool(best['body']), retracted=False, template_record=False, publisher=best['publisher'], quality_note='routine_administration' if routine else ''))
if rows: emit(rows)
pq.write_table(pa.Table.from_pylist(raw_policy), OUT / 'policy_raw_ledger.parquet', compression='zstd')
manifest['policy_raw_records'] = len(raw_policy)
manifest['policy_snapshot_sha256'] = sha(policy_copy)
manifest['source_counts'] = dict(counts)
manifest['quality_counts'] = dict(quality)
manifest['date_ranges'] = {s: {'min': min(v), 'max': max(v)} for s, v in dates.items()}
manifest['documents'] = offset
manifest['selection_rules'] = {'papers': 'all identity-deduplicated records from works; no year/language/eligibility exclusion; retractions and templated records retained with flags', 'patents': 'publication year 2026, detail date preferred; dedup country+application; all publication links retained; no exact-title dedup', 'policy': 'all years; dedup URL or document-number+publisher, otherwise full metadata+text; administrative notices retained', 'unusable_text': 'retained in accounting with usable=false; not assigned an invented semantic class', 'literature_unit': 'published/preprint work identity using inherited cross-version dedup'}
manifest['completed_utc'] = now()
dump(OUT / 'INPUT_MANIFEST.json', manifest)
print('COMPLETE', manifest['source_counts'], manifest['date_ranges'], now(), flush=True)
