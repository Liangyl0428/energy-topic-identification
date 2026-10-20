"""Recount explicit energy-task title scopes across the frozen full corpus.

No API calls, no inherited F-topic ranks, no inferred maturity grades.
Large document memberships stay in work; reviewable aggregates ship in final.
"""
from pathlib import Path
import argparse
import hashlib
import inspect
import json
import math
import re
import sys
from datetime import datetime, timezone
import duckdb
import pandas as pd

FINAL = Path(__file__).resolve().parents[1]
ROOT = FINAL.parent
sys.path.insert(0, str(FINAL))
from runtime_config import load_runtime
from p1_common import read, write, table, sha, WINDOWS
from p2_taxonomy import VERSION, CATEGORIES, taxonomy

OUT = FINAL / 'assets/p2'
WORK = ROOT / 'work/business_p2_20261019'
ID = FINAL / 'energy-topic-identification/assets/full_nmf500'
HOT = FINAL / 'energy-topic-hotspots/assets/full_nmf500'
MAT = FINAL / 'energy-technology-trl-crl/assets/full_nmf500'


def sql(value):
    return "'" + str(value).replace("'", "''") + "'"


def pattern(value):
    return value.replace('[- ]', '[- ‐‑‒–—−]')


def match_title(title, topic):
    if topic['negative_pattern'] and re.search(topic['negative_pattern'], title, re.I):
        return []
    hits = [re.search(pattern(p), title, re.I) for p in topic['match_patterns']]
    return [m.group(0) for m in hits] if all(hits) else []


def describe_trend(recent, previous, recent_denom, previous_denom, growing, institutions):
    """Predeclared diagnostic tiers, not predictions or expert approval."""
    ratio = recent / recent_denom / (previous / previous_denom) if previous and previous_denom and recent_denom else None
    if recent < 30 or previous < 30:
        status, priority = '样本较少或基期较小', '观察'
    elif ratio >= 1.2 and growing >= 3 and institutions >= 1:
        status, priority = '份额持续上升', '优先研读'
    elif ratio < 0.8:
        status, priority = '份额下降', '核查变化'
    elif ratio >= 1.2:
        status, priority = '份额上升但持续性待观察', '持续跟踪'
    else:
        status, priority = '份额相对平稳', '持续跟踪'
    return {'share_growth_ratio': ratio, 'signal': status, 'attention': priority}


def input_fingerprint(runtime):
    source = runtime.path('classification_run')
    manifest = read(source/'ASSIGNMENTS_MANIFEST.json')
    if set(manifest['files']) != {p.name for p in (source/'assignments').glob('*.parquet')}:
        raise ValueError('Assignment inventory drift')
    # Hash each real input part once; refuse silently changed classifications.
    for name, expected in manifest['files'].items():
        if sha(source/'assignments'/name) != expected:
            raise ValueError('Assignment changed: '+name)
    return {'version': VERSION, 'taxonomy_sha256': sha(Path(__file__).with_name('p2_taxonomy.py')),
            'builder_sha256': sha(Path(__file__)),
            'membership_code_sha256': hashlib.sha256((inspect.getsource(open_database)+inspect.getsource(pattern)).encode()).hexdigest(),
            'assignments_manifest_sha256': sha(source/'ASSIGNMENTS_MANIFEST.json'),
            'assignment_parts_freshly_hashed': len(manifest['files']),
            'metadata_path': str(runtime.path('metadata_db')),
            'metadata_bytes': runtime.path('metadata_db').stat().st_size,
            'metadata_mtime_ns': runtime.path('metadata_db').stat().st_mtime_ns,
            'metadata_full_hash_recomputed': False,
            'source_kind': 'frozen_assignments_with_original_titles_and_quality_flags',
            'raw_data_path': str(runtime.path('raw_data_dir')),
            'corpus_path': str(runtime.path('corpus_dir')),
            'external_network_used': False, 'windows': WINDOWS}


def open_database(runtime, rebuild):
    WORK.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WORK/'business.duckdb'))
    con.execute("SET threads=4; SET memory_limit='5GB'")
    con.execute('SET temp_directory='+sql(WORK/'tmp'))
    if rebuild:
        con.execute('DROP TABLE IF EXISTS members; DROP TABLE IF EXISTS population')
        src = runtime.path('classification_run')/'assignments/*.parquet'
        con.execute("""CREATE TABLE population AS SELECT row_id,doc_id,source,title,
          try_cast(date AS DATE) date,category_id,title_only,retracted,template_record,usable,
          usable AND NOT retracted AND NOT template_record AS eligible
          FROM read_parquet("""+sql(src)+')')
        n, unique = con.execute('SELECT count(*),count(DISTINCT doc_id) FROM population').fetchone()
        if n != unique:
            raise ValueError('Frozen doc_id is not unique')
        con.execute('CREATE TABLE members (doc_id VARCHAR,business_topic_id VARCHAR)')
        for topic in taxonomy():
            conditions = ['regexp_matches(title,'+sql(pattern(p))+",'i')" for p in topic['match_patterns']]
            if topic['negative_pattern']:
                conditions.append('NOT regexp_matches(title,'+sql(topic['negative_pattern'])+",'i')")
            con.execute('INSERT INTO members SELECT doc_id,'+sql(topic['business_topic_id'])+
                        ' FROM population WHERE usable AND '+ ' AND '.join(conditions))
            count = con.execute('SELECT count(*) FROM members WHERE business_topic_id=?',[topic['business_topic_id']]).fetchone()[0]
            print(topic['business_topic_id'],topic['name'],count,flush=True)
        con.execute('CHECKPOINT')
        con.execute('COPY (SELECT m.*,p.row_id,p.source,p.date,p.category_id,p.eligible FROM members m JOIN population p USING(doc_id)) TO '+
                    sql(WORK/'memberships.parquet')+" (FORMAT PARQUET,COMPRESSION ZSTD)")
    con.execute('ATTACH '+sql(runtime.path('metadata_db'))+' AS metadata (READ_ONLY)')
    con.execute("""CREATE OR REPLACE TEMP VIEW member_docs AS
       SELECT m.business_topic_id,p.* FROM members m JOIN population p USING(doc_id)""")
    return con


def build(runtime, force=False):
    OUT.mkdir(parents=True, exist_ok=True)
    for p in [ID/'p2', HOT/'p2', MAT/'p2']:
        p.mkdir(exist_ok=True)
    fingerprint = input_fingerprint(runtime)
    previous = read(WORK/'INPUTS.json') if (WORK/'INPUTS.json').exists() else None
    cache_keys = ['taxonomy_sha256', 'membership_code_sha256', 'assignments_manifest_sha256']
    reuse = previous is not None and all(previous.get(k)==fingerprint[k] for k in cache_keys) and (WORK/'memberships.parquet').exists()
    con = open_database(runtime, not reuse or force)
    write(WORK/'INPUTS.json',fingerprint)
    topics = taxonomy()
    bids = [t['business_topic_id'] for t in topics]
    periods = pd.period_range('2021Q3','2026Q2',freq='Q').astype(str)
    history = "date BETWEEN DATE '2021-07-01' AND DATE '2026-06-30'"
    # Population is the identity-deduplicated frozen literature pool, irrespective
    # of how many business scopes match a paper. It is not sum(topic counts).
    den = con.execute("SELECT concat(year(date),'Q',quarter(date)) period,count(*) papers FROM population WHERE source='paper' AND eligible AND "+history+' GROUP BY ALL').df()
    denom = dict(zip(den.period, den.papers))
    counts = con.execute("SELECT business_topic_id,concat(year(date),'Q',quarter(date)) period,count(*) papers FROM member_docs WHERE source='paper' AND eligible AND "+history+' GROUP BY ALL').df()
    grid = pd.MultiIndex.from_product([bids,periods],names=['business_topic_id','period'])
    q = counts.set_index(['business_topic_id','period']).reindex(grid,fill_value=0).reset_index()
    q['denominator_papers'] = q.period.map(denom)
    q['share'] = q.papers/q.denominator_papers
    q.to_csv(HOT/'p2/business_quarter_counts.csv',index=False)
    den.to_csv(HOT/'p2/population_quarter_counts.csv',index=False)
    con.execute("""CREATE OR REPLACE TEMP TABLE recent_metadata AS
        SELECT p.doc_id,p.date,w.work_id,w.institutions
        FROM population p LEFT JOIN metadata.works w ON substr(p.doc_id,7)=w.work_id
        WHERE p.source='paper' AND p.eligible AND p.date BETWEEN '2024-07-01' AND '2026-06-30'
        AND EXISTS (SELECT 1 FROM members m WHERE m.doc_id=p.doc_id)""")
    institutions = con.execute("""SELECT m.business_topic_id,
       CASE WHEN r.date>='2025-07-01' THEN 'recent' ELSE 'previous' END time_window,
       count(DISTINCT lower(trim(i.name))) n
       FROM recent_metadata r JOIN members m USING(doc_id),
       unnest(string_split(coalesce(r.institutions,''),';')) i(name)
       WHERE lower(trim(i.name)) NOT IN ('','none','nan','[]') GROUP BY ALL""").df()
    ic = {(r.business_topic_id,r.time_window):int(r.n) for r in institutions.itertuples()}
    metadata_missing = con.execute("SELECT m.business_topic_id,count(*) FILTER(WHERE work_id IS NULL) missing,count(*) FILTER(WHERE coalesce(trim(institutions),'') IN ('','None','nan','[]')) empty FROM recent_metadata r JOIN members m USING(doc_id) GROUP BY ALL").df().set_index('business_topic_id').to_dict('index')
    source_counts = con.execute('SELECT business_topic_id,source,count(*) records,count(*) FILTER(WHERE eligible) quality_eligible_records,count(*) FILTER(WHERE eligible AND date BETWEEN \'2026-01-01\' AND \'2026-06-30\') common_window_records FROM member_docs GROUP BY ALL').df()
    source_counts.to_csv(HOT/'p2/source_counts.csv',index=False)
    bridge = con.execute('SELECT category_id,business_topic_id,source,count(*) documents FROM member_docs GROUP BY ALL ORDER BY category_id,business_topic_id,source').df()
    bridge.to_csv(ID/'p2/f_business_membership_counts.csv',index=False)
    # Fixed-hash samples span windows; not the most NMF-confident documents.
    samples = con.execute("""WITH ranked AS (SELECT *,CASE
       WHEN source!='paper' THEN source
       WHEN date BETWEEN '2025-07-01' AND '2026-06-30' THEN 'recent'
       WHEN date BETWEEN '2024-07-01' AND '2025-06-30' THEN 'previous'
       ELSE 'other_years' END sample_stratum,
       FROM member_docs), picked AS (SELECT *,row_number() OVER
       (PARTITION BY business_topic_id,sample_stratum ORDER BY md5(doc_id||'p2-review-v1')) rn FROM ranked)
       SELECT * EXCLUDE(rn) FROM picked WHERE rn<=3 ORDER BY business_topic_id,sample_stratum,doc_id""").df()
    evidence = []
    by_bid = {t['business_topic_id']:t for t in topics}
    for r in samples.to_dict('records'):
        r['date'] = str(r['date'].date()) if pd.notna(r['date']) else None
        r['quote_field'] = 'title'
        r['matched_quotes'] = match_title(r['title'],by_bid[r['business_topic_id']])
        r['review_status'] = 'automatic_title_match_pending_semantic_review'
        r['sample_method'] = 'lowest_md5_within_business_scope_and_time_source_stratum'
        r['url'] = 'https://openalex.org/'+r['doc_id'].split(':',1)[1] if r['source']=='paper' else None
        evidence.append(r)
    # Resolve original corpus identity, URL and continuous body context for samples.
    wanted = pd.DataFrame({'row_id': sorted({r['row_id'] for r in evidence})})
    con.register('wanted_sample_ids', wanted)
    parts = read(runtime.path('corpus_dir').parent/'INPUT_MANIFEST.json')['parts']
    needed = [runtime.path('corpus_dir')/Path(p['file']).name for p in parts
              if any(p['first_row']<=i<p['first_row']+p['n'] for i in wanted.row_id)]
    ctx = con.execute('SELECT c.row_id,c.doc_id,c.url,c.body,c.language FROM read_parquet(['+
                      ','.join(sql(p) for p in needed)+']) c JOIN wanted_sample_ids w USING(row_id)').df()
    context = {r['row_id']:r for r in ctx.to_dict('records')}
    for r in evidence:
        c=context[r['row_id']]
        if c['doc_id']!=r['doc_id']:raise ValueError('Corpus identity mismatch')
        r['url']=c['url'] or r['url'];r['language']=c['language']
        body=c['body'] if isinstance(c['body'],str) else ''
        r['body_excerpt']=body[:1800];r['body_excerpt_truncated']=len(body)>1800
        r['membership_basis']='title_only_rule_not_body_inference'
    table(ID/'p2/evidence_samples',evidence)
    metrics=[]
    for t in topics:
        bid=t['business_topic_id'];own=q[q.business_topic_id.eq(bid)]
        recent=own[own.period.ge('2025Q3')];previous_q=own[own.period.between('2024Q3','2025Q2')]
        r=int(recent.papers.sum());p=int(previous_q.papers.sum())
        rd=int(recent.denominator_papers.sum());pdn=int(previous_q.denominator_papers.sum())
        growing=sum(float(a)>float(b) for a,b in zip(recent.share,previous_q.share))
        ri=ic.get((bid,'recent'),0);pi=ic.get((bid,'previous'),0)
        signal=describe_trend(r,p,rd,pdn,growing,ri-pi)
        rs=r/rd;ps=p/pdn
        literal=f'近期 {r:,} 篇、前期 {p:,} 篇；占冻结文献池的份额为 {rs:.3%} 和 {ps:.3%}；4 个季度中 {growing} 个份额同比上升。'
        attention=signal['attention']
        action={'优先研读':'优先抽取近期增量研究，与已有路线比较验证条件，并安排技术交流。',
                '观察':'先补充代表证据与连续季度观察，避免小基数放大。',
                '核查变化':'核查收录、题名术语和技术路线迁移；份额下降不能直接认定技术失去价值。',
                '持续跟踪':'维持跟踪，重点比较实测效果和目标场景适配性。'}[attention]
        own_sources=source_counts[source_counts.business_topic_id.eq(bid)].to_dict('records')
        metrics.append({**t,**signal,'recent_papers':r,'previous_papers':p,
            'recent_denominator':rd,'previous_denominator':pdn,'recent_share':rs,'previous_share':ps,
            'paper_count_growth_ratio': r/p if p else None,
            'share_change_percentage_points':100*(rs-ps),'growing_quarters':growing,
            'recent_institutions':ri,'previous_institutions':pi,
            'metadata_coverage':metadata_missing.get(bid,{'missing':0,'empty':0}),
            'quarter_counts':own[['period','papers','denominator_papers','share']].to_dict('records'),
            'source_counts':own_sources,'narrative':literal,
            'decision_interpretation':f'{signal["signal"]}。{action} 本主题需要回答：{t["decision_question"]}',
            'potential_assessment':{'observed_signal':signal['signal'],'opportunity_to_investigate':t['decision_question'],
                 'condition_to_verify':t['bottleneck_to_check'],'next_step':t['next_investigation'],
                 'future_outcome':'未预测','future_potential_score':None},
            'recommended_actions':[action,t['next_investigation']],
            'evidence_doc_ids':[d['doc_id'] for d in evidence if d['business_topic_id']==bid],
            'statistical_population':'all_frozen_documents_matching_versioned_title_rules',
            'denominator_scope':'all_unique_quality_eligible_frozen_papers_in_same_window',
            'scope_approved':False,'rank_eligible':False,'trend_recomputed':True,
            'windows':WINDOWS,'generation_method':'recomputed_facts_and_analyst_task_framework',
            'limitations':['题名规则筛选可能漏掉隐含任务或其他语言；当前计数描述这个检索范围，不等于完整行业规模。',
              '多标签允许交叉，跨主题总量须按 doc_id 去重，不能相加。',
              '论文与机构变化不等于作者人数变化或未来预测。',
              '专利是冻结申请记录而非专利族；政策只是题名相关，尚未核验支持、监管或提及关系。']})
    table(ID/'p2/business_taxonomy',topics)
    table(HOT/'p2/business_insights',metrics)
    # Every legacy F cluster receives observed task composition and traceable
    # examples, not an invented single energy name.
    fbase=pd.read_csv(ID/'topic_catalog.csv')
    matched_counts=con.execute("SELECT category_id,count(DISTINCT doc_id) n FROM member_docs WHERE source='paper' GROUP BY ALL").df().set_index('category_id').n.to_dict()
    frows=[]
    for f in fbase.to_dict('records'):
        own=bridge[(bridge.category_id==f['category_id']) & (bridge.source=='paper')].sort_values('documents',ascending=False)
        shares=[{'business_topic_id':r.business_topic_id,'name':by_bid[r.business_topic_id]['name'],
                 'documents':int(r.documents)} for r in own.itertuples()]
        matched=int(matched_counts.get(f['category_id'],0));total=int(f['paper_documents'])
        frows.append({**f,'matched_unique_papers':matched,'unresolved_papers':total-matched,
             'business_composition':shares,'display_name_zh':f['category_id']+'｜'+('、'.join(x['name'] for x in shares[:2])+'等检索任务' if shares else '暂无明确业务任务命中'),
             'interpretation':'该编号保留算法聚类身份。下面是逐篇题名筛选的业务构成，不能把整个聚类改称其中一个任务。',
             'scope_approved':False,'whole_cluster_relabel':False,'business_version':VERSION})
    table(ID/'p2/f_topic_bridge',frows)
    cases=[]
    for c in read(MAT/'p1/case_insights.json'):
        own=[]
        for t in topics:
            if t['analysis_type']!='technical':continue
            for field in ['canonical_name','object_configuration','application_or_target_function']:
                quotes=match_title(str(c.get(field) or ''),t)
                if quotes:
                    own.append({'business_topic_id':t['business_topic_id'],'name':t['name'],
                                'quote_field':field,'quotes':quotes,'status':'object_text_candidate_pending_review'})
                    break
        a=c['trl_public_evidence_stage'];b=c['crl_public_evidence_stage']
        objective=c['application_or_target_function']
        if a is None:
            decision='先核查技术验证证据'
        elif a<=4:
            decision='安排目标工况验证'
        elif a<=6:
            decision='评估示范测试条件'
        elif b is None or b<=2:
            decision='核查工程适配与商业履约'
        else:
            decision='开展复制应用与经济性尽调'
        missing=c['case_specific_gaps']
        cases.append({**c,'business_version':VERSION,'business_links':own,
          'decision_stage':decision,
          'decision_brief':f'针对“{c["canonical_name"]}”在“{objective}”中的应用，建议{decision}。'+c['joint_interpretation'],
          'specific_questions':[f'在甲方目标场景下，{c["object_configuration"]}是否维持原测试条件和性能？']+
              [f'需取得材料并核实：{g}' for g in missing],
          'application_checks':list(dict.fromkeys(by_bid[l['business_topic_id']]['next_investigation'] for l in own)),
          'evidence_fetch_status':'existing_local_evidence_only',
          'grade_recomputed_or_upgraded':False})
    table(MAT/'p2/case_decision_cards',cases)
    populations=con.execute("SELECT source,count(*) records,count(*) FILTER(WHERE eligible) quality_eligible_records FROM population GROUP BY ALL").df().to_dict('records')
    matched_sources=con.execute('SELECT source,count(DISTINCT doc_id) matched_unique_documents FROM member_docs GROUP BY ALL').df().to_dict('records')
    summary={'version':VERSION,'created_utc':datetime.now(timezone.utc).isoformat(),
        'business_topics':len(topics),'business_categories':len(CATEGORIES),'legacy_f_topics':len(frows),
        'population_records':sum(r['records'] for r in populations),'populations':populations,
        'matched_unique_by_source':matched_sources,
        'membership_links':con.execute('SELECT count(*) FROM members').fetchone()[0],
        'evidence_sample_links':len(evidence),'evidence_sample_unique_docs':len({r['doc_id'] for r in evidence}),
        'object_cards':len(cases),'objects_with_business_candidates':sum(bool(c['business_links']) for c in cases),
        'paired_axis_objects':sum(c['paired_axes_usable'] for c in cases),
        'full_corpus_title_screening_completed':True,'rule_scope_trends_recomputed':True,
        'expert_approved_topics':0,'semantic_accuracy_independently_validated':False,
        'future_predictions_available':False,'external_network_used':False,
        'production_frontend_deployed':False,'input_fingerprint':fingerprint,
        'membership_artifact':str((WORK/'memberships.parquet').relative_to(ROOT)),
        'membership_sha256':sha(WORK/'memberships.parquet'),
        'interpretation':'全量冻结语料上的明确题名检索范围与重算趋势；不是已经人工逐篇审定的全行业分类。'}
    write(OUT/'SUMMARY.json',summary)
    write(OUT/'platform_data.json',{'summary':summary,'categories':CATEGORIES,
          'topics':metrics,'legacy_topics':frows,'cases':cases,'evidence_samples':evidence})
    with pd.ExcelWriter(OUT/'业务主题与决策解读.xlsx',engine='openpyxl') as writer:
        for name,rows in [('业务定义',topics),('趋势与行动',metrics),('F主题业务构成',frows),('文献证据样本',evidence),('对象决策',cases)]:
            flat=[{k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rows]
            df=pd.DataFrame(flat)
            # Excel is a review view; source titles and values must remain text.
            df.to_excel(writer,sheet_name=name,index=False)
            ws=writer.book[name];ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
            for row in ws:
                for cell in row:
                    if cell.data_type=='f':cell.data_type='s'
            for col in ws.columns:ws.column_dimensions[col[0].column_letter].width=24
    con.close()
    print(json.dumps({k:v for k,v in summary.items() if k!='input_fingerprint'},ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--force',action='store_true')
    args=parser.parse_args();build(load_runtime(),force=args.force)
