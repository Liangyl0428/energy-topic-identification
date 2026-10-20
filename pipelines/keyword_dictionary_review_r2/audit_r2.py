"""Persist the assistant's readings of the fixed R2 diagnostic cohort."""
from common import *

NOTES={
'R003':('摘要支持','摘要明确为光伏接入微电网的变换控制；主题名称同时说明MPPT并不限于光伏。'),
'R015':('证据不足','题名是冷储热与布雷顿火电循环，抽水蓄能标签可能为背景或错配；缺摘要，待全文核对。'),
'R025':('证据不足','题名仅表明法国电力系统情景分析，核电的具体角色缺摘要核实。'),
'R026':('摘要支持','摘要明确比较新建核电机组允许或禁止的情景及其对电源结构和排放的影响。'),
'R027':('范围待定','核燃料技术匹配，但场景是航天核热推进；电网招标是否纳入该场景需业务范围判断。'),
'R042':('已撤销触发','摘要是稀土离子的赝电容电吸附回收，缺储能研究依据；按能源范围撤销该论文Supercapacitor触发。'),
'R043':('证据不足','题名支持太阳能淡化，但储热是否构成研究内容缺摘要核实。'),
'R047':('摘要支持','摘要明确讨论微型CHP、分布式发电与热储能对电网的调节作用。'),
'R054':('摘要支持','摘要为发电投资组合和电力交易。Electricity仅支持通用电力关联，主题名称已据此校准，不声称是潮流研究。'),
'R061':('背景关联','研究断路器转轴的焊接制造，设备对象相关，但不是继电保护算法研究。'),
'R064':('摘要支持','摘要明确为40 kV高压直流发生器，支持高电压主题。'),
'R068':('背景关联','变压器站作为220 kV网络经济可靠性仿真的组成部分；不是变压器设计本身。'),
'R074':('摘要支持','摘要明确采用VSC变换器；Switched-mode power supply可能来自负载背景，粗类变换器有文本支持。'),
'R078':('证据不足','摘要主要是柔性电化学储能，尚不能确认Power electronics代表功率器件或变换研究，保留待核。'),
'R091':('范围待定','能量采集技术明确，应用是心脏起搏器供能；广义能源关联与电网业务范围须分开判断。'),
'R092':('文献类型提醒','题名是特刊社论，主题相关，但不能直接按原创研究成果计数。'),
'R096':('摘要支持','摘要明确为辐射制冷，属于暖通粗类；Radiant heating原词冷热方向并不精确。'),
'R102':('全局规则已修正','摘要是小水电站。Power station改归通用供能系统，不再据此把水电站归入火电。'),
'R108':('证据不足','题名是页岩气采收与封存，Oil shale标签所指油页岩是否成立缺摘要核对。'),
'R114':('证据不足','题名明确生物柴油能量生命周期分析，但具体排放或环境影响内容缺摘要确认。'),
'R120':('摘要支持','摘要明确讨论油气生产、价格、成本和投资，支持能源经济粗类。'),
'R125':('题录质量问题','题名像期刊名，但摘要是电动汽车文章内容；不能据题名单独删除。主题有背景关联，题录需修复。'),
'R126':('背景关联','摘要主要为电动汽车快充，新能源接入是后续研究方向；可再生能源不是主要研究对象。'),
'R127':('证据不足','题名为物联网负荷预测，是否实际研究或使用智能电表仍需摘要/全文。'),
'R128':('背景关联','摘要明确使用智能电表负荷曲线用于低压网络规划；计量是数据来源，不是唯一主旨。'),
'R133':('全局规则已修正','摘要是电力潮流和输电拥塞，非计算机通信网络；Computer network不再触发能源通信主题。'),
'R134':('保守规则可能漏分','题名显示车队IVR通信应用可能相关；取消Computer network泛化触发后暂不归入通信主题，留作补词候选。'),
'R138':('摘要支持','摘要明确研究燃料电池催化剂制备与结构表征，支持能源材料主题。'),
'R139':('证据不足','题名是环境光催化；Solar energy词所指是否符合能源应用范围缺摘要确认。'),
'R144':('已撤销触发','摘要中light指轻轨交通，不是电光源；撤销Electric light触发，保留电动车主题的补词建议。'),
'N001':('背景关联','氙灯和碳弧灯用于材料老化试验，电光源相关，不代表照明节能是主要对象。'),
'N008':('题名支持','暖通除湿与舒适性相关，风机盘管具体角色可再核实。'),
'N011':('证据不足','题名是光催化材料，卤素灯可能是实验光源；缺摘要，不能断言研究照明节能。'),
'N014':('已撤销触发','摘要明确电解槽—氢罐—燃料电池—电池系统，无内燃机系统依据；撤销该论文Internal combustion engine触发。'),
'N015':('题名支持','近红外LED荧光粉属于电光源材料；电网核心业务范围仍需单独判断。'),
'N016':('子词需核对','摘要为重质原油开采炼制，石油粗类正确；Light crude oil可能是比较背景或来源细粒度偏差。'),
'N017':('背景关联','紫外光源用于苯酚废水降解，电光源是实验条件，不能解释为照明节能主旨。'),
'N018':('证据不足','题名为油藏微生物表面活性剂，是否研究增强采油而非仅采样来源需更多正文。'),
'N022':('摘要支持','摘要讨论石油价格、库存市场与供应安全，支持能源经济粗类；具体储油套利词义仍可细审。'),
'N025':('背景关联','摘要重点是上网电价，RPS作为比较政策出现；能源政策粗类成立，不能断言主旨为RPS。'),
'N031':('子词需核对','题名明确燃气轮机和蒸汽注入，热力设备粗类成立，但缺摘要确认汽包这一具体设备。'),
}

def main():
    c=connect();fresh=pd.read_parquet(WORK/'fresh_topic_samples.parquet');terms=pd.read_parquet(WORK/'new_direct_term_samples.parquet')
    pin=json.loads((HERE/'review_sample_hashes.json').read_text())
    assert all(sha(WORK/name)==value for name,value in pin.items()),'Diagnostic sample changed; read it again before reusing annotations'
    rows=[]
    for frame,kind in [(fresh,'fresh_topic_relation'),(terms,'new_direct_term')]:
        for r in frame.itertuples():
            status,note=NOTES.get(r.evidence_id,('题名支持','已逐项阅读题名和命中词，支持该主题的初步关联；不据此断言其为唯一或主要研究方向。'))
            retained=c.execute('SELECT count(*) FROM topic_relations WHERE row_id=? AND topic_code=?',[int(r.row_id),r.topic_code]).fetchone()[0]>0
            trigger=True if kind=='fresh_topic_relation' else c.execute('SELECT count(*) FROM candidate_hits WHERE row_id=? AND keyword_code=?',[int(r.row_id),r.keyword_code]).fetchone()[0]>0
            rows.append({'evidence_id':r.evidence_id,'sample_kind':kind,'row_id':int(r.row_id),'doc_id':r.doc_id,
                'topic_code':r.topic_code,'title':r.title,'review_status':status,'review_note':note,
                'retained_after_review':retained,'sample_keyword_retained_after_review':trigger,
                'reviewer':'assistant','expert_approved':False,'independent_blind_test':False})
    review=pd.DataFrame(rows);review.to_csv(WORK/'paper_semantic_review.csv',index=False,encoding='utf-8-sig')
    # Re-evaluate the old issue cohort after the final two global corrections.
    oldroot=ROOT/'work/keyword_dictionary_multilabel_20261019'
    old=pd.read_parquet(oldroot/'new_topic_samples.parquet').merge(pd.read_csv(oldroot/'sample_review.csv'),on='evidence_id')
    c.register('old_review',old[['evidence_id','row_id','topic_code','title','review_status','review_note']])
    reg=c.execute('''SELECT o.*,e.row_id IS NOT NULL still_assigned_to_original_topic,
      a.doc_id,a.classification_status,a.topic_codes final_topic_codes
      FROM old_review o JOIN assignments a USING(row_id) LEFT JOIN topic_relations e USING(row_id,topic_code)
      ORDER BY evidence_id''').df()
    reg.to_parquet(WORK/'previous_semantic_review_regression.parquet',index=False)
    old_bad=reg[reg.review_status.isin(['疑似误分','疑似过度推断'])]
    reg['final_topic_codes']=reg.final_topic_codes.map(lambda x:' | '.join(x))
    issues=reg[~reg.review_status.isin(['题名支持','正文支持']) | reg.evidence_id.eq('D028')].copy()
    issues['r1_annotation_corrected_in_r2']=issues.evidence_id.eq('D028')
    issues.to_csv(WORK/'previous_semantic_issues.csv',index=False,encoding='utf-8-sig')
    # Missing-keyword findings are recommendations, not fabricated source tags.
    original_meta=pd.read_parquet(oldroot/'review_metadata.parquet')
    suggestions=[]
    for doc,topic,word in [('paper:W3140535007','KWD-T0019','Lithium-ion battery'),('paper:W929228867','KWD-T0019','Lithium-ion battery'),('paper:W2808770485','KWD-T0034','Transformer'),('paper:W2473986016','KWD-T0051','Thermal power station'),('paper:W122256720','KWD-T0022','Thermal energy storage')]:
        m=original_meta[original_meta.doc_id.eq(doc)].iloc[0]
        a=c.execute('SELECT classification_status,topic_codes FROM assignments WHERE doc_id=?',[doc]).fetchone()
        suggestions.append({'doc_id':doc,'title':m.title,'suggested_topic':topic,'suggested_keyword':word,
          'classification_status':a[0],'applied':False,'reason':'题名有明确对象，但来源关键词缺失；建议补词后重新审核，未直接改写来源关键词。'})
    for eid,topic,word in [('R144','KWD-T0042','Electric vehicle'),('R134','KWD-T0067','Interactive voice response')]:
        m=fresh[fresh.evidence_id.eq(eid)].iloc[0]
        suggestions.append({'doc_id':m.doc_id,'title':m.title,'suggested_topic':topic,'suggested_keyword':word,
          'classification_status':c.execute('SELECT classification_status FROM assignments WHERE row_id=?',[int(m.row_id)]).fetchone()[0],
          'applied':False,'reason':'题名/摘要可指认具体对象；来源中缺少足够明确的关键词，建议补词后审核，尚未施加归属。'})
    pd.DataFrame(suggestions).to_csv(WORK/'missing_keyword_suggestions.csv',index=False,encoding='utf-8-sig')
    # The source-word audit keeps sampling-time and final dictionary states separate.
    keys=pd.read_csv(WORK/'sample_source_keywords.csv').fillna('')
    if 'decision_at_sampling' not in keys:keys=keys.rename(columns={'decision':'decision_at_sampling','topic_code':'topic_at_sampling'})
    lookup=c.execute('SELECT k.raw_name,d.decision decision_after_review,d.topic_code topic_after_review FROM keyword_lookup k JOIN dictionary d USING(keyword_code)').df()
    keys=keys.drop(columns=['decision_after_review','topic_after_review'],errors='ignore').merge(lookup,on='raw_name',validate='many_to_one')
    keys.to_csv(WORK/'sample_source_keywords.csv',index=False,encoding='utf-8-sig')
    d=json.loads((WORK/'DICTIONARY_COMPLETE.json').read_text());prior=json.loads((oldroot/'DICTIONARY_COMPLETE.json').read_text())
    out={'summary':'本轮逐项审读词名并复查181条论文主题/关键词实例，修正泛化触发及有文本依据的逐篇错配。抽样用于诊断与迭代，不是全库语义准确率验收。',
      'term_name_reviewed':d['r2_term_name_review_count'],'newly_read_terms':d['r2_newly_read_terms'],
      'old_terms_revisited':d['r2_term_name_review_count']-d['r2_newly_read_terms'],
      'unread_terms_before':prior['decisions']['unreviewed'],'unread_terms_after':d['decisions']['unreviewed'],
      'unread_keyword_occurrence_mass_before':prior['keyword_document_occurrences_by_decision']['unreviewed'],
      'unread_keyword_occurrence_mass_after':d['keyword_document_occurrences_by_decision']['unreviewed'],
      'term_name_review_is_not_article_context_validation':True,
      'fresh_topic_samples':len(fresh),'new_direct_term_samples':len(terms),'sample_status_counts':review.review_status.value_counts().to_dict(),
      'old_flagged_semantic_relations':len(old_bad),'old_flagged_relations_no_longer_present':int((~old_bad.still_assigned_to_original_topic).sum()),
      'old_missed_annotation_corrected':'D028: PV decommissioning had been incorrectly title-supported in v1; nuclear trigger withheld in r2.',
      'document_trigger_withholdings':int(pd.read_csv(WORK/'document_keyword_review.csv').action.eq('withhold_trigger').sum()),
      'explicit_unresolved_source_tags':int(pd.read_csv(WORK/'document_keyword_review.csv').action.eq('needs_context').sum()),
      'missing_keyword_suggestions_not_applied':len(suggestions),'semantic_accuracy_validated':False,
      'independent_blind_test':False,'caveat':'Fresh samples excluded v1 papers but were then used to refine rules; do not interpret counts as a held-out accuracy score or every removed relation as a corrected error.',
      'remaining_issues':['43k词尚未逐项审读；已读通用词多数仍需语境判断。','来源标签错误、缺关键词和题录错误仍存在，未按题名单独批量删除。','设备或技术词可能仅作为背景/实验条件出现；主题相关不等于主要研究对象。','收紧通用词提高了判断门槛，也可能造成漏分；R134已保留为补词候选。','医学供能、航天核能等边界应用仍需按招标业务范围审定。']}
    write(WORK/'REVIEW.json',out)
    checks={'original_paper_population':c.execute('SELECT count(*) FROM assignments').fetchone()[0]==4831088,
      'source_observations_unchanged':c.execute('SELECT count(*) FROM observations').fetchone()[0]==58998384,
      'withheld_source_words_really_observed':c.execute('''SELECT count(*) FROM withheld_keywords w ANTI JOIN
        (SELECT o.row_id,k.keyword_code FROM observations o JOIN keyword_lookup k USING(keyword_id)) s USING(row_id,keyword_code)''').fetchone()[0]==0,
      'no_withheld_keyword_triggers_remain':c.execute('SELECT count(*) FROM candidate_hits JOIN withheld_keywords USING(row_id,keyword_code)').fetchone()[0]==0,
      'power_station_does_not_imply_thermal_power':c.execute("SELECT topic_code FROM dictionary WHERE canonical_name='power station'").fetchone()[0]=='KWD-T0061',
      'generic_computer_network_does_not_trigger':c.execute("SELECT decision FROM dictionary WHERE canonical_name='computer network'").fetchone()[0]=='broad_auxiliary',
      'known_old_semantic_regressions':int((~old_bad.still_assigned_to_original_topic).sum())==8,
      'all_181_samples_have_annotations':len(review)==181 and review.evidence_id.nunique()==181,
      'no_suggested_keyword_added_to_source':not any(x['applied'] for x in suggestions)}
    oldassets=ROOT/'final/assets/keyword_dictionary_multilabel';manifest=json.loads((oldassets/'RELEASE.json').read_text())
    checks['v1_all_514_assets_unchanged']=all(sha(oldassets/name)==h for name,h in manifest['files'].items())
    write(WORK/'SEMANTIC_REVIEW_CHECK.json',{'passed':all(checks.values()),'checks':checks,'semantic_accuracy_validated':False})
    print(json.dumps(out,ensure_ascii=False,indent=2));assert all(checks.values()),checks

if __name__=='__main__':main()
