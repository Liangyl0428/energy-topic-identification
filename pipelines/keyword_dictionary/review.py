"""Record the assistant's actual reading of the fixed final sample.

These annotations apply to the frozen evidence IDs and titles of this release.
After any membership change, review again; do not reuse them as an auto-review.
"""
from common import *

# Exceptions to title-supported membership; evidence excerpts were read for
# ambiguous cases. No precision estimate is inferred from this tuning sample.
NOTES={
'D001':('背景关联','正文以抽水蓄能为主，太阳能并网是应用背景；光伏标签不等于光伏为主要研究对象。'),
'D010':('证据不足','题名仅说明水电联产、淡化和储能，缺正文；Geothermal desalination词不能单独验证地热驱动。'),
'D011':('疑似误分','题名是种马精液与饲料补充研究，却带Wind power来源标签；字面规则继承了源标签错误。'),
'D020':('正文支持','正文讨论地热资源、温泉与地震构造关系，支持地热资源主题。'),
'D025':('正文支持','正文为ARIES聚变电站中子学与屏蔽；通用核能主题允许与聚变主题重叠，不应称其为裂变研究。'),
'D033':('证据不足','题名涉及合金中的氢固溶行为，但缺正文；储氢能源应用目前只由Hydrogen storage标签指示。'),
'D035':('证据不足','氢动力SUV与燃料电池相容，但缺正文，题名尚不能排除其他氢动力路线。'),
'D039':('正文支持','正文明确讨论电池SOC、过充过放和充放电控制，支持电池管理。'),
'D041':('证据不足','题名为制氢电极，Supercapacitor标签可能误配；无正文，保留待核。'),
'D049':('正文支持','正文明确讨论智能电网、PMU布置和网络攻击。'),
'D055':('疑似过度推断','正文是风力发电机恒频运行，甚至说明无需频率控制；Automatic frequency control不足以证明调度与灵活性研究。'),
'D058':('证据不足','正文讨论最优潮流与电压补偿，Reliability engineering条件词对供电可靠性主题的证据偏弱。'),
'D062':('正文支持','正文明确提出故障限流型超导电缆并分析限流性能，符合保护设备主题。'),
'D063':('疑似误分','正文开路电压约0.95—1.00 V；相对较高的光伏电压被标成High voltage，不能视为电网高电压研究。'),
'D064':('疑似误分','正文绝缘层用于光伏半导体背接触，来源Insulator (electricity)不能证明电力高压绝缘或局放。'),
'D067':('证据不足','题名是华东电网输配电展望，Transformer标签提供线索，但尚未逐项确认变压器研究内容。'),
'D069':('范围待定','正文为短电源线的多频段滤波和电磁兼容，广义供电相关；是否纳入电网输电线路专题需业务判断。'),
'D070':('正文支持','正文多导体线路时域仿真并与EMTP对照，支持线路分析主题。'),
'D072':('证据不足','题名只表明广域阻尼控制，HVDC应用需结合完整正文核实。'),
'D074':('证据不足','风能与电能质量控制相关，Converters词触发变换器主题；题名不足以确定变换器是研究对象。'),
'D081':('证据不足','燃料电池热电联产题名不能证明旋转发电机研究，Auxiliary power unit条件词偏宽。'),
'D086':('正文支持','正文明确提到提高制动再生效率，支持再生制动。'),
'D090':('范围待定','题名明确为植入医疗器械无线供能；技术上匹配，但电网招标业务是否需要此场景须单独筛选。'),
'D097':('疑似误分','正文研究太阳能蒸馏器，并未研究建筑；Passive solar building design标签疑似错配。'),
'D099':('证据不足','题名涉及冷却塔防冻，换热词提供关联，但能源应用范围需更完整内容确认。'),
'D113':('疑似过度推断','正文烟气再循环用于燃料利用率和抑制积碳；直接扩展成排放治理主题证据偏弱。'),
'D115':('证据不足','题名支持经济环境评估，具体碳核算或碳治理内容仍需全文确认。'),
'D123':('范围待定','芯片网络节能属于广义能效，不能自动当成电网能源业务的核心研究。'),
'D127':('正文支持','正文明确包含智能电表部署、计量数据管理与用户接受度。'),
'D132':('疑似过度推断','正文为SVM负荷预测，Nonlinear system是问题性质，不能独立证明优化与控制方法研究。'),
'D133':('证据不足','题名为SOI LDMOS高压互连效应，Telecommunications标签不足以证明能源通信网络应用。'),
'D134':('疑似过度推断','正文为托卡马克可见光成像诊断，Telecommunications标签不能证明通信或网络安全研究。'),
'D137':('疑似误分','正文为印度碳封存选项与政策前景，未见碳纤维研究；Carbon fibers标签疑似错配。'),
'D141':('背景关联','电弧炉粉尘是原料来源，题名主要研究废渣制铁酸锌；电热设备不是明确主要对象。'),
}

def main():
    c=connect();s=pd.read_parquet(WORK/'new_topic_samples.parquet')
    assert sha(WORK/'new_topic_samples.parquet')=='1c56d9d53cab5a796bf43baf70a846973bcd237c7cbb26532d744a03e8a59ce8', 'Sample changed: review the new evidence before publishing'
    assert len(s)==142
    # Guard key identities; this file is a human-readable record, not a classifier.
    assert 'stallion' in s.set_index('evidence_id').loc['D011','title']
    assert 'Shamrock' in s.set_index('evidence_id').loc['D063','title']
    assert 'Carbon Sequestration in India' in s.set_index('evidence_id').loc['D137','title']
    rows=[]
    for r in s.itertuples():
        status,note=NOTES.get(r.evidence_id,('题名支持','已阅读题名与触发词，二者支持该主题的初步关联；未据此断言是论文唯一或主要研究方向。'))
        rows.append({'evidence_id':r.evidence_id,'review_status':status,'review_note':note,
          'reviewer':'assistant','review_scope':'title_and_keyword_evidence; excerpts read for ambiguous cases',
          'expert_approved':False,'independent_blind_test':False})
    reviewed=pd.DataFrame(rows);reviewed.to_csv(WORK/'sample_review.csv',index=False,encoding='utf-8-sig')
    # Track the actual erroneous memberships that motivated the family gates.
    old=pd.read_parquet(WORK/'baseline_any_energy_anchor/new_topic_samples.parquet')
    chosen=old[old.evidence_id.isin(['D019','D020','D025','D026','D051','D061','D063','D086','D089','D098','D102','D107','D111'])].copy()
    chosen=chosen[['evidence_id','row_id','doc_id','title','topic_code']].rename(columns={'evidence_id':'initial_evidence_id'})
    c.register('old_debug_cases',chosen)
    fixes=c.execute('''SELECT o.*,e.row_id IS NOT NULL still_has_original_topic,
        a.topic_codes final_topic_codes,a.classification_status FROM old_debug_cases o
        JOIN assignments a USING(row_id) LEFT JOIN topic_relations e USING(row_id,topic_code)
        ORDER BY initial_evidence_id''').df()
    for col in ['final_topic_codes']:fixes[col]=fixes[col].map(lambda x:' | '.join(x))
    fixes.to_csv(WORK/'rule_refinement_regression.csv',index=False,encoding='utf-8-sig')
    previous=pd.read_parquet(WORK/'previous_audit_regression.parquet')
    selected=['P046','P062','P081','P083','P090','P093','P121','P124','P141']
    oldrefs=[]
    for r in previous[previous.evidence_id.isin(selected)].itertuples():
        oldrefs.append({'evidence_id':r.evidence_id,'doc_id':r.doc_id,'title':r.title,
           'classification_status':r.classification_status,'topic_codes':r.topic_codes.tolist(),
           'interpretation':'仍缺正确来源关键词，无法恢复真实能源主题' if r.evidence_id in ['P062','P093','P141'] else '此前不恰当的能源主题归属已不再触发；未强制回填'})
    badsource=[]
    for rowid in [2788864,4813066]:
        row=c.execute('SELECT doc_id,classification_status,topic_codes FROM assignments WHERE row_id=?',[rowid]).fetchone()
        words=c.execute('SELECT k.raw_name FROM observations o JOIN keyword_lookup k USING(keyword_id) WHERE o.row_id=? ORDER BY k.raw_name',[rowid]).fetchall()
        badsource.append({'doc_id':row[0],'classification_status':row[1],'topic_codes':row[2],
           'source_keywords':[x[0] for x in words],'interpretation':'电池论文的来源词缺电池信息，词典匹配无法找回；没有用题名暗中补词。'})
    before=json.loads((WORK/'baseline_any_energy_anchor/CLASSIFIED.json').read_text())['counts']
    after=json.loads((WORK/'CLASSIFIED.json').read_text())['counts']
    result={'summary':'逐主题调试抽样142条：修复了无关方向共现导致的部分误分，仍发现原始标签错配、多义词和条件词过宽。完整性校验通过；语义质量尚未验收通过。',
      'reviewed_relations':142,'topics_reviewed':71,'sample_status_counts':reviewed.review_status.value_counts().to_dict(),
      'reviewer':'assistant','expert_approved':False,'independent_blind_test':False,
      'sampling':'Two lowest md5(doc_id||topic_code||dictionary-review-v1) nonflagged paper relations per topic; a tuning sample, not a prevalence-weighted blind sample.',
      'before_any_anchor_rule':before,'after_related_anchor_rule_and_term_review':after,
      'rule_regressions_tested':len(fixes),'original_bad_relations_removed':int((~fixes.still_has_original_topic).sum()),
      'previous_nmf_regressions':oldrefs,'known_missing_keyword_references':badsource,
      'release_recommendation':'审阅与接入试用版；不要作为已完成语义验收的生产分类或据此直接发布热点/成熟度。',
      'next_unresolved_work':['逐项审核剩余长尾词；保留未确认词，不等同剔除范围外词。','用题名/摘要核对来源标签，处理高电压、绝缘、风电等已发现错配。','进一步收紧自动调频、非线性系统、通信等条件词。','按招标业务范围审核医疗供能、芯片节能等边界场景。']}
    write(WORK/'REVIEW.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
