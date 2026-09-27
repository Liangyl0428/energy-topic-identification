"""生成 Git 可见文件的带用途结构图（不包含本地语料和运行产物）。"""
from pathlib import Path
import argparse
import subprocess

ROOT=Path(__file__).resolve().parents[1]
NAMES={
 'assets':'发布用的紧凑结果；不是原始语料', 'full_nmf500':'当前全量 500 主题流程或成果',
 'experiments':'已完成消融与灵敏度实验的表格、报告和校验记录',
 'pipelines':'计算与复现入口', 'full_nmf':'当前全量主流程',
 'tests':'自动化测试及固定输入', 'fixtures':'仅用于兼容回归，不代表当前成果',
 'nmf500':'共享计算模块或固定回归流程；当前入口见 full_nmf',
 'nmf500_results':'成熟度回归期望输出', 'snapshot_20260925':'固定回归输入快照',
 'keyword_nmf':'关键词矩阵与 NMF 共享组件及兼容回归',
 'embedding':'向量编码与池化兼容组件', 'topic_modeling':'主题组件兼容回归代码；不是全量生产入口',
 'hotspots':'多年份和潜在关联兼容回归实现',
 'src':'可导入的算法模块', 'energy_hotspots':'热点评分、命令行及离线回放包',
 'trl_crl':'成熟度双轴评估引擎', 'data':'有边界的成熟度证据输入，必须保留',
 'docs':'方法、数据、复现与目录说明', 'tools':'发布校验、清单及维护工具',
 'provenance':'文件指纹与审计元数据', '.github':'远端自动化配置', 'workflows':'持续集成工作流',
 'README.md':'项目入口：当前方法、结果及运行说明', 'REPORT.md':'面向读者的结果报告',
 'PROJECT_STRUCTURE.md':'本文件：全部受版本管理文件的用途索引',
 'METHOD.md':'当前算法与适用边界', 'ALGORITHM.md':'评分算法说明',
 'REPRODUCING.md':'环境、输入和复现步骤', 'CORE_FILES.md':'核心文件与外部大文件边界',
 'FULL_NMF.md':'全量主题流程说明', 'FULL_EXPERIMENTS.md':'实验设计和解释限制',
 'RESULTS.md':'结果说明', 'DATA_SCHEMA.md':'数据字段约定', 'DATA_DICTIONARY.md':'字段解释',
 'NOTICE.md':'数据来源和使用声明', '.gitignore':'排除缓存、本地大数据和运行输出',
 '.gitattributes':'Git 文本与二进制属性', 'pyproject.toml':'包元数据、依赖与命令入口',
 'MANIFEST.in':'源码分发包含文件规则', 'CORE_FILES.json':'当前核心文件完整性清单',
 'MANIFEST.json':'当前发布结果的 SHA-256 指纹', 'COMPLETE.json':'完成标记、输入绑定和输出指纹',
 'SUMMARY.json':'机器可读统计摘要', 'PROTOCOL.json':'实验参数、范围、限制与输入指纹',
 'VALIDATION.json':'数据完整性检查结果', 'POSTPROCESS_DELIVERY.json':'三仓库交付及实验绑定记录',
 'TRAINING_COMPLETE.json':'训练配置、轮次诊断及模型指纹',
 'INFERENCE_COMPLETE.json':'全量论文推断完成记录', 'ENCODING_COMPLETE.json':'全量编码完成记录',
 'VOCABULARY_COMPLETE.json':'词表拟合范围与参数', 'ASSIGNMENTS_MANIFEST.json':'本地逐条分类分片指纹',
 'QUALITY_DIAGNOSTICS.json':'类别规模和中心重叠诊断，非准确率',
 'coverage.csv':'按来源统计输入、已分类与未分类数量', 'topic_catalog.csv':'主题编号、关键词与规模',
 'topic_assignment_quality.csv':'逐主题分类差距与几何诊断',
 'hotspot_metrics.csv':'各主题热点得分、门槛和数值候选资格',
 'quarter_counts.csv':'各主题季度论文数量', 'institution_citation_context.csv':'机构广度与引用背景',
 'cross_source_signals.csv':'论文、专利和政策共同窗口信号',
 'transfer_source_summary.csv':'专利政策匹配统计', 'core_components.csv':'核心热点评分分量',
 'emerging_components.csv':'新兴热点评分分量', 'scenarios.csv':'逐消融与门槛情景的候选和排序变化',
 'weight_draws.csv':'随机权重扰动结果', 'rank_intervals.csv':'逐主题扰动排名范围',
 'scenario_memberships.csv':'逐情景候选成员名单', 'data_filter_counts.csv':'文本过滤后的实际记录数量',
 'policy_document_loo.csv':'逐篇撤回政策后的候选资格',
 'potential_association_baseline.csv':'跨来源潜在关联基准指标',
 'evidence_scenarios.csv':'逐证据撤回情景的双轴变化', 'case_fragility.csv':'逐案例证据依赖程度',
 'full_topic_case_fragility.csv':'连接当前主题的案例证据依赖',
 'mapping_sensitivity.csv':'主题关联参数网格及覆盖变化',
 'theme_context_top3.csv':'案例和技术方向的前三个候选主题',
 'case_hotspot_links.csv':'案例与热点指标连接', 'theme_evidence_profiles.csv':'各主题可检索证据概况，不是主题等级',
 'objects.json':'成熟度评估案例边界', 'sources.json':'证据来源登记', 'evidence.json':'证据段落与可知日期',
 'observations.json':'从证据提取的事实观察', 'gate_reviews.json':'成熟度门槛审核决定',
 'technical_profiles.json':'案例技术任务与边界画像', 'observed_facts.json':'规范化事实登记',
 'technology_registry.json':'技术方向登记', 'themes.json':'证据库主题实体',
 'theme_direction_links.json':'主题与技术方向关系', 'case_technology_links.json':'案例与技术对象关系',
 'dataset.json':'证据数据集元信息',
 'run.py':'编排全量分类与下游计算', 'prepare.py':'全量清洗、关键词统计与矩阵构建',
 'train.py':'全量 NMF 分批训练与论文推断', 'fast_nmf.py':'NMF 数值计算与批处理加速',
 'finalize.py':'主题中心、跨来源分类与全量校验', 'after_full.py':'实验、校验和三仓库交付编排',
 'publish_local.py':'将紧凑成果发布到仓库 assets', 'resume_delivery.py':'安全恢复未完成交付',
 'status.py':'读取阶段标记显示进度', 'optimize_encoder.py':'优化编码模型运行格式',
 'report.py':'生成人类可读结果报告', 'experiments.py':'执行消融及灵敏度实验',
 'build.py':'构建本阶段计算结果', 'common.py':'公共路径、配置和辅助函数',
 'encode.py':'批量文本向量编码', 'encode_context.py':'编码案例和技术方向以关联主题',
 'mapping.py':'候选主题相似度匹配及边界约束', 'engine.py':'逐对象双轴成熟度推理',
 'rules.py':'TRL/CRL 门槛规则', 'pipeline.py':'数据加载、评估与成果输出',
 'research.py':'研究证据整理辅助', 'scoring.py':'核心与新兴热点评分、门槛和确定性排序',
 'cli.py':'命令行参数与入口', '__main__.py':'模块命令行入口', '__init__.py':'Python 包初始化',
 'replay.py':'固定输入的离线兼容回放', 'replay_snapshot.py':'兼容快照回放编排',
 'check_current_release.py':'校验核心代码、成果指纹和文档链接',
 'check_release.py':'检查发布文件、二进制白名单及数据约束',
 'validate_release.py':'发布完整性校验入口', 'update_release_manifest.py':'更新发布文件指纹',
 'project_structure.py':'重建本结构图及逐文件用途', 'build_release.py':'源码发布包构建工具',
 'bind_review_scopes.py':'将审核记录绑定到明确对象边界',
 'conftest.py':'测试共享配置',
}


NAMES.update({'download_encoder.py': '下载固定修订的兼容编码器权重；不是当前 BGE-M3 下载入口', 'embedding_common.py': '兼容编码流程的路径、文本清洗和文件校验函数', 'pool_encoder.py': '为兼容 ONNX 编码器增加池化与归一化输出', 'components.py': '可复用主题模型、指标和分类组件；关键词组件被当前全量流程直接调用', 'run_pipeline.py': '关键词矩阵构建、NMF 拟合和回归所需辅助函数', 'selection_experiments.py': '固定回归指标的权重与选择敏感性检查，不是当前成果报告', 'candidate_common.py': '兼容候选模型的路径、主题数和随机种子配置', 'experiment_components.py': '重用逐文档词频缓存的主题模型组件', 'lexical.py': '中英文分词与词项分析器', 'topic_common.py': '兼容主题流程的路径、文本和校验工具', 'train_baseline.py': '兼容主题训练与流式计数实现，供组件回归使用', 'train_candidates.py': '兼容候选主题模型训练实现，非当前生产入口', 'multiyear_build.py': '兼容回归的多年季度计数与背景数据构建', 'multiyear_delivery.py': '兼容回归表格和交付产物生成', 'multiyear_experiments.py': '兼容回归的多年热点消融及敏感性计算', 'multiyear_finalize.py': '兼容回归结果整理和最终输出', 'multiyear_plots.py': '兼容回归的热点趋势和实验图表', 'multiyear_scoring.py': '兼容回归的多年热点评分', 'multiyear_validate.py': '兼容回归结果约束与完整性检查', 'potential_delivery.py': '兼容回归的潜在关联表格输出', 'potential_experiments.py': '兼容回归的潜在关联消融实验', 'potential_unified.py': '兼容回归的跨来源潜在关联计算', 'potential_unified_metrics.py': '兼容回归的跨来源指标与过滤条件', 'review.py': '候选主题范围及语义审核应用', 'review_contract.py': '审核决定的输入绑定和有效性约束', 'validate.py': '固定回归输出的数据约束检查', 'weight_summary.csv': '各类随机权重扰动的汇总统计', 'changed_cases.csv': '逐实验情景发生等级变化的案例及变化内容'})

def purpose(rel,is_dir=False):
    p=Path(rel)
    if rel.startswith('tests/fixtures/'):
        return '固定回归'+('目录' if is_dir else '输入/期望值')+'；不作为当前结果使用'+('：'+NAMES[p.name] if p.name in NAMES and not is_dir else '')
    if p.name in NAMES:return NAMES[p.name]
    if p.name.startswith('test_'):return '回归测试：'+p.stem[5:].replace('_',' / ')
    if p.name.startswith('requirements'):return '运行/测试依赖版本约束（用途由文件后缀区分）'
    if rel.startswith('.github/'):return '自动安装依赖并运行测试和校验'
    if p.suffix=='.py':
        return '兼容回归辅助：'+p.stem.replace('_',' / ')+'；保留用于依赖链或测试'
    if rel.startswith('provenance/'):return '发布或回归审计记录：'+p.stem.replace('_',' / ')
    if 'context' in p.stem:return '实验各条件的机构/引用背景数据'
    if 'quarter' in p.stem:return '实验各条件的季度计数数据'
    if 'review_decisions' in p.stem:return '固定回归审核决定；不得继承为当前主题审核结论'
    return ('目录：' if is_dir else '结果/配置：')+p.stem.replace('_',' / ')


def render(root=ROOT):
    files=set(subprocess.check_output(['git','-C',str(root),'ls-files','--cached','--others','--exclude-standard','-z']).decode().split('\0'))-{''}
    files={p for p in files if (root/p).is_file()}
    files.add('docs/PROJECT_STRUCTURE.md')
    tree={}
    for rel in sorted(files):
        branch=tree
        for part in Path(rel).parts:branch=branch.setdefault(part,{})
    lines=[root.name+'/  # 当前发布源码与紧凑成果']
    def walk(branch,prefix='',base=''):
        entries=sorted(branch.items(),key=lambda x:(not bool(x[1]),x[0]))
        for i,(name,children) in enumerate(entries):
            last=i==len(entries)-1;rel=base+name
            lines.append(prefix+('└── ' if last else '├── ')+name+('/' if children else '')+'  # '+purpose(rel,bool(children)))
            if children:walk(children,prefix+('    ' if last else '│   '),rel+'/')
    walk(tree)
    report='assets/full_nmf500/REPORT.md'
    experiment=report if root.name.endswith('identification') else 'assets/full_nmf500/experiments/REPORT.md'
    text='# 项目结构与逐文件用途\n\n## 从哪里开始\n\n当前计算入口是 `pipelines/full_nmf/`，当前成果仅在 `assets/full_nmf500/`。`tests/fixtures/` 是固定回归输入，不是另一套待选用成果。共享模块和兼容实现因当前调用或测试需要而保留，不应直接替代全量入口。\n\n'
    text+='阅读 [当前报告](../'+experiment+')、[方法](METHOD.md) 和 [复现步骤](REPRODUCING.md)。下面逐项列出全部 Git 管理的文件及目录，不用省略号隐藏文件。\n\n## 完整结构图\n\n```text\n'+'\n'.join(lines)+'\n```\n\n'
    text+='## 不随仓库发布的本地内容\n\n`work/`、`outputs/` 或 `results/` 中的全量运行目录保存训练权重、向量、逐条分类、数据库和日志；原始文献及编码器权重也属于外部运行输入。这些文件体量大，不是本结构图漏列的源码，具体输入位置与生成步骤见复现说明。删除仓库中的旧发布快照不会删除这些运行数据。\n\n## 维护本图\n\n新增、移动或删除文件后运行 `python tools/project_structure.py`。只扫描 Git 可见文件，不扫描原始语料；发布前还应运行核心文件校验。每个文件名后为其作用；测试数据不可用于宣称当前模型效果。\n'
    (root/'docs/PROJECT_STRUCTURE.md').write_text(text)
    return files


if __name__=='__main__':render()
