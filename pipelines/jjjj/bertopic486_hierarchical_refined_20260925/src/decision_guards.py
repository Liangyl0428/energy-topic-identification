"""Second-pass linguistic precision checks, recorded separately from initial routing."""
from refine_common import *

TITLE_GUARDS={
    'M389.shipping':(re.compile(r'\bships?\b|\bshipping\b|\bmaritime\b|船舶|航运',re.I),'shipping必须是船舶词，不能命中relationship等词内片段'),
    'M361.knowledge_graph':(re.compile(r'\bpower\b|\belectric(?:al|ity)?\b|电力|电网',re.I),'电力知识图谱必须明确电力对象，不能命中powerful等词内片段'),
    'M062.pyrolysis':(re.compile(r'\bbiomass\b|\bwood\b|\bwoody\b|生物质|木质',re.I),'木质对象必须是独立词，不能命中Sherwood等术语'),
    'M049.gel':(re.compile(r'\bgel\b|hydrogel|凝胶',re.I),'凝胶相须有明确表述，不能仅由gelatin等材料名推断'),
    'M033.sludge_dewatering':(re.compile(r'\bdewatering\b|dewaterability|\bconditioning\b|脱水|调理',re.I),'conditions或作为原料的dewatered sludge不能替代脱水/调理任务'),
    'M007.coating':(re.compile(r'slurry|calender|slot.die|roll.to.roll|coating.(?:process|machine|equipment|uniformity|thickness)|涂布|辊压|浆料',re.I),'电极涂布制造须有工艺证据；材料表面包覆不足以接受'),
    'M101.switchgear':(re.compile(r'diagnos|fault.detect|fault.identif|condition.monitor|故障检测|故障诊断|状态监测',re.I),'短路电流应力并非开关设备故障诊断'),
    'M127.graphene_membrane':(re.compile(r'\bmembranes?\b|分离膜|石墨烯膜',re.I),'脱盐不等于膜分离，须有明确膜对象'),
    'M141.rotor':(re.compile(r'design|structur|manufactur|fabricat|topolog|设计|结构|制造|加工',re.I),'仅提及转子不足以证明结构设计或制造任务'),
    'M141.stator':(re.compile(r'design|structur|manufactur|fabricat|topolog|设计|结构|制造|加工',re.I),'仅提及定子不足以证明结构设计或制造任务'),
    'M492.winding':(re.compile(r'manufactur|fabricat|winding.machine|coil.winding|winding.design|绕线|绕组制造|绕组设计|线圈制造|线圈加工',re.I),'仅使用电机绕组不是绕组制造研究'),
    'M169.ecm':(re.compile(r'equivalent.circuit|Thevenin|Rint|电路模型|等效电路',re.I),'一般非线性系统参数估计不能当作电池等效电路'),
    'M142.islanding':(re.compile(r'control|transition|switching|stabil|transient|控制|切换|稳定|暂态',re.I),'islanded只说明运行场景，不能替代动态控制任务'),
    'M226.water':(re.compile(r'adsorp|remov|degrad|decontamin|remediat|pollutant|吸附|去除|降解|修复|污染物',re.I),'生物炭在废水中促进产气不能据此认作污染物去除'),
    'M253.location':(re.compile(r'\blocations?\b|\bsiting\b|\bplacement\b|选址|站点规划',re.I),'选址须为独立词；displacement或allocation不等于选址'),
    'M268.proton_membrane':(re.compile(r'membrane.{0,40}(?:material|composite|conductiv|propert|develop|fabricat|synthes)|(?:composite|hybrid|sulfonat|sulphonat|Nafion|SPEEK|polybenzimidazole).{0,60}membrane|质子.{0,8}膜材料|膜.{0,20}(?:制备|合成|改性|复合|电导)|(?:制备|合成|改性|复合).{0,20}膜',re.I),'质子交换膜燃料电池系统名称不能当作膜材料研究证据'),
    'M290.fusion':(re.compile(r'engineering|design|construction|blanket|first.wall|divertor|vacuum.vessel|reactor.material|shielding|工程|设计|建造|包层|第一壁|偏滤器|真空室|屏蔽',re.I),'托卡马克等离子体过程不能仅因装置名称归入装置工程'),
    'M439.ewaste':(re.compile(r'\belectronic.waste\b|\be.waste\b|\bWEEE\b|电子废物|电子垃圾',re.I),'电子废物须有完整对象，不能命中temperature waste等词尾'),
    'M397.hydropower_dispatch':(re.compile(r'dispatch|schedul|调度',re.I),'一般设备运行维护不是水电调度'),
    'M150.carbon_capture':(re.compile(r'porous.carbon|activated.carbon|carbon.aerogel|carbon.sorbent|carbon.adsorbent|biochar|carbonaceous|多孔碳|多孔炭|活性炭|生物炭|碳气凝胶',re.I),'carbon dioxide中的carbon不能充当多孔碳材料对象'),
    'M459.risk_warning':(re.compile(r'power.equipment|electrical.equipment|transformer|switchgear|circuit.breaker|power.line|电力设备|电气设备|配电设备|输电设备|变压器|开关柜|输电线路',re.I),'须明确被评估电力设备；专利的“方法系统设备介质”尾缀不构成设备对象'),
    'M003.offshore_economics':(re.compile(r'economic|\bcost|financ|\binvest(?:ment|ing|or|ors|ments)?\b|\bmarket|LCOE|deploy|development.polic|经济|成本|开发规划|投资|部署',re.I),'技术系统的development/investigation不能替代海上风电开发经济研究'),
    'M034.water_heating':(re.compile(r'water[ -]?heat(?:er|ing)|space[ -]?heating|热水|供热|采暖',re.I),'water-heat management不是热水器或供热任务'),
    'M055.dispatch':(re.compile(r'\bdispatch(?:ing)?\b|schedul|arbitrage|调度|套利',re.I),'non-dispatchable等描述不能替代储能调度任务'),
    'M085.fault':(re.compile(r'\bfault|diagnos|defect.detect|defect.inspect|defect.identif|detect.{0,20}defect|故障|缺陷检测|缺陷识别|缺陷诊断',re.I),'材料深能级缺陷与器件结构缺陷不等于组件故障检测'),
    'M085.degradation':(re.compile(r'modules?|panels?|arrays?|photovoltaic.system|PV.system|组件|光伏板|光伏系统|阵列',re.I),'光伏组件退化须有组件/系统对象，不能泛指吸收层或单个材料'),
    'M101.transformer':(re.compile(r'power.transformer|distribution.transformer|electrical.transformer|oil.immersed|transformer.oil|transformer.winding|transformer.fault|faults?.{0,15}(?:in|of).{0,8}transformer|变压器',re.I),'Transformer机器学习模型不是电力变压器，须有明确物理对象'),
    'M175.short_circuit':(re.compile(r'calculat|estimat|analysis|assess|计算|估计|分析|评估|等值',re.I),'短路电流限制控制不能替代短路电流计算任务'),
    'M206.aging':(re.compile(r'\baging\b|\bageing\b|\bcycle.life\b|\bcalendar.life\b|老化|循环寿命',re.I),'aging须为独立词，不能命中imaging或leveraging'),
    'M239.rooftop':(re.compile(r'deploy|install|planning|potential|adopt|siting|capacity|penetration|assessment|impact|integration|安装|部署|规划|潜力|接入|容量|渗透|影响|评估',re.I),'屋顶场景本身不足以证明部署/规划任务'),
    'M324.adsorption':(re.compile(r'\badsorp|\badsorb|\bsorbents?\b|吸附',re.I),'absorbent不能以词内sorbent自动当作固体吸附剂'),
    'M323.mhd':(re.compile(r'tokamak|stellarator|fusion|magnetic.confinement|toroidal|spheromak|divertor|聚变|托卡马克|磁约束|环形约束|偏滤器',re.I),'一般或天体等离子体MHD不能直接认作磁约束稳定性'),
    'M483.integration':(re.compile(r'system.integrat|integrated.design|hybrid.energy.storage|energy.storage.cabinet|battery.system.integrat|储能系统集成|储能柜|集成装置|集成系统|消防|\bsafety\b|fire.prot',re.I),'储能参与市场或可再生能源接入不能仅凭integration认作储能设备集成'),
    'M347.gasification':(re.compile(r'\bbiomass\b|\b(?:wood|woody|hardwood|softwood|sawdust)\b|生物质|木质',re.I),'生物质气化须有完整原料对象，不能由Sherwood等词内wood推断'),
    'M015.algal_biofuel':(re.compile(r'\balgae\b|\balgal\b|microalga|macroalga|藻',re.I),'藻类须有明确对象，不能由amalgam等词内片段推断'),
    'M307.led_lighting':(re.compile(r'(?<![A-Za-z])LEDs?(?![A-Za-z])|light.emitting.diode|发光二极管',re.I),'LED须为独立缩写，不能由controlled等词尾推断'),
    'M324.absorption':(re.compile(r'\babsorp|solvent|aqueous.{0,60}amine|solution.{0,45}amine|胺溶液|吸收|溶剂',re.I),'胺功能化材料不必然是溶剂吸收，须有明确液相/吸收任务'),
}
EXCLUDE_GUARDS={
    'M048.binder':(re.compile(r'binder[\s-]*free|without.{0,12}binder|无粘结剂|无黏结剂|免粘结剂',re.I),'无粘结剂电极不自动归为粘结剂材料研究'),
    'M027.charger_thermal':(re.compile(r'battery.cool|battery.thermal|cooling.{0,20}batter|电池冷却|电池热管理|电池散热',re.I),'电池冷却不能替代充电设施本体散热'),
    'M062.pyrolysis':(re.compile(r'toxic|cytotoxic|genotoxic|cultured.cell|毒性|毒理',re.I),'热解产物毒理研究与热解工艺的主任务不同'),
    'M049.solid':(re.compile(r'quasi.solid|gel|准固态|凝胶',re.I),'准固态或凝胶电解质不强分入全固态子类'),
    'M141.rotor':(re.compile(r'diagnos|fault|insulation|parameter.identif|故障|诊断|绝缘|参数辨识',re.I),'转子故障/绝缘表征任务不能替代制造设计'),
    'M141.stator':(re.compile(r'diagnos|fault|insulation|parameter.identif|故障|诊断|绝缘|参数辨识',re.I),'定子故障/绝缘表征任务不能替代制造设计'),
    'M142.islanding':(re.compile(r'dispatch|schedul|economic|调度|经济',re.I),'孤岛微网调度与动态控制可能交叉，保留复核'),
    'M226.water':(re.compile(r'methane.production|biogas|anaerobic.digestion|产甲烷|产沼气|厌氧消化',re.I),'生物炭助力厌氧产气与去污任务交叉，保留复核'),
    'M279.graphite':(re.compile(r'silicon|SiOx|Si/C|硅',re.I),'硅石墨复合负极不强制作为单一石墨负极子类'),
    'M379.module':(re.compile(r'disassembl|拆解|拆卸',re.I),'拆解任务不是电池包装配结构'),
    'M390.cable_support':(re.compile(r'cableway|suspension.bridge|索道|缆道|斜拉桥',re.I),'机械钢索支撑不是电缆桥架或线束'),
    'M264.cover':(re.compile(r'inspection|diagnos|检测方法|检验方法|诊断',re.I),'端子检测不能仅凭端子名称认作密封结构设计'),
    'M482.pemfc':(re.compile(r'reform|hydrogen.generat|hydrogen.produc|氢气发生|制氢|重整',re.I),'为PEMFC供氢的重整器不自动归入燃料电池本体运行'),
    'M315.power_semiconductor':(re.compile(r'transfer.switch|switching.system|转换开关|切换系统',re.I),'采用IGBT的系统不能仅凭器件名称归为半导体器件研究'),
    'M085.degradation':(re.compile(r'organic|polymer|perovskite|dye.sensiti|quantum.dot|有机|聚合物|钙钛矿|染料敏化|量子点',re.I),'特定材料太阳能电池研究不直接迁为通用光伏组件退化'),
    'M193.lithium_extraction':(re.compile(r'spent.{0,30}batter|black.mass|recycl|废旧|黑粉|回收',re.I),'废电池及黑粉回收不是矿产/盐湖锂资源提取'),
    'M212.isolated':(re.compile(r'isolated.communicat|隔离通讯|隔离通信|隔离信号',re.I),'通信隔离不等于DC-DC功率拓扑隔离'),
    'M251.permanent_magnet':(re.compile(r'scrap|recycl|metal.recover|废旧|回收',re.I),'废磁体金属回收与永磁材料性能设计任务不同'),
    'M262.current':(re.compile(r'fault.tolerant|sensorless|容错|无传感',re.I),'传感器容错控制不能等同电流测量电路研究'),
    'M262.voltage':(re.compile(r'classification.of.{0,20}events|event.classif|events.using|事件分类|事件识别',re.I),'使用电压量测的事件分类不是电压测量电路研究'),
    'M277.cable_material':(re.compile(r'cable.modeling|cable.modelling|EMI.simulat|电缆建模|电磁干扰仿真',re.I),'电缆电路建模不能仅由conductor字样归为材料结构'),
    'M311.heat_exchanger':(re.compile(r'earth.to.air|earth.air|\bEAHX\b|地埋|地源',re.I),'地耦合换热器与地源子类边界重合，保留复核'),
    'M325.floating_wind':(re.compile(r'monitoring|fault.diagnos|condition.monitor|监测|故障诊断',re.I),'漂浮风机监测研究不能只凭平台类型替代具体诊断任务'),
    'M386.gas_network':(re.compile(r'leakage|leak.locat|fault.detect|corrosion|泄漏|检漏|腐蚀|故障检测',re.I),'管网检测算法的优化不是管网运行优化'),
    'M467.wood_processing':(re.compile(r'insurance|contractual.price|timber.price|保险|合同价格|木材价格',re.I),'木材加工产业的经济研究不是加工工艺'),
}
ACCEPTED={'refined_child','cross_parent_reclassified','reclassified_after_cleaning','parent_supported'}
OVERRIDE_FILE=BASE/'review/SEMANTIC_OVERRIDES.json'
OVERRIDES=read(OVERRIDE_FILE) if OVERRIDE_FILE.exists() else {}
MANUAL_VETO={int(r['row_id']):r['reason'] for r in OVERRIDES.get('semantic_veto',[])}
QUALITY_VETO={int(r['row_id']):r['reason'] for r in OVERRIDES.get('quality_veto',[])}
EXTRA_EDITORIAL=re.compile(r"^(?:Editor['’]s Note\b|Publisher['’]s Note\b|Corrigendum\b|Erratum\b|Correction\s*[:：]|Retraction\s*[:：]|Retraction\s+of\b|Editorial\s*[:：]|Editorial Note\b|Referee report[.:]|Peer review report\b|Cover Photograph\b)",re.I)

def quality_veto(row):
    if row.get('row_id') in QUALITY_VETO:return QUALITY_VETO[row['row_id']]
    if EXTRA_EDITORIAL.search(row['title']):return '明确编辑说明、勘误、撤稿说明或同行评审报告题名'
    return None
ALIASES={'M274.biogas_process':'M128','M005.grid_construction':'M005','M302.fet':'M302',
         'M123.carbon_dispatch':'M123','M446.metering':'M446'}
NAME_OVERRIDES={'M128.food_sludge':'餐厨垃圾或污泥厌氧消化',
                'M101.line_fault':'输配电线路故障检测与定位','M137.parameters':'光伏电池与组件模型参数辨识',
                'M255.co2_hydrogenation':'二氧化碳催化加氢与甲烷化','M252.orc':'有机朗肯循环发电',
                'M114.hydrate':'二氧化碳水合物形成与分离'}
GENERIC_TARGETS={'M130.manufacturing','M303.temperature_sensing','M262.current','M262.voltage','M315.power_semiconductor',
                 'M141.rotor','M141.stator','M492.winding','M390.cable_support','M264.cover'}

def canonical_topic(tid):return ALIASES.get(tid,tid)

def extra_guard(row):
    title=row['title'];rule=row['rule_id'];tid=row.get('final_topic_id','')
    def hit(p):return bool(re.search(p,title,re.I))
    if tid in {'M108.zinc_ion','M414'} and hit(r'non.aqueous|nonaqueous|非水'):
        return '明确非水体系不能作为水系锌电池'
    if tid=='M261' and hit(r'anode|negative.electrode|electrolyte|separator|dendrite|负极|电解质|电解液|隔膜|枝晶') and not hit(r'cathode|positive.electrode|polysulfide|正极|多硫化物'):
        return '锂硫电池负极或电解质部件不能直接归入正极/多硫化物主类'
    if rule in {'M021.electrolyte','M447.anode','M447.cathode'} and not hit(r'\bsodium\b|\bNa[ -]?(?:ion|metal)\b|钠'):
        return '钠电池须有独立钠对象，不能由coordination等词内na.ion推断'
    if rule in {'M049.solid','M049.gel'} and hit(r'magnesium|aluminium|aluminum|potassium|calcium|镁|铝|钾|钙'):
        return '非锂体系或跨离子体系不能强分到锂聚合物电解质'
    if tid in {'M008','M036.co2_photo'}:
        if not hit(r'reduc|valorization|conversion|还原|转化'):return '仅同时出现CO2及电化学/光催化不能证明二氧化碳还原任务'
        if tid=='M008' and hit(r'photoelectrochem|photoelectrocatal|光电化学|光电催化'):return '光电化学CO2还原与纯电还原的边界需复核'
    if rule=='M015.algal_biofuel' and hit(r'lignocellulos|cellulosic|木质纤维素'):
        return '藻类与木质纤维素生物燃料并列比较，不能强分单一原料'
    if rule in {'M016.piezoelectric','M016.electromagnetic'} and hit(r'piezoelectric|压电') and hit(r'thermoelectric|electromagnetic|热电|电磁'):
        return '多机理混合能量采集需要确定主方向'
    if rule in {'M023.tidal','M120.wave_energy'} and hit(r'\bwave\b|波浪') and hit(r'\btidal\b|潮流|潮汐'):
        return '波浪与潮汐/潮流研究同时出现，保留复核'
    if rule=='M033.sludge_dewatering' and hit(r'methanogen|biogas|methane.production|产甲烷|产气'):
        return '脱水与生物产气并列任务，保留主类复核'
    if rule=='M033.sludge_dewatering' and hit(r'digesters?.as.heat.storage|digester.temperature'):
        return '消化器储热运行的副指标不能替代污泥脱水主任务'
    if rule=='M003.offshore_economics' and hit(r'\bwave\b|波浪能'):
        return '海上风电与波浪能并列技术比较，不强分单一风电子类'
    if tid=='M010.photocatalytic_h2' and hit(r'photoelectrocatal|photoelectrochem|光电催化|光电化学'):
        return '有外加电化学环节的制氢不能直接等同单纯光催化制氢'
    if rule=='M045.coal_gasification' and hit(r'(?:aromatics|tar).{0,80}coal.gasification|coal.gasification.{0,60}(?:extract|separat)|煤气化.{0,30}(?:芳烃|萃取)'):
        return '煤气化副产物分离不能替代气化反应任务'
    if rule=='M062.pyrolysis' and hit(r'upgrading.{0,20}bio.oil|生物油.{0,12}提质'):
        return '热解油后续提质与热解反应需区别'
    if rule=='M058.fermentative_h2' and hit(r'electrohydrogenesis|microbial.electrolysis|微生物电解'):
        return '暗发酵与微生物电解耦合制氢不强分单一路线'
    if rule in {'M124.dry_reforming','M124.steam_reforming'} and hit(r'steam|蒸汽') and hit(r'dry.reform|steam.dry|干重整'):
        return '蒸汽与干重整共同研究不强分单一路线'
    if rule=='M135.market_design':
        t=re.sub(r'发展改革委(?:员会)?|发展和改革委(?:员会)?','',title)
        if not re.search(r'market.design|mechanism|market.reform|机制|制度|改革',t,re.I):
            return '机关名“发展改革委”不能充当电力市场改革任务证据'
    if rule in {'M141.stator','M141.rotor'} and hit(r'整流桥|发电系统|rectifier|converter'):
        return '使用定转子的整流/发电系统拓扑不能替代定转子结构研究'
    if rule=='M164.lightning' and hit(r'lightning.return.stroke|雷电回击') and not hit(r'overhead|coupling|架空|耦合'):
        return '雷电回击的传输线等效模型不是输电线路防雷研究'
    if rule=='M169.ecm' and hit(r'charging.profile|charging.strateg|charging.control|充电策略|充电控制'):
        return '采用等效电路的充电控制研究需区分主任务'
    if rule=='M192.solid_storage' and hit(r'energy.supply.system|distributed.energy|configuration.opt|综合能源|容量配置'):
        return '供能系统中的储氢部件不足以认作储氢材料或反应器研究'
    if rule=='M198.copper_thermoelectric' and hit(r'Mo3Sb7|Bi2Te3'):
        return '同时研究非铜基体系或复合主相，铜基归属需复核'
    if rule=='M226.water' and hit(r'persulfate|peroxymonosulfate|peroxydisulfate|过硫酸盐|过一硫酸盐'):
        return '过硫酸盐活化有统一反应主类，不能另复制生物炭材料子类'
    if rule=='M239.economics' and hit(r'energy.payback') and not hit(r'cost|economic|\binvestment|成本|经济|投资'):
        return '能量回收期与投资回收期不同，技术经济归属需复核'
    if rule=='M239.economics' and hit(r'hybrid|混合|互补') and hit(r'\bwind\b|fuel.cell|风能|风电|燃料电池'):
        return '光伏与其他能源组成的混合系统经济性不强分单一光伏技术'
    if rule=='M206.aging' and hit(r'cathode|anode|electrode|film|正极|负极|电极|包覆') and not hit(r'\baging\b|\bageing\b|老化'):
        return '电极材料循环性能提升不一定是电池老化实验主任务'
    if rule=='M253.location' and hit(r'(?:siting|placement).of.{0,25}(?:DER|FACTS|distributed.generation)|分布式电源选址'):
        return '被选址对象是电源/补偿装置，不一定是充电站'
    if rule=='M264.cover' and hit(r'烫边|卷绕装置|叠片装置|焊接装置|制造设备'):
        return '加工设备不能仅因密封或壳体字样归为电池盖板结构'
    if rule=='M268.proton_membrane' and hit(r'燃料电池用.{0,25}(?:碳纸|气体扩散层|双极板|催化剂|电极)|carbon.paper|gas.diffusion.layer|bipolar.plate'):
        return '质子交换膜燃料电池用碳纸/其他部件不是质子交换膜材料'
    if rule=='M279.graphite' and re.search(r'\bSi\b|\bSiO[x2]\b',title):return '硅石墨复合负极不能强制作为石墨单一子类'
    if rule=='M277.cable_material' and hit(r'locali[sz]ation|fault.locat|diagnos|故障定位|诊断'):
        return '电缆绝缘缺陷定位与材料结构研究应区分'
    if rule=='M374.potassium' and hit(r'sodium|钠'):
        return '钠钾体系并列研究不强分钾离子电池子类'
    if rule in {'M290.fission','M290.fusion'} and hit(r'fusion|聚变') and hit(r'fission|裂变'):
        return '裂变和聚变并列研究，不强分单一路线'
    if rule=='M290.fusion' and hit(r'plasma.detach|confinement|instability|runaway|disruption|等离子体脱靶|约束性能') and not hit(r'engineering|design|construction|工程|设计|建造'):
        return '等离子体物理过程不因出现偏滤器而认作装置工程'
    if rule=='M324.adsorption' and hit(r'tar.reform|焦油重整'):
        return 'CO2捕集与焦油重整双功能研究需确定主任务'
    if rule=='M360.counterelectrode' and hit(r'photoanode|光阳极'):
        return '光阳极与对电极共同研究，保留染料敏化主类'
    if rule in {'M381.air_cooling','M381.liquid_cooling'} and hit(r'air.cooling|风冷') and hit(r'liquid.cooling|oil.cooling|液冷|油冷'):
        return '气冷与液冷耦合，不强制单一冷却路线'
    if rule=='M385.steam_turbine' and hit(r'generators?.{0,30}(?:steam.turbine.power.plant|steam.turbine)|汽轮发电机') and hit(r'availability|reliability|故障|可靠性'):
        return '电站发电机可靠性不是汽轮机热力性能'
    if rule=='M389.rail' and not hit(r'energy.consumption|energy.efficien|traction.opt|traction.option|eco.driv|regenerat|energy.sav|energy.opt|能耗|节能|能效|再生制动|牵引优化|运行优化'):
        return '泛牵引供电现象不足以认作轨道交通能耗优化'
    if rule=='M389.shipping' and hit(r'\broad\b|公路') and hit(r'maritime|shipping|海运|航运'):
        return '公路与航运多运输方式对比不强分船舶子类'
    if tid=='M414' and hit(r'supercapacitor|超级电容'):
        return '锌离子混合超级电容器不直接作为水系锌电池负极'
    if rule=='M482.pemfc':
        t=re.sub(r'proton.exchange.membrane.fuel.cells?|polymer.electrolyte(?:.membrane)?.fuel.cells?|质子交换膜燃料电池','',title,flags=re.I)
        if re.search(r'membrane|ionomer|sulfon|sulphon|poly\(|catalyst|platinum|nanowall|nanotube|graphene|碳纸|催化剂|膜材料|聚合物|石墨烯|碳纳米',t,re.I):
            return '燃料电池应用中的膜/催化材料不能替代电池本体运行建模'
    if tid=='M429' and hit(r'converter|inverter|power.supply|变换器|逆变器|电源'):
        return '采用SiC器件的变换系统需与器件本体研究区分'
    if rule=='M439.plastic' and hit(r'biodiesel|生物柴油'):
        return '塑料回收和生物柴油并列应用，保留多任务复核'
    if tid=='M453' and hit(r'alumin(?:ium|um).air|magnesium.air|primary.batter|一次电池|原电池|铝空气'):
        return '一次/金属空气电池不直接归二次电池电解液主类'
    if rule=='M459.risk_warning' and hit(r'人员|作业|人身|staff|worker|occupational'):
        return '人员作业安全风险不等于电力设备风险'
    if rule=='M460.irrigation' and hit(r'配电网|power.grid|distribution.network'):
        return '服务灌溉的电网调度不等于灌溉水资源调度'
    if rule=='M468.adsorption' and (hit(r'(?:recover|recovery).{0,35}(?:Au\(III\)|gold)|贵金属回收|金回收') or hit(r'supercapacitor|超级电容')):
        return '贵金属回收或储能器件复用不能强制当作水污染物去除'
    if rule=='M483.integration' and hit(r'energy.management|SOC.optim|dispatch|schedul|能量管理|调度|功率分配'):
        return '储能调度或能量管理不能仅因系统集成场景认作设备集成研究'
    if rule not in {'M295.education','M295.hil'}:
        t=re.sub(r'teaching.learning.based|teacher.student|student.teacher','',title,flags=re.I)
        if re.search(r'\bstudents\b|\bteaching\b|\beducation(?:al)?\b|\bcurriculum\b|教学|课程|人才培养',t,re.I):
            return '教学应用与具体技术研究的主任务不同，保留复核'
    if rule=='M274.biogas_process' and not hit(r'biogas|biomethane|anaerobic|digest|ferment|沼气|厌氧|消化|发酵'):
        return '产甲烷未明确生物过程，不自动并入厌氧消化'
    if rule in {'M128.food_sludge','M128.manure'} and hit(r'food.waste|sludge|餐厨|厨余|污泥') and hit(r'manure|dung|agricultural.residue|粪便|粪污|秸秆'):
        return '跨原料共消化涉及两个子类，保留主类复核'
    if rule in {'M288.air_heat_pump','M288.ground_heat_pump'} and hit(r'air.source|空气源') and hit(r'ground.source|地源'):
        return '空气源与地源热泵共同研究，不能强分单一路线'
    if rule in {'M045.coal_gasification','M347.gasification'} and hit(r'biomass|生物质|wood|木质') and hit(r'\bcoal\b|煤'):
        return '煤与生物质共气化不能强分单一原料子类'
    if tid=='M414' and hit(r'alkali|lithium|sodium|potassium|碱金属|锂|钠|钾'):
        return '多种金属负极共同研究，锌专类证据不足'
    if tid=='M363':
        stripped=re.sub(r'(?:platinum|noble.metal|precious.metal|metal)[ -]*free|non[ -]*(?:noble|precious)[ -]*metal|非贵金属|无铂', '', title,flags=re.I)
        precious=bool(re.search(r'platinum|palladium|ruthenium|iridium|gold|silver|铂|钯|钌|铱|银',stripped,re.I) or re.search(r'\b(?:Pt|Pd|Ru|Ir|Au|Ag)(?:[A-Z0-9]|/|-|@|\b)',stripped))
        nonprecious=hit(r'non.noble|non.precious|metal.free|platinum.free|Fe.N.C|iron|cobalt|manganese|copper|nickel|nitrogen.doped.carbon|heteroatom|非贵金属|无金属|铁|钴|锰|铜|镍|氮掺杂碳')
        if precious or not nonprecious:return '原主类限定非贵金属；贵金属或材料范围不明的ORR不能自动并入'
    if rule=='M268.proton_membrane' and hit(r'alkaline.fuel.cell|solid.oxide.fuel.cell|碱性燃料电池|固体氧化物燃料电池'):
        return '多燃料电池路线综述不是单一质子交换膜材料研究'
    if tid in GENERIC_TARGETS and row.get('old_parent_status') not in {None,'','宽泛待细分','混杂待重分','外围或非研究文本'} and row.get('old_parent_id')!=row.get('final_parent_id'):
        return '具体原主题迁往通用器件/方法类可能丢失研究对象，保留原主类复核'
    # A prominent second reaction is checked independently of candidate retrieval.
    reaction_targets={'M010.photocatalytic_h2','M112.pollutants','M203.pollutants','M079.other_pollutants','M036.co2_photo','M235','M256','M154','M363','M008'}
    if tid in reaction_targets:
        tasks=[hit(r'hydrogen.evolution|hydrogen.production|hydrogen.generat|析氢|制氢'),
               hit(r'oxygen.evolution|析氧'),hit(r'oxygen.reduction|氧还原'),
               hit(r'photodegrad|photocatalytic.degrad|pollutant.degrad|pollutant.oxid|光降解|光催化降解|污染物降解|染料降解'),
               hit(r'(?:CO2|carbon.dioxide).{0,20}(?:reduc|conversion)|(?:reduc|conversion).{0,20}(?:CO2|carbon.dioxide)|二氧化碳还原')]
        if sum(tasks)>1:return '题名同时列出多种反应任务，候选检索不全时也不强制单标签'
    return None

def guard(row):
    if row['assignment_status'] not in ACCEPTED:return None
    if row.get('row_id') in MANUAL_VETO:return MANUAL_VETO[row['row_id']]
    item=TITLE_GUARDS.get(row['rule_id'])
    if item and not item[0].search(row['title']):return item[1]
    item=EXCLUDE_GUARDS.get(row['rule_id'])
    if item and item[0].search(row['title']):return item[1]
    return extra_guard(row)

def apply(row,old_status):
    reason=guard(row)
    if not reason:return row,None
    before=dict(row_id=row['row_id'],title=row['title'],proposed_topic_id=row['final_topic_id'],
        old_parent_id=row['old_parent_id'],rule_id=row['rule_id'],reason=reason)
    row.update(final_parent_id=row['old_parent_id'],final_topic_id=row['old_parent_id'],final_topic_label=row['old_parent_name'],
        assignment_status='precision_guard_pending',needs_review=True,parent_changed=False,topic_changed=False,
        candidate_topic_ids=canonical_topic(before['proposed_topic_id']),eligible_for_topic_counts=False)
    return row,before
