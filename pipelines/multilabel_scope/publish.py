"""Publish a local, self-contained review bundle for the data-driven release."""
from run import *
import html

ASSETS=ROOT/'final/assets/nmf500_multilabel_scope'
PREVIEW=ROOT/'final/preview/nmf500_multilabel.html'
STATES={'keep_core':'核心保留','keep_supporting':'支撑·条件保留','review':'待审','exclude':'排除'}


def records(frame):return json.loads(frame.to_json(orient='records',force_ascii=False))


def main():
    valid=base.read(OUT/'VALIDATION.json');assert valid['passed']
    ASSETS.mkdir(parents=True,exist_ok=True)
    catalog=pd.read_csv(OUT/'topic_catalog_reviewed.csv')
    labels=pd.read_csv(OUT/'review/topic_display_labels.csv')
    catalog=catalog.merge(labels[['topic_id','display_name_zh','label_basis']],on='topic_id',how='left',validate='one_to_one')
    catalog['display_name']=catalog.display_name_zh.fillna(catalog.name)
    catalog['scope_display']=catalog.scope_state.map(STATES)
    catalog.to_csv(ASSETS/'topic_catalog.csv',index=False,encoding='utf-8-sig')
    sensitivity=pd.read_csv(OUT/'threshold_scope_sensitivity.csv')
    counts=pd.read_csv(OUT/'topic_counts_by_source_threshold.csv')
    evidence=pd.read_parquet(OUT/'review/topic_evidence.parquet')
    source_cases=pd.read_csv(OUT/'review/cross_source_case_review.csv')
    projection=pd.read_csv(OUT/'transfer/projection_diagnostics.csv')
    selection=base.read(OUT/'transfer/TRANSFER_SELECTION.json')
    confirmed=projection[(projection.neighbors==selection['neighbors'])&(projection.split=='confirmation')&(projection.threshold==.10)&(projection.similarity_gate==selection['similarity_gate'])].iloc[0]
    protocol=base.read(OUT/'PROTOCOL.json')
    summary={'release_id':'nmf500_multilabel_scope_20261019','k':500,'default_threshold':.10,
        'thresholds':[.05,.10,.15],'source_records':{'paper':4831088,'patent':281295,'policy':6621},
        'scope_counts':catalog.scope_state.value_counts().to_dict(),'retained_topic_count':int(catalog.scope_state.isin(['keep_core','keep_supporting']).sum()),
        'scope_review_authority':'助手初审；尚未经过领域专家批准','records_physically_deleted':0,
        'cross_source_status':'语义迁移候选，需审核；不是专利/政策的直接NMF贡献或准确率',
        'projection_confirmation_f1_against_paper_nmf':float(confirmed.membership_f1_against_nmf),
        'projection_confirmation_precision_against_paper_nmf':float(confirmed.membership_precision_against_nmf),
        'projection_confirmation_recall_against_paper_nmf':float(confirmed.membership_recall_against_nmf),
        'known_rejected_relations':5,'existing_hotspot_or_maturity_results_recomputed':False,
        'topic_ids':'RBK500-T0001–RBK500-T0500; new full-data model, not old F IDs or sample-model IDs',
        'label_note':'118个核心中文名来自现有主题与抽样内容的一对一描述，不改变模型或归属。其他主题保留原始关键词名。'}
    data={'summary':summary,'topics':records(catalog),'threshold_statistics':records(sensitivity),'topic_counts':records(counts),
        'topic_evidence':records(evidence),'cross_source_case_review':records(source_cases),'projection_diagnostics':records(projection),
        'validation':valid,'protocol':protocol}
    write(ASSETS/'platform_data.json',data)
    for src,name in [(OUT/'threshold_scope_sensitivity.csv','threshold_scope_sensitivity.csv'),
        (OUT/'topic_counts_by_source_threshold.csv','topic_counts_by_source_threshold.csv'),
        (OUT/'review/topic_scope_decisions.csv','topic_scope_decisions.csv'),
        (OUT/'review/topic_display_labels.csv','topic_display_labels.csv'),
        (OUT/'review/relation_review_overrides.csv','relation_review_overrides.csv'),
        (OUT/'review/cross_source_case_review.csv','cross_source_case_review.csv'),
        (OUT/'assignment_status_counts.csv','assignment_status_counts.csv'),
        (OUT/'VALIDATION.json','VALIDATION.json'),(OUT/'PROTOCOL.json','PROTOCOL.json')]:shutil.copy2(src,ASSETS/name)
    notes=pd.DataFrame([
        ('建模与编号','4,637,813篇剩余非零关键词论文参与K=500全量训练，5轮，seed17。删除名单仍为前次20个学科大类；新ID不能直接关联旧F主题、热点或成熟度。'),
        ('贡献','论文p=W*L2(H)/sum(W*L2(H))，处理NMF缩放不定性。贡献不是概率，也不是能源相关度。'),
        ('多主题规则','贡献>=阈值的关系均为原始归属，不设Top-N上限，不强制argmax。提供5%、10%、15%三档；10%是工作默认值，不是专家验证最优值。'),
        ('范围','核心保留、支撑条件保留、待审、排除。500项均由助手读取关键词与首轮抽样题名作初审，争议主题补读摘要；未声称人类专家批准。'),
        ('支撑主题逐记录检查','完整冻结标题/正文命中公开能源词规则，或同时达到同一阈值的核心主题，才保留支撑关系；未命中不等于无关，进入待审。该规则偏重中文/英文，多语种记录可能漏检。'),
        ('不重新归一化','主题排除、记录待审和已知关系拒绝都不改变原始贡献。其他保留关系继续有效。'),
        ('交叉计数','同一记录可同时有保留、待审和排除关系。各状态覆盖文献数不可相加；全平台文献量按doc_id去重。主题规模另列贡献加权量。'),
        ('专利与政策','从192,563篇训练样本池中的有效参考论文，以BGE语义近邻迁移主题分布；实际有效参考数见REFERENCE_COMPLETE。选10邻居、温度0.05、相似度门槛0.55。不是直接NMF推断。'),
        ('迁移检验','在与参考论文身份不重叠的20,000篇论文上，前10,000选择邻居数、后10,000报告一致性。全量NMF看过这些论文，因此仅检验语义投影，不是未见NMF泛化或跨来源语义准确率。'),
        ('迁移质量边界',f'10%阈值、0.55相似度门槛下，一致性F1={confirmed.membership_f1_against_nmf:.3f}，precision={confirmed.membership_precision_against_nmf:.3f}，recall={confirmed.membership_recall_against_nmf:.3f}。尚不足以把迁移结果当正式分类真值；专利政策均标记候选。'),
        ('已发现误配','18条专利政策案例补读后，对油气加药装置→燃料电池/污水处理、导热封装→电解质等共5条关系作拒绝并留痕。未把少量案例当总体准确率。'),
        ('词义与名称','Lithium (medication)、Control theory (sociology)等词义错误尚在输入中。中文展示名改善阅读但不声称已修复这些输入问题。'),
        ('待审反例','妇科/传统医学名称下存在可再生供热、能源作物、矩阵变换器等记录；染料降解主题有光燃料电池反例，因此保持待审而未整类删除。'),
        ('未完成的专家工作','主题范围、专利政策语义准确率尚未进行领域专家盲审；没有估计整体语义准确率。'),
        ('下游','本轮生成多主题与范围筛选版本及接口。旧F主题热点、趋势和TRL/CRL尚未按新归属重算；禁止按相同序号直接复用。')],columns=['项目','说明'])
    with pd.ExcelWriter(ASSETS/'K500多主题归属与范围审核.xlsx',engine='openpyxl') as writer:
        sheets=[('500主题与范围',catalog),('阈值与范围影响',sensitivity),('主题分来源计数',counts),('主题论文抽样',evidence),
            ('专利政策案例',source_cases),('已拒绝关系',pd.read_csv(OUT/'review/relation_review_overrides.csv')),
            ('迁移一致性诊断',projection),('文献最终状态',pd.read_csv(OUT/'assignment_status_counts.csv')),('方法与边界',notes),
            ('程序校验',pd.DataFrame(valid['checks'].items(),columns=['检查','通过']))]
        for name,frame in sheets:
            frame.to_excel(writer,sheet_name=name,index=False);ws=writer.book[name];ws.freeze_panes='B2';ws.auto_filter.ref=ws.dimensions
            for column in ws.columns:
                ws.column_dimensions[column[0].column_letter].width=min(60,max(18,len(str(column[0].value))+3))
                for cell in column:
                    if isinstance(cell.value,str):cell.data_type='s'
    default=sensitivity[(sensitivity.threshold==.10)&sensitivity.stage.isin(['quality_qualified','retained'])]
    code=str(ROOT/'final/energy-topic-identification/pipelines/multilabel_scope')
    doc='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>K500多主题归属与范围审核说明</title><style>body{font-family:system-ui;line-height:1.8;max-width:1150px;margin:36px auto;padding:0 20px;color:#203545}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-bottom:1px solid #dce5ed;text-align:left;padding:10px;vertical-align:top}th{background:#edf4f7}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf4f7;padding:18px}a{color:#006c83}</style>'''
    doc+='<h1>K=500 多主题归属与能源范围审核</h1><p>本轮已完成全量模型、三档阈值归属、主题范围初审与可追溯筛选。没有物理删除原始记录。专利和政策为语义迁移候选，仍需内容审核。</p>'
    doc+='<p><a href="../../preview/nmf500_multilabel.html">打开交互审阅</a> · <a href="K500多主题归属与范围审核.xlsx">下载审阅工作簿</a> · <a href="platform_data.json">机器可读接口包</a></p>'
    doc+='<h2>10%阈值下的实际覆盖</h2>'+default.to_html(index=False,border=0,float_format=lambda x:f'{x:,.4f}')
    doc+='<p>quality_qualified为质量门槛及已知关系拒绝之后、范围筛选之前；retained为最终业务关系。支撑主题还需能源应用线索。不同状态可覆盖同一文献，不能相加。</p>'
    doc+='<h2>方法、审核与适用边界</h2>'+notes.to_html(index=False,border=0)
    doc+='<h2>数据文件</h2><pre>'+html.escape(json.dumps({'topic_catalog':str(ASSETS/'topic_catalog.csv'),'scope_ledger':str(OUT/'review/topic_scope_decisions.csv'),
        'document_memberships':str(OUT/'business_assignments/*.parquet'),'all_edges_ge_005':str(OUT/'business_edges_ge_005/*.parquet'),
        'paper_raw_memberships':str(OUT/'full_model/paper_assignments/*.parquet'),'transfer_evidence':str(OUT/'transfer/assignments/*.parquet'),
        'model':str(OUT/'full_model/model.joblib')},ensure_ascii=False,indent=2))+'</pre>'
    doc+='<h2>查询与复现</h2><p>在项目根目录使用 .venv-hotspots/bin/python。修改范围清单后重新运行 apply_scope.py、validate.py、publish.py；审阅清单是版本输入，重训不会自动替代它。相同方法重训后的主题ID可能变化，应重新审核。</p><pre>'+html.escape('\n'.join([
        f'.venv-hotspots/bin/python {code}/query.py patent26:855781b3efb40f04fe7ce65e --threshold 0.10',
        f'.venv-hotspots/bin/python {code}/run.py train-papers',f'.venv-hotspots/bin/python {code}/transfer.py run',
        f'.venv-hotspots/bin/python {code}/review.py packet',f'.venv-hotspots/bin/python {code}/apply_scope.py',
        f'.venv-hotspots/bin/python {code}/validate.py',f'.venv-hotspots/bin/python {code}/publish.py']))+'</pre>'
    doc+='<p>业务归属字段：topic_ids为零起始整数；显示编码从topic_catalog映射。topic_contributions保留原始值；scope_review_topic_ids、excluded_topic_ids及rejected_relation_count保留筛选去向。requires_semantic_review为专利政策候选标识。其他阈值的支撑主题条件应重新计算核心共属，使用query.py，不可直接复用10%布尔字段。</p></html>'
    (ASSETS/'使用与接入说明.html').write_text(doc)
    template=(Path(__file__).parent/'preview.html').read_text()
    compact={key:data[key] for key in ['summary','topics','threshold_statistics','topic_counts','topic_evidence','cross_source_case_review']}
    payload=json.dumps(compact,ensure_ascii=False,separators=(',',':'),allow_nan=False).replace('<','\\u003c')
    PREVIEW.write_text(template.replace('__DATA__',payload))
    manifest={'release_id':summary['release_id'],'status':'local_review_release','validation_passed':True,'preview':str(PREVIEW),
        'assets':str(ASSETS),'work_dir':str(OUT),'score_kinds':{'paper':'nmf_l2_relative_contribution','patent':'semantic_neighbor_transfer_contribution','policy':'semantic_neighbor_transfer_contribution'},
        'scope_ledger_sha256':sha(OUT/'review/topic_scope_decisions.csv'),'relation_review_sha256':sha(OUT/'review/relation_review_overrides.csv'),
        'files':{p.name:sha(p) for p in ASSETS.iterdir() if p.is_file() and p.name!='RELEASE.json'},
        'pipeline_sources':{p.name:sha(p) for p in Path(__file__).parent.glob('*.py')},'existing_F500_results_replaced':False}
    write(ASSETS/'RELEASE.json',manifest);write(OUT/'RELEASE_COMPLETE.json',manifest)
    write(ROOT/'final/config/nmf500_multilabel_release.json',{'schema_version':1,'release_id':summary['release_id'],
        'data_json':'../assets/nmf500_multilabel_scope/platform_data.json','preview':'../preview/nmf500_multilabel.html',
        'membership_dir':'../../work/nmf500_multilabel_scope_20261019/business_assignments',
        'default_threshold':.10,'old_F_ids_compatible':False,'cross_source_candidates_only':True})
    print(default.to_string(index=False));print('PUBLISHED',ASSETS)


if __name__=='__main__':main()
