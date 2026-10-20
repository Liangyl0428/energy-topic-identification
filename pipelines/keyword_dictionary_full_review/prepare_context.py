"""Freeze diagnostic contexts, never infer semantic labels automatically."""
from common import *
import pyarrow.parquet as pq


def main():
    assert not (WORK / 'CONTEXT_PREPARED.json').exists(), 'Frozen context queue already exists'
    p = read(WORK / 'PROGRESS.json')
    assert p['reviewed_in_this_full_pass'] == p['total_terms'] == 48327
    for b in p['batch_manifest']:
        assert sha(WORK / b['review_file']) == b['review_sha256']
    x = pd.read_csv(WORK / 'term_review_ledger.csv', keep_default_na=False)
    assert len(x) == x.keyword_code.nunique() == x.review_index.nunique() == 48327
    chosen = (x.semantic_category.isin([
        'explicit_energy_mapping_candidate', 'term_meaning_requires_context',
        'known_energy_boundary_not_activated']) | x.prior_decision.isin(['direct', 'conditional']))
    targets = x[chosen].copy()
    topics = {t['topic_code']: t for t in read(BASELINE / 'topic_definitions.json')}
    targets['allowed_topics'] = targets.topic_code.map(
        lambda code: topics.get(code, {}).get('conditional_anchor_topics', []))
    targets['new_mapping'] = targets.semantic_category.eq('explicit_energy_mapping_candidate')
    targets['active_prior'] = targets.prior_decision.isin(['direct', 'conditional'])
    targets['priority'] = 3
    targets.loc[targets.active_prior, 'priority'] = 2
    targets.loc[targets.new_mapping, 'priority'] = 1
    # Explicitly identified cross-batch issues must appear at the front.
    names = {
        'Turbofan', 'Turbojet', 'Aero engine', 'Aircraft engine', 'Rocket engine',
        'Goose', 'RDF', 'Primary cell', 'Corium', 'CO poisoning', 'Plateau pressure',
        'Mechanical ventilation', 'Commutator', 'Scram', 'Resolver', 'Bulb', 'NODAL',
        'ASTRA', 'TEC', 'DSPACE', 'SQUID', 'Squid', 'Voltmeter', 'Multimeter',
        'Ammeter', 'Electrometer', 'Braking chopper', 'Eddy current brake',
        'Christmas tree', 'Astron', 'Methanizer', 'Transductor', 'DIDO', 'ID3',
        'Passive radiator', 'Smart power', 'Biopower', 'HYDROSOL', 'Transformer',
        'Motor control', 'Dynamic braking', 'Solarisation', 'Short circuit ratio',
        'Candle', 'Tritium illumination', 'Railgun', 'Inverter',
    }
    # Add explicitly requested issues even if they were initially generic nontriggers.
    extra = x[x.display_name.isin(names) & ~x.keyword_code.isin(targets.keyword_code)].copy()
    extra['allowed_topics'] = [[] for _ in range(len(extra))]
    extra['new_mapping'] = False
    extra['active_prior'] = extra.prior_decision.isin(['direct', 'conditional'])
    extra['priority'] = 0
    targets = pd.concat([targets, extra], ignore_index=True)
    targets.loc[targets.display_name.isin(names), 'priority'] = 0
    targets.to_parquet(WORK / 'context_targets.parquet', index=False)
    c = connect()
    c.register('target_input', targets)
    c.execute('CREATE OR REPLACE TABLE context_targets AS SELECT * FROM target_input')
    c.execute('CREATE OR REPLACE VIEW observations AS SELECT * FROM baseline.observations')
    c.execute('CREATE OR REPLACE VIEW papers AS SELECT * FROM baseline.papers')
    c.execute('CREATE OR REPLACE TABLE keyword_lookup AS SELECT * FROM baseline.keyword_lookup')
    print('Selecting reproducible source observations', flush=True)
    # Stratify by compatibility with R2's anchors solely for diagnostic sampling.
    # These are NOT validated final memberships and are labeled accordingly.
    q = c.execute('''WITH anchor_map AS (
        SELECT map(list(keyword_code),list(topic_code)) kw_to_topic
        FROM baseline.dictionary WHERE decision='direct'
      ), occurrences AS (
        SELECT o.row_id, k.keyword_code, max(o.score) source_keyword_score
        FROM observations o JOIN keyword_lookup k USING(keyword_id)
        JOIN context_targets t USING(keyword_code)
        GROUP BY o.row_id,k.keyword_code
      ), base AS (
        SELECT o.*,p.doc_id,p.title_only,p.retracted,p.template_record,
          t.decision,t.new_mapping,t.priority,t.document_frequency,t.allowed_topics,
          list_transform(list_filter(coalesce(a.anchor_keyword_codes,[]::VARCHAR[]),
            kw -> kw != o.keyword_code),kw -> map_extract_value(m.kw_to_topic,kw)) other_anchor_topics
        FROM occurrences o JOIN context_targets t USING(keyword_code)
        JOIN papers p USING(row_id) LEFT JOIN baseline.anchors a USING(row_id)
        CROSS JOIN anchor_map m
      ), stratified AS (
        SELECT *,CASE WHEN len(other_anchor_topics)=0 THEN FALSE
          WHEN len(allowed_topics)=0 THEN TRUE
          ELSE len(list_intersect(allowed_topics,other_anchor_topics))>0
          END baseline_compatible_anchor FROM base
      ), ranked AS (
        SELECT *,row_number() OVER(PARTITION BY keyword_code,baseline_compatible_anchor
            ORDER BY retracted OR template_record,title_only,
              md5(doc_id || keyword_code || 'continuous-full-review-context-v2')) sample_rank
        FROM stratified
      ) SELECT * EXCLUDE(allowed_topics,other_anchor_topics) FROM ranked
        WHERE sample_rank <= CASE WHEN priority=0 OR (new_mapping AND decision='direct') THEN 2 ELSE 1 END
        ORDER BY priority,keyword_code,baseline_compatible_anchor DESC,sample_rank''').df()
    assert set(targets.keyword_code) == set(q.keyword_code), 'A target has no actual source observation'
    q['context_index'] = range(1, len(q) + 1)
    q['evidence_id'] = q.context_index.map(lambda i: f'C{i:05d}')
    meta = []
    ids = set(int(i) for i in q.row_id)
    for i, part in enumerate(sorted(CORPUS.glob('part-*.parquet'))):
        stats = pq.ParquetFile(part).metadata.row_group(0).column(0).statistics
        own = sorted(r for r in ids if stats.min <= r <= stats.max)
        if own:
            meta.append(pd.read_parquet(part, columns=['row_id','doc_id','title','body','url','language','date'],
                                       filters=[('row_id','in',own)]))
        if i % 40 == 0:
            print('Source metadata partitions', i, flush=True)
    meta = pd.concat(meta, ignore_index=True)
    assert meta.row_id.nunique() == len(meta) == len(ids)
    meta.to_parquet(WORK / 'context_metadata.parquet', index=False)
    q = q.merge(meta, on=['row_id','doc_id'], validate='many_to_one')
    q = q.merge(targets[['keyword_code','review_index','display_name','topic_code','reason','semantic_category',
                        'prior_decision','prior_topic_code']], on='keyword_code', validate='many_to_one')
    c.register('selected_contexts', q[['row_id','evidence_id']])
    source = c.execute('''SELECT s.evidence_id,o.row_id,k.keyword_code,k.keyword_id,k.raw_name,o.score,
        d.decision baseline_decision,d.topic_code baseline_topic_code
        FROM selected_contexts s JOIN observations o USING(row_id)
        JOIN keyword_lookup k USING(keyword_id) JOIN baseline.dictionary d USING(keyword_code)
        ORDER BY s.evidence_id,k.keyword_code,k.keyword_id''').df()
    source.to_parquet(WORK / 'context_source_keywords.parquet', index=False)
    # Full bodies are preserved separately. Reviewers must explicitly expand any
    # excerpt when the title does not justify a semantic judgment.
    q.drop(columns='body').to_parquet(WORK / 'frozen_context_queue.parquet', index=False)
    q[['context_index','evidence_id','keyword_code','display_name','row_id','doc_id','title']].to_csv(
        WORK / 'context_queue.csv', index=False, encoding='utf-8-sig')
    summary = {
        'target_terms': len(targets), 'contexts': len(q), 'unique_papers': len(ids),
        'term_name_count': 48327, 'source_dictionary_sha256': p['source_sha256'],
        'term_ledger_sha256': sha(WORK / 'term_review_ledger.csv'),
        'context_queue_sha256': sha(WORK / 'frozen_context_queue.parquet'),
        'metadata_sha256': sha(WORK / 'context_metadata.parquet'),
        'source_keywords_sha256': sha(WORK / 'context_source_keywords.parquet'),
        'method': 'Deterministic samples per observed keyword, stratified by compatibility with other baseline direct anchors, excluding the reviewed keyword itself; prefer unflagged records with body, then md5; two per stratum for new direct mappings and explicit risk terms, one otherwise.',
        'scope': 'Every new mapping, every existing active word, all unresolved word meanings and recorded boundaries; additional cross-batch issues.',
        'baseline_anchors_are_sampling_only': True,
        'reviewed_keyword_excluded_from_sampling_anchors': True,
        'automatic_semantic_decisions': False,
        'independent_blind_accuracy_test': False,
    }
    write(WORK / 'CONTEXT_PREPARED.json', summary)
    write(WORK / 'CONTEXT_PROGRESS.json', {'total_contexts':len(q),'reviewed':0,'batch_manifest':[]})
    print(json.dumps(summary,ensure_ascii=False,indent=2), flush=True)


if __name__ == '__main__':
    main()
