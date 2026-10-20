"""Round 2: records of names actually read, explicit mappings and narrower gates.

Queue spelling selects terms to READ; it does not assign energy membership.
Word-name review and article-context review are separate evidence levels.
"""
from refine_rules import *
from common import ROOT, WORK, sha
import pandas as pd

OLD=ROOT/'work/keyword_dictionary_multilabel_20261019'
assert sha(OLD/'keyword_dictionary.csv')=='eabcbbb172da013a01af8ea4cd179e59c2a541bae8af93be3b4fae7b00b20b47', 'Baseline dictionary changed; reread the review queues'
old=pd.read_csv(OLD/'keyword_dictionary.csv').fillna('')
OLD_DICTIONARY=old
pending=old[old.decision.eq('unreviewed')].sort_values(['document_frequency','keyword_code'],ascending=[False,True])
top=pending.head(600)
energy=pending[pending.display_name.str.contains(r'energ|power|electri|volta|batter|grid|fuel|nuclear|solar|wind|hydro|coal|gas|oil|turbine|reactor|transformer|motor|capacitor|inverter|heat|carbon|renewab|photovolta|storage|charg|transmission|conduct|cable|relay|fusion|fission|plasma|thermal|lithium|sodium|hydrogen|steam|diesel',case=False,regex=True)]
focused=old[~old.decision.isin(['direct','conditional']) & old.display_name.str.contains(r'lighting|lamp|substation|switchgear|feeder|busbar|insulation|rectifier|photovoltaic|circuit breaker|load flow|synchronous|synchronou|thermoelectric|hydraulic turbine',case=False,regex=True)]
aux=old[old.decision.eq('general_auxiliary')].sort_values('document_frequency',ascending=False).head(220)
read_names=pd.concat([top,energy,focused,aux]).drop_duplicates('keyword_code')
REVIEW={r.canonical_name:{'decision':'general_auxiliary','topic_code':'',
 'reason':'已逐项阅读词名；通用概念、材料、方法、物质或多义词，单靠该词不足以指认能源技术主题。保留供后续语境复核，不等同与能源无关。',
 'review_scope':'term_name_read_context_not_resolved','prior_decision':r.decision}
 for r in read_names.itertuples()}
seen=set(old.canonical_name);syn=synonyms();old_index=old.set_index('canonical_name')

def decide(words,state,code=None,reason=''):
    for word in words.split('|'):
        name=syn.get(normalize(word),normalize(word))
        assert name in seen,word
        REVIEW[name]={'decision':state,'topic_code':f'KWD-T{code:04d}' if code else '',
           'reason':reason,'review_scope':'explicit_term_mapping_review','prior_decision':old_index.loc[name,'decision']}

# Fix actual overgeneralizations observed in the previous paper review.
decide('High voltage|Insulator (electricity)','conditional',32,'高电压和绝缘体也用于低电压半导体语境；仅与规定电力设备直接词共现时触发高压绝缘主题。')
decide('Automatic frequency control|Frequency deviation|Low-frequency oscillation|Nonlinear system|Algorithm|Auxiliary power unit|Flue gas|Photocurrent|Visible spectrum','general_auxiliary',reason='上轮抽查显示词义、问题性质或设备背景不能独立证明原对应主题；取消触发，保留原词。')
decide('Telecommunications|Reliability engineering|Photochemistry','broad_auxiliary',reason='学科或宽泛领域标签，不能单独证明能源通信、供电可靠性或光催化研究。')

# Direct additions are concrete technologies/equipment or explicit energy policy.
for code,words in {
 20:'Charge controller|Depth of discharge',26:'Busbar',31:'Switchgear',
 37:'Welding power supply',40:'Direct torque control|Ultrasonic motor|Piezoelectric motor',
 48:'Fan coil unit|Thermal expansion valve',51:'Chemical looping combustion|Steam drum|Steam engine',
 54:'Light crude oil|Tight oil|Shale oil extraction|Oil in place|Oil well|Oil exploration|Oil drilling|Microbial enhanced oil recovery|Steam-assisted gravity drainage',
 55:'Internal combustion engine|Homogeneous charge compression ignition',
 59:'Renewable portfolio standard',60:'Oil-storage trade',
}.items():decide(words,'direct',code,'词名明确指向能源设备、技术、能源资源或能源政策；按完整来源词身份触发，不按字符串片段匹配。')

for code,words in {
 1:'Crystalline silicon|Amorphous silicon|Quantum efficiency|Singlet fission',
 5:'Low-temperature thermal desalination|Desalination|Reverse osmosis',
 12:'Methanogenesis',13:'Atomic energy|Thermal hydraulics',
 14:'Uranium|Nuclear disaster|Decay heat|Nuclear radiation',
 15:'Plasma diagnostics|Plasma parameters|Plasma confinement|Plasma instability|Plasma stability|Zonal flow (plasma)|Dense plasma focus|Waves in plasmas',
 20:'Overcharge|Self-discharge|Charge cycle|Pre-charge',22:'Molten salt|Enthalpy of fusion',
 27:'Three-phase|Phasor',30:'Voltage spike|Disturbance voltage|Ripple',
 32:'Corona discharge|Brush discharge|Streamer discharge|Space charge',
 37:'Charge pump|Capacitor-input filter',39:'Wide-bandgap semiconductor',
 40:'Vector control|Field coil|Coil noise',
 48:'Thermal comfort|Evaporator|Coefficient of performance|Lithium bromide',
 49:'Daylighting|Thermal bridge|Thermal transmittance|Thermal mass|Pipe insulation',
 50:'Thermal efficiency|Working fluid|Boiling heat transfer|Flow boiling|Loop heat pipe|Micro-loop heat pipe|Thermal management of electronic devices and systems|Heat transmission',
 51:'Critical heat flux|Superheating|Steam pressure|Thermal barrier coating',52:'Coke',
 54:'Oil consumption|Oil pump|Oil storage|Oil tank|Gas oil ratio|Coiled tubing',
 55:'Turbocharger|Ignition system|Aircraft fuel system|Diesel locomotive',
 57:'NOx|Environmental impact assessment|Environmental remediation|Pollution|Thermal pollution|Oil pollution',
 58:'Climate change mitigation|Global warming|Carbon dioxide in Earth\'s atmosphere',
 62:'Power optimization|Power gating|Dynamic voltage scaling|Leakage power|Low-power electronics|Ultra low power',
 63:'Renewable resource',65:'Boosting (machine learning)|Cluster analysis',66:'Fuzzy control system',
 68:'Fast ion conductor|Proton conductor|Nafion|Oxygen reduction|Intercalation (chemistry)|Lithium carbonate|Lithium fluoride|Lithium perchlorate|Lithium nitrate|Lithium chloride|Lithium oxide|Lithium iodide|Lithium sulfate|Differential pulse voltammetry|Anodic stripping voltammetry|Cathodic stripping voltammetry|Adsorptive stripping voltammetry',
 69:'Nanowire|Nanofiber|Nanocrystalline material|Nanosheet|Nanotube|Titanium dioxide|Organic semiconductor|Polyaniline|Polypyrrole|PEDOT:PSS|Yttria-stabilized zirconia|Cobalt oxide|Molybdenum disulfide|Aerogel|Superconductivity|Superconducting magnet|High-temperature superconductivity|Superconducting wire|Cathodic protection|Carbon fiber reinforced polymer|Carbon fiber composite',
 71:'Plasma arc welding|Plasma cutting|Electrogas welding|Gas metal arc welding|Gas tungsten arc welding|Carbon arc welding',
}.items():decide(words,'conditional',code,'明确相关的材料、设备、过程或方法词；需同篇规定相关方向的能源锚点，关键词共现仅支持主题线索。')

# A missing technology family supported by observed words, not a preset K target.
add('照明与照明节能','电光源、灯具及智能照明；LED器件本身须有明确照明词，避免将显示或光通信自动视为照明。')
decide('Electric light|LED lamp|Fluorescent lamp|Gas-discharge lamp|Sodium-vapor lamp|Halogen lamp|Mercury-vapor lamp|Arc lamp|Smart lighting|Intelligent lighting|Solid-state lighting','direct',72,'明确电光源、灯具或照明系统；广义用电技术，业务是否属于电网核心范围另行判断。')
decide('Light-emitting diode|OLED|Thermal management of high-power LEDs','conditional',72,'器件也用于显示、通信等场景；须同篇明确照明直接词才归为照明。')

decide('Molecular physics|Atmospheric sciences|Biochemical engineering|Architectural engineering|Botany|Climatology|Statistical physics|Electronics|Archaeology|Manufacturing engineering|Geochemistry|Library science|Radiochemistry|International economics|Monetary economics|Geophysics|Financial economics|Seismology|Genetics|Agricultural engineering|Paleontology|Geodesy|Engineering management|Microbiology|Polymer science|Geomorphology|Theology|Development economics|Epistemology|Horticulture|Cell biology|Social science|Public administration|Thermal engineering|Thermal science|Nuclear science|Nuclear astrophysics','broad_auxiliary',reason='学科、宽泛行业或知识领域，不设为能源技术独立触发词。')
decide('Compensation (psychology)|Modulation (music)|Stress (linguistics)|Lattice (music)|Reactivity (psychology)|Anaerobic exercise|Leakage (economics)|Relaxation (psychology)|Feature (linguistics)|Cluster (spacecraft)|Deformation (meteorology)|Photothermal therapy|Dynamics (music)|Transformation (genetics)|Tracking (education)|Natural (archaeology)|Condenser (optics)|Pipeline (software)|Oscillation (cell signaling)|Strain (injury)|Distortion (music)|Traction (geology)|Space (punctuation)|Plan (archaeology)|Pulse (music)|Displacement (psychology)|Digestion (alchemy)|tar (computing)|Dendrite (mathematics)|Arc (geometry)|Control theory (sociology)|Control (management)|Composite number|Substrate (aquarium)|Crystal (programming language)|Reperfusion injury|Cable theory|Perfusion|Computer data storage|Snapshot (computer storage)|Optical storage|3D optical data storage|Cloud storage|Optical storage|Mass storage|Oil painting|Boilerplate text|Nuclear family|Windfall gain|Windshield|Power graph analysis|Graph power|Graph energy|Voltage graph|Loop fusion|Loop fission|And-inverter graph|Power doppler|Muscle power|Motor cortex|Motor imagery|Motor nerve|Blood plasma|Human plasma|Plasma volume|Plasma membrane Ca2+ ATPase|Plasma glucose|Plasma homocysteine|Plasma osmolality|Platelet-rich plasma|Plasmapheresis|Plasma medicine|Motor skill|Nuclear export signal|Nuclear pore|Nuclear lamina|Nuclear matrix|Somatic cell nuclear transfer|Spinal fusion|Fusion splicing|Fusion rules|Repeatable Battery for the Assessment of Neuropsychological Status','excluded',reason='已读词名显示为错误同形词义、非能源存储/能量概念或明确医学生物语境；不触发能源主题，不删除包含该词的论文。')

# Related-family gates are explicit and have no circular conditional anchors.
FAMILIES[5]=[3,4,5,10]
FAMILIES[32]=[26,27,31,32,33,34,35,36,37,38,39,40,41,44,64]
FAMILIES[39]=[2,24,36,37,38,39,40,41,42,44,45,71]
GLOBAL_SUPPORT.discard(68);FAMILIES[68]=[1,16,17,18,19,20,21,23,47,56]
FAMILIES[72]=[72]
TOPICS[27]['name']='电力调度、调频与灵活性'
TOPICS[27]['definition']='经济调度、可调度电源、电网调频、调峰及电力运行计划；通用自动频率控制不独立触发。'

# Additional corrections grounded in the new article cohort.
decide('Power station','direct',61,'发电站是跨能源类型的通用设备概念；归入供能系统，不再仅凭此词推断为火力发电。')
decide('Computer network','broad_auxiliary',reason='新摘要显示电力输电网络也被误配为Computer network；不能仅凭该泛化标签判断能源通信研究，取消独立触发。')
TOPICS[1]['name']='最大功率点跟踪与光伏控制'
TOPICS[1]['definition']='最大功率点跟踪、太阳跟踪器及光伏控制与并网；MPPT也可用于风电等对象，不单凭它断言研究对象为光伏。'
TOPICS[26]['name']='电力系统与电能通用研究'
TOPICS[26]['definition']='电力系统、电能与潮流运行等研究；Electricity或Electric power只提供通用电力关联，不能证明具体潮流研究。'
TOPICS[71]['name']='电光源、照明与照明节能'
TOPICS[71]['definition']='电光源、灯具、智能照明与照明节能；光源也可用作试验设备，命中不等于照明是论文主要对象。'

# Apply every explicit record to the vocabulary lists before dictionary build.
for name,r in REVIEW.items():
    for t in TOPICS:
        for mode in ['direct','conditional']:
            t[mode]=[word for word in t[mode] if syn.get(normalize(word),normalize(word))!=name]
    for seq in [BROAD_TERMS,OUTSIDE_TERMS,AUXILIARY_TERMS]:
        seq[:]=[word for word in seq if normalize(word)!=name]
    if r['decision'] in ['direct','conditional']:
        next(t for t in TOPICS if t['topic_code']==r['topic_code'])[r['decision']].append(name)
    elif r['decision']=='broad_auxiliary':BROAD_TERMS.append(name)
    elif r['decision']=='excluded':OUTSIDE_TERMS.append(name)
    else:AUXILIARY_TERMS.append(name)
