from common import *

def main():
    c=connect()
    dictionary=json.loads((WORK/'DICTIONARY_COMPLETE.json').read_text())
    print('MATCH explicit dictionary keywords',flush=True)
    c.execute('''CREATE OR REPLACE TABLE candidate_hits AS
        SELECT o.row_id,o.keyword_id source_keyword_id,o.score source_keyword_score,
               k.keyword_code,d.topic_code,d.decision,d.display_name,
               CASE WHEN d.conditional_anchor_topics='' THEN []::VARCHAR[] ELSE string_split(d.conditional_anchor_topics,' | ') END allowed_anchor_topics
        FROM observations o JOIN keyword_lookup k USING(keyword_id)
        JOIN dictionary d USING(keyword_code) WHERE d.decision IN ('direct','conditional')''')
    c.execute('''CREATE OR REPLACE TABLE anchors AS SELECT row_id,
        list(DISTINCT keyword_code ORDER BY keyword_code) anchor_keyword_codes,
        list(DISTINCT display_name ORDER BY display_name) anchor_keywords,
        list(DISTINCT topic_code ORDER BY topic_code) anchor_topic_codes
        FROM candidate_hits WHERE decision='direct' GROUP BY row_id''')
    c.execute("""CREATE OR REPLACE TABLE eligible_hits AS SELECT h.* FROM candidate_hits h
        JOIN anchors a USING(row_id) WHERE h.decision='direct' OR len(h.allowed_anchor_topics)=0
        OR len(list_intersect(h.allowed_anchor_topics,a.anchor_topic_codes))>0""")
    print('GROUP exact topic memberships and evidence',flush=True)
    relation_query='''SELECT h.row_id,h.topic_code,
        bool_or(h.decision='direct') has_direct_hit,
        list(DISTINCT h.keyword_code ORDER BY h.keyword_code) matched_keyword_codes,
        list(DISTINCT h.display_name ORDER BY h.display_name) matched_keywords,
        list(DISTINCT h.source_keyword_id ORDER BY h.source_keyword_id) matched_source_keyword_ids
        FROM eligible_hits h JOIN anchors a USING(row_id) WHERE h.row_id BETWEEN {lo} AND {hi} GROUP BY h.row_id,h.topic_code'''
    assignment_query='''WITH grouped AS (
        SELECT row_id,list(topic_code ORDER BY topic_code) topic_codes,
               list(topic_code ORDER BY topic_code) FILTER(WHERE has_direct_hit) direct_topic_codes,
               list(topic_code ORDER BY topic_code) FILTER(WHERE NOT has_direct_hit) conditional_topic_codes
        FROM topic_relations WHERE row_id BETWEEN {lo} AND {hi} GROUP BY row_id), raw AS (
        SELECT row_id,count(*) raw_keyword_count,count(DISTINCT keyword_code) canonical_keyword_count
        FROM observations JOIN keyword_lookup USING(keyword_id) WHERE row_id BETWEEN {lo} AND {hi} GROUP BY row_id), blocked AS (
        SELECT row_id,count(*) conditional_hit_count FROM candidate_hits WHERE decision='conditional' AND row_id BETWEEN {lo} AND {hi} GROUP BY row_id)
        SELECT p.*,coalesce(raw.raw_keyword_count,0) raw_keyword_count,
          coalesce(raw.canonical_keyword_count,0) canonical_keyword_count,
          coalesce(g.topic_codes,[]::VARCHAR[]) topic_codes,
          coalesce(g.direct_topic_codes,[]::VARCHAR[]) direct_topic_codes,
          coalesce(g.conditional_topic_codes,[]::VARCHAR[]) conditional_topic_codes,
          coalesce(len(g.topic_codes),0)::INTEGER topic_count,
          coalesce(a.anchor_keyword_codes,[]::VARCHAR[]) anchor_keyword_codes,
          coalesce(a.anchor_keywords,[]::VARCHAR[]) anchor_keywords,
          coalesce(a.anchor_topic_codes,[]::VARCHAR[]) anchor_topic_codes,
          NOT p.retracted AND NOT p.template_record AS quality_eligible,
          CASE WHEN g.row_id IS NOT NULL THEN 'assigned'
               WHEN raw.row_id IS NULL THEN 'no_keywords'
               WHEN blocked.row_id IS NOT NULL THEN 'conditional_only_no_energy_anchor'
               ELSE 'no_active_dictionary_keyword' END classification_status
        FROM papers p LEFT JOIN grouped g USING(row_id) LEFT JOIN anchors a USING(row_id)
        LEFT JOIN raw USING(row_id) LEFT JOIN blocked USING(row_id) WHERE p.row_id BETWEEN {lo} AND {hi}'''
    # Bound LIST aggregation memory by document range.
    for lo in range(0,4831088,100000):
        hi=min(lo+99999,4831087)
        for table,query in [('topic_relations',relation_query),('assignments',assignment_query)]:
            prefix=f'CREATE OR REPLACE TABLE {table} AS ' if lo==0 else f'INSERT INTO {table} '
            c.execute(prefix+query.format(lo=lo,hi=hi))
        print('GROUPED',hi+1,flush=True)
    counts=c.execute('''SELECT count(*) papers,count(*) FILTER(WHERE topic_count>0) assigned_papers,
        count(*) FILTER(WHERE topic_count>1) multilabel_papers,sum(topic_count) relations,
        count(*) FILTER(WHERE topic_count>0 AND quality_eligible) quality_eligible_assigned_papers,
        count(*) FILTER(WHERE NOT quality_eligible) flagged_records,
        max(topic_count) maximum_topics_per_paper FROM assignments''').df().iloc[0].to_dict()
    print('EXPORT partitioned assignments and keyword evidence',flush=True)
    (WORK/'paper_assignments').mkdir(exist_ok=True);(WORK/'paper_topic_relations').mkdir(exist_ok=True)
    import pyarrow.parquet as pq
    for part in sorted(CORPUS.glob('part-*.parquet')):
        meta=pq.ParquetFile(part);stats=meta.metadata.row_group(0).column(0).statistics
        lo,hi=int(stats.min),int(stats.max)
        if lo>=4831088:continue
        hi=min(hi,4831087)
        for table,folder,query in [
            ('assignments','paper_assignments','SELECT * FROM assignments WHERE row_id BETWEEN ? AND ? ORDER BY row_id'),
            ('topic_relations','paper_topic_relations','''SELECT p.doc_id,e.*,a.anchor_keywords,a.anchor_topic_codes,p.quality_eligible
               FROM topic_relations e JOIN assignments p USING(row_id) JOIN anchors a USING(row_id)
               WHERE e.row_id BETWEEN ? AND ? ORDER BY e.row_id,e.topic_code''')]:
            target=str(WORK/folder/part.name).replace("'","''")
            c.execute(f"COPY ({query}) TO '{target}' (FORMAT PARQUET,COMPRESSION ZSTD)",[lo,hi])
    c.execute('''SELECT topic_code,count(*) documents,count(*) FILTER(WHERE has_direct_hit) direct_documents,
        count(*) FILTER(WHERE NOT has_direct_hit) conditional_documents,
        count(*) FILTER(WHERE quality_eligible) quality_eligible_documents
        FROM topic_relations JOIN assignments USING(row_id) GROUP BY topic_code ORDER BY topic_code''').df().to_csv(WORK/'topic_counts.csv',index=False)
    c.execute('SELECT topic_count,count(*) papers FROM assignments GROUP BY topic_count ORDER BY topic_count').df().to_csv(WORK/'topics_per_paper.csv',index=False)
    c.execute('SELECT classification_status,count(*) papers FROM assignments GROUP BY classification_status').df().to_csv(WORK/'assignment_status_counts.csv',index=False)
    # Display all raw keyword-count bins, including empty records.
    c.execute('SELECT canonical_keyword_count,count(*) papers FROM assignments GROUP BY canonical_keyword_count ORDER BY canonical_keyword_count').df().to_csv(WORK/'keywords_per_paper.csv',index=False)
    counts={k:int(v) for k,v in counts.items()}
    summary={'release_id':'keyword_dictionary_multilabel_20261019','counts':counts,
        'topics':dictionary['topics'],'dictionary_sha256':dictionary['dictionary_sha256'],
        'rule':'Every exact observed direct keyword triggers its topic. Conditional keywords require a compatible direct-topic anchor in the SAME paper; only supporting themes allow any direct energy anchor. Allowed families are explicit in the dictionary. Union all matching themes, deduplicate; no score threshold or top-N cap.',
        'quality_policy':'All papers receive literal dictionary memberships, including flagged records. Retracted/template flags and quality_eligible are retained so downstream users can exclude them; no document is physically deleted.',
        'matching_fields':'Canonical original source keyword identities only. Titles/abstracts not used to infer missing keywords.',
        'no_nmf':True,'no_transfer':True,'no_renormalization':True,
        'semantic_accuracy_validated':False,'scope':'all 4831088 frozen paper records; patents and policies not inferred in this release'}
    write(WORK/'CLASSIFIED.json',summary);print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
