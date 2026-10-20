"""Assistant-curated, explicit keyword-to-theme decisions grounded in the corpus.

This is a controlled vocabulary, not a claim of automatic topic discovery or
expert approval. Words are matched by normalized exact identity, not substrings.
Generic terms can activate a supporting theme only with a direct energy term.
"""
from common import normalize

TOPICS=[]
def add(name,definition,direct='',conditional=''):
    TOPICS.append({'topic_code':f'KWD-T{len(TOPICS)+1:04d}','name':name,'definition':definition,
        'direct':[s.strip() for s in direct.split('|') if s.strip()],
        'conditional':[s.strip() for s in conditional.split('|') if s.strip()]})

add('光伏电池与光伏发电','光伏材料器件、太阳能电池及光伏发电系统。',
    'Photovoltaics|Photovoltaic system|Solar cell|Organic solar cell|Polymer solar cell|Dye-sensitized solar cell|Perovskite solar cell|Cadmium telluride photovoltaics|Copper indium gallium selenide solar cells|Thin film solar cell|Hybrid solar cell|Quantum dot solar cell|Plasmonic solar cell|Silicon solar cell|Solar cell efficiency|Theory of solar cells|Photovoltaic effect|Anomalous photovoltaic effect|Thermophotovoltaic|Building-integrated photovoltaics|Rooftop photovoltaic power station|Photovoltaic mounting system|Solar simulator|Solar cable',
    'Open-circuit voltage|Carrier lifetime|Passivation|Surface photovoltage')
add('光伏跟踪、控制与并网','光伏最大功率点跟踪、太阳跟踪器及光伏并网控制。',
    'Maximum power point tracking|Grid-connected photovoltaic power system|Solar tracker|Solar micro-inverter|Power optimizer|Grid-tie inverter')
add('太阳能热利用与聚光','太阳热集热、聚光、干燥、供热及光热发电。',
    'Concentrated solar power|Solar thermal collector|Solar water heating|Solar air conditioning|Solar furnace|Solar pond|Solar chimney|Solar dryer|Solar mirror|Photovoltaic thermal hybrid solar collector|Nanofluids in solar collectors|Parabolic trough|Solar thermal energy|Concentrating solar power|Solar power tower')
add('太阳能资源与综合利用','太阳能资源评估及未进一步细分的太阳能应用。',
    'Solar energy|Solar power|Solar energy conversion|Solar powered|Solar Resource|Air mass (solar energy)',
    'Solar irradiance|Solar zenith angle|Solar constant|Solar gain')
add('太阳能与地热淡化','以太阳能或地热驱动的海水淡化与蒸馏。','Solar still|Solar desalination|Geothermal desalination')
add('风力发电与风资源','风电机组、风电场、风资源评估及出力预测。',
    'Wind power|Offshore wind power|Vertical axis wind turbine|Variable speed wind turbine|Small wind turbine|Wind generator|Wind power forecasting|Wind resource assessment|Wind hybrid power systems|Windmill|Wind turbine|Wind farm|Wind energy',
    'Wind speed|Wind direction|Wind profile power law|Wind gradient|Wind shear|Log wind profile|Wind engineering|Wind profiler')
add('水力发电与水轮机','水力发电、水电工程及水轮机。',
    'Hydropower|Hydro power|Hydroelectricity|Small hydro|Micro hydro|Water turbine|Hydraulic turbines|Francis turbine|Hydroelectric power|Pelton wheel|Kaplan turbine')
add('抽水蓄能与机械储能','抽水、压缩空气及飞轮等机械形式的储能。','Pumped-storage hydroelectricity|Compressed air energy storage|Flywheel energy storage|Pumped storage|Gravity energy storage')
add('海洋能发电','波浪、潮汐、海洋温差及盐差发电。',
    'Marine energy|Tidal power|Wave power|Wave energy converter|Ocean thermal energy conversion|Osmotic power|Wells turbine',
    'Tidal current|Tidal range|Wind wave')
add('地热开发与地热供能','地热勘探、地热发电与地热供热。','Geothermal energy|Geothermal power|Geothermal heating|Geothermal exploration',
    'Geothermal gradient|Hydrothermal circulation')
add('生物质能源与生物燃料','生物质燃料、生物柴油、生物乙醇及生物质热化学能源转化。',
    'Bioenergy|Biofuel|Biodiesel|Biodiesel production|Biomass gasification|Biomass fuels|Energy crop|Cellulosic ethanol|Corn ethanol|Ethanol fuel|Aviation biofuel|Algae fuel|Biomass to liquid|Wood fuel|Waste-to-energy|Refuse-derived fuel|Biopower|Bio-energy with carbon capture and storage',
    'Biomass (ecology)|Lignocellulosic biomass|Bagasse|Pyrolysis|Hydrothermal liquefaction|Hydrothermal carbonization|Biochar|Ethanol fermentation')
add('沼气生产与利用','沼气、填埋气及生物天然气能源利用。','Biogas|Biogas production|Landfill gas|Renewable natural gas',
    'Anaerobic digestion|Anaerobic digester')
add('核裂变与核电工程','核反应堆、核电厂及裂变能源系统。',
    'Nuclear power|Nuclear power plant|Nuclear reactor|Nuclear fission|Nuclear plant|Nuclear power industry|Pressurized water reactor|Boiling water reactor|Light-water reactor|Molten salt reactor|Sodium-cooled fast reactor|Breeder reactor|Liquid fluoride thorium reactor|Nuclear reactor core|Reactor pressure vessel|Research reactor',
    'Nuclear engineering|Nuclear technology|Nuclear industry|Nuclear data|Nuclear graphite|Fission products|Nuclear fission product|Nuclear transmutation|Fast fission|Fission product yield')
add('核燃料循环与核安全','核燃料、乏燃料、后处理、退役及核设施安全。',
    'Nuclear fuel|Nuclear fuel cycle|Spent nuclear fuel|Nuclear reprocessing|MOX fuel|Thorium fuel cycle|Spent fuel pool|Nuclear decommissioning|Nuclear criticality safety|Fukushima Nuclear Accident|Fuel element failure',
    'Nuclear material|Long-lived fission product|Radiation protection|Fuel cycle')
add('核聚变与聚变装置','托卡马克、仿星器、惯性/磁约束聚变及装置部件。',
    'Tokamak|Stellarator|Wendelstein 7-X|Fusion power|Nuclear fusion|Thermonuclear fusion|Magnetic confinement fusion|Inertial confinement fusion|Spherical tokamak|Tokamak Fusion Test Reactor|Divertor|ITER|ASDEX Upgrade',
    'Tritium|Deuterium|Plasma|Magnetohydrodynamics|Hydrogen isotope')
add('制氢与水分解','制氢、水分解、电解水及生物制氢。',
    'Hydrogen production|Water splitting|Photocatalytic water splitting|Electrolysis of water|Alkaline water electrolysis|Polymer electrolyte membrane electrolysis|High-temperature electrolysis|High-pressure electrolysis|Photoelectrolysis|Biohydrogen|Fermentative hydrogen production|Microbial electrolysis cell|Methanol reformer|HYDROSOL',
    'Steam reforming|Water-gas shift reaction|Hydrogen purifier')
add('储氢、氢燃料与氢能供应','储氢、氢燃料、氢能基础设施和氢经济。',
    'Hydrogen storage|Hydrogen fuel|Hydrogen economy|Hydrogen technologies|Compressed hydrogen|Liquid hydrogen|Solid hydrogen|Hydrogen vehicle|Hydrogen internal combustion engine vehicle|Hydrogen fuel enhancement|Power to gas',
    'Hydride|Magnesium hydride|Lithium hydride|Sodium borohydride|Hydrogen spillover|Hydrogen sensor|Dehydrogenation|Gaseous hydrogen')
add('燃料电池','各类燃料电池、电堆及可逆燃料电池。',
    'Fuel cells|Fuel cell|Proton exchange membrane fuel cell|Solid oxide fuel cell|Microbial fuel cell|Direct methanol fuel cell|Direct-ethanol fuel cell|Molten carbonate fuel cell|Alkaline fuel cell|Regenerative fuel cell|Unitized regenerative fuel cell')
add('电池与电化学储能','充电电池、不同化学体系电池、电池组及电化学储能。',
    'Battery (electricity)|Lithium-ion battery|Lithium battery|Lithium–sulfur battery|Lithium vanadium phosphate battery|Lead–acid battery|Sodium-ion battery|Potassium-ion battery|Flow battery|Battery pack|Battery storage|Electrochemical energy storage|Automotive battery|Electric-vehicle battery|Alkaline battery|Organic radical battery|VRLA battery|Nanowire battery|Solid-state battery|Zinc–air battery|Lithium air battery|Nickel–metal hydride battery|Nickel–cadmium battery|Rechargeable battery')
add('电池管理、充电与安全','电池荷电/健康状态、充电控制、容量及安全管理。',
    'State of charge|Battery charger|Battery capacity|Battery management system|Trickle charging',
    'State of health|Thermal runaway|Cell voltage|Solid electrolyte interphase|Battery recycling')
add('超级电容器','双电层、赝电容及超级电容储能。','Supercapacitor|Supercapacitors|Pseudocapacitor|Electric double-layer capacitor')
add('储热与蓄冷','热能储存及相变蓄热应用。','Thermal energy storage|Thermal storage|Heat storage|Cold thermal energy storage|Ice storage air conditioning',
    'Phase-change material|Latent heat|Phase change')
add('储能系统与储能集成','系统层储能、并网储能与磁储能。','Energy storage|Grid energy storage|Superconducting magnetic energy storage|Hybrid energy storage')
add('微电网与分布式供能','微电网、分布式发电、独立供能及多能互补。',
    'Microgrid|Distributed generation|Distributed power generation|Distributed power|Stand-alone power system|Hybrid power|Distributed energy resources|Integrated energy system')
add('智能电网与虚拟电厂','智能电网、虚拟电厂及智能能源网络。','Smart grid|Virtual power plant|Energy internet|Smart energy|Smart power')
add('输配电网络与电网规划','电力输配电、电网连接、配电网与电力网络建设。',
    'Power grid|Electric power transmission|Electric power distribution|Distribution grid|Power network|Grid connection|Grid code|Electricity system|Electrical network|Electric network|National Grid|Power network design',
    'Electrical engineering|Power engineering|Electrical engineering technology|Grid')
add('电力系统潮流与运行','电力系统运行、潮流分析、系统仿真与平衡。',
    'Electric power system|Power flow|Power-flow study|Power system simulation|Power system simulator for engineering|Load balancing (electrical power)|Unified power flow controller|Electric power|Electricity')
add('电力调度与灵活性','经济调度、可调度电源、调峰及电力运行计划。',
    'Economic dispatch|Dispatchable generation|Load following power plant|Peaking power plant|Base load power plant',
    'Power sharing|Scheduling (production processes)|Unit commitment')
add('需求响应、负荷与供电可靠性','需求响应、电力负荷、电力需求预测及负荷切除。',
    'Demand response|Electricity demand|Load Shedding|Electrical load|Load forecasting|Electric load forecasting|Power outage|Demand-side management',
    'Demand forecasting|Load management|Reliability engineering')
add('电能质量与电压调节','功率因数、无功、电压偏差、电力谐波及滤波。',
    'Power quality|Electric power quality|Power factor|AC power|Single-phase electric power|Power system harmonics|Active power filter|Voltage sag|Voltage regulation|Voltage optimisation|Voltage droop|Voltage drop|Overvoltage|Ferroresonance in electricity networks|Low voltage ride through|Reactive power|Voltage stability',
    'Harmonics|Harmonic|Total harmonic distortion|Voltage compensation')
add('继电保护与开断设备','电力保护、继电器、断路器及短路故障保护。',
    'Power-system protection|Protective relay|Digital protective relay|Circuit breaker|Arc-fault circuit interrupter|Fault current limiter|Fault indicator|Differential protection|Fuse (electrical)|Sulfur hexafluoride circuit breaker|Prospective short circuit current|Transient recovery voltage',
    'Relay|Short circuit|Solid-state relay|Fault detection and isolation|Short circuit ratio|Overcurrent')
add('高电压、绝缘与局部放电','高压绝缘、局放、电树枝及介质耐压。',
    'High voltage|Insulator (electricity)|Electrical treeing|Electrical insulation paper|Dielectric withstand test|Partial discharge|Insulation system',
    'Dielectric|Dielectric strength|Dielectric loss|Electrical breakdown|Electric breakdown|Breakdown voltage|Liquid dielectric|Dielectric gas|Dielectric spectroscopy|Electric discharge|Electrical equipment')
add('防雷、接地与电气安全','防雷器、接地系统及电气安全。','Lightning arrester|Earthing system|National Electrical Code',
    'Lightning strike|Lightning detection|Electric shock|Electrical shock|Stray voltage|Grounding')
add('变压器与设备状态监测','电力变压器、互感器、绝缘油和变压器状态监测。',
    'Transformer|Distribution transformer|Current transformer|Transformer oil|Energy efficient transformer|Autotransformer|Isolation transformer|Delta-wye transformer|Amorphous metal transformer|Transformer types|Dissolved gas analysis',
    'Transformer effect')
add('电缆与输电线路','电力电缆、输电线和线路基础设施。','Power cable|High-voltage cable|Transmission line',
    'Electrical conduit|Electrical wiring|All-dielectric self-supporting cable')
add('高压直流与柔性输电','HVDC输电、换流站及直流互联。','High-voltage direct current|HVDC converter|HVDC converter station|Flexible AC transmission system')
add('变换器与开关电源','DC/DC、AC/AC变换器、开关电源和电源拓扑。',
    'Boost converter|Buck converter|Buck–boost converter|Forward converter|Flyback converter|Ćuk converter|Resonant converter|DC-to-DC converter|Cycloconverter|Switched-mode power supply|Switched-mode power supply applications|Capacitive power supply|Voltage converter|Uninterruptible power supply|Power supply unit|Flyback transformer',
    'Converters|Voltage regulator|Voltage controller|Voltage multiplier|Voltage doubler|Constant power circuit|Power supply|Switched capacitor')
add('逆变器与功率调制','功率逆变器及其调制控制。','Inverter|Power inverter|Voltage source inverter|Resonant inverter|Z-source inverter',
    'Pulse-width modulation|Space vector modulation|Multilevel inverter')
add('功率半导体与功率器件','电力电子、功率开关器件及功率模块。',
    'Power electronics|Power semiconductor device|Power MOSFET|Power module|Insulated-gate bipolar transistor|Thyristor',
    'Power cycling|Silicon carbide|Gallium nitride|MOSFET|IGBT')
add('电机与驱动控制','各类电动机、转子、驱动器及电机控制。',
    'Electric motor|Induction motor|Synchronous motor|DC motor|AC motor|Switched reluctance motor|Permanent magnet synchronous motor|Permanent magnet motor|Reluctance motor|Wound rotor motor|Brushed DC electric motor|Superconducting electric machine|Electric machine|Electrical machinery|Linear motor|Linear induction motor|Universal motor|Servomotor|Torque motor|Stepper motor|Motor drive|Motor controller|Motor control|Motor soft starter|Homopolar motor',
    'Rotor (electric)|Stator|Armature (electrical engineering)|Torque|Commutation')
add('发电机与发电机组','电能发电机、异步/同步发电机和备用机组。',
    'Electric generator|Generator (circuit theory)|Permanent magnet synchronous generator|Induction generator|Doubly fed electric machine|Diesel generator|Magnetohydrodynamic generator',
    'Auxiliary power unit')
add('电动汽车、充电与车网互动','电动汽车、充电设备、动力电池应用及V2G。',
    'Electric vehicle|Electric cars|Battery electric vehicle|Charging station|Vehicle-to-grid|Inductive charging|Hybrid electric vehicle|Plug-in hybrid|Smart charging',
    'Powertrain|Automotive engineering|Fuel efficiency|Miles per gallon gasoline equivalent|Alternative fuel vehicle')
add('再生制动与能量回收','车辆或电驱系统的再生制动和动能回收。','Regenerative brake|Regenerative braking|Dynamic braking',
    'Brake|Dynamic braking system')
add('牵引供电与电气化铁路','轨道车辆牵引电机、供电网络及电力机车。','Traction power network|Electric locomotive|Electric traction|Traction motor|Railway electrification system')
add('无线电能传输','无线、感应及射频电能传输。','Wireless power transfer|Radio frequency power transmission',
    'Maximum power transfer theorem')
add('能量采集与微能源','压电、摩擦电及微型能量采集。','Energy harvesting|Triboelectric nanogenerator|Piezoelectric energy harvesting',
    'Piezoelectricity|Triboelectric effect|Pyroelectricity|Piezoelectric coefficient|Pyroelectric crystal')
add('热电转换与热电制冷','热电材料、温差发电及热电制冷。','Thermoelectric effect|Thermoelectric materials|Thermoelectric generator|Thermoelectric cooling',
    'Seebeck coefficient|Bismuth telluride')
add('热泵、暖通与制冷','热泵、空调、冷热供应及建筑暖通设备。',
    'Heat pump|Air source heat pumps|Absorption heat pump|Heat pump and refrigeration cycle|Air conditioning|HVAC|Chiller boiler system|Heat recovery ventilation|Energy recovery ventilation|Refrigeration',
    'Refrigerant|Gas compressor|Infiltration (HVAC)')
add('建筑节能与建筑供能','低能耗建筑、建筑能源模拟、被动太阳能及建筑保温。',
    'Zero-energy building|Low-energy house|Building energy simulation|Passive solar building design|Building insulation',
    'Thermal insulation|Dynamic insulation|Vacuum insulated panel|Solar greenhouse')
add('余热利用、热力循环与换热','有机朗肯、热力循环、余热回收及能源设备换热。',
    'Organic Rankine cycle|Rankine cycle|Waste heat recovery unit|Heat recovery steam generator|Cogeneration|Stirling engine|Stirling cycle|Waste heat|Combined cycle',
    'Heat exchanger|Plate heat exchanger|Plate fin heat exchanger|Regenerative heat exchanger|Shell and tube heat exchanger|Micro heat exchanger|Concentric tube heat exchanger|Copper in heat exchangers|Moving bed heat exchanger|Heat transfer|Cooling tower|Water cooling|Exergy|Exergy efficiency')
add('火力发电、锅炉与透平','火电厂、燃气/蒸汽轮机、锅炉及联合循环发电。',
    'Thermal power station|Steam-electric power station|Power station|Steam turbine|Gas turbines|Integrated gasification combined cycle|Coal fired power plant|Pulverized coal-fired boiler|Steam power|Boiler (water heating)|Boiler feedwater|Boiler feedwater pump|Boiler water|Boiler blowdown|Flash boiler',
    'Turbine|Turbine blade|Gas burner|Combustion|Combustor')
add('煤炭与煤基能源转化','煤炭、煤气化、液化及煤基能源资源。',
    'Coal|Bituminous coal|Brown coal|Hard coal|Coal gasification|Underground coal gasification|Coal liquefaction|Coalbed methane|Enhanced coal bed methane recovery|Clean coal|Clean coal technology|Coal fired|Coal gas|Energy value of coal',
    'Coal mining|Coal rank|Coal preparation plant|Coal slurry|Coal tar|Coal combustion products|Coal dust|Coal basin|Coal measures')
add('天然气、液化天然气与管输','天然气资源、加工、储运、LNG及燃气供应。',
    'Natural gas|Liquefied natural gas|Compressed natural gas|Natural gas field|Natural gas industry|Natural gas storage|Natural-gas processing|Gas pipeline|Shale gas|Tight gas|Substitute natural gas|Oil and natural gas|Associated petroleum gas|Oil shale gas|Gas industry',
    'Gas consumption|Gas engine|Sour gas|Dry gas|Wet gas|Gas leak')
add('石油与炼制','石油资源、勘探、储层、炼制及石油产品。',
    'Petroleum|Petroleum industry|Petroleum engineering|Petroleum product|Petroleum reservoir|Petroleum exploration|Offshore oil and gas|Hydrocarbon exploration|Oil refinery|Petroleum system|Petroleum geology|Petroleum geochemistry',
    'Petroleum coke|Completion (oil and gas wells)|Well test (oil and gas)|Gas lift|Hydrodesulfurization|Hydrodenitrogenation')
add('燃料、合成燃料与燃料供给','化石/替代燃料、合成气、甲醇燃料及燃料性能。',
    'Fossil fuel|Diesel fuel|Fuel oil|Methanol fuel|Syngas|Wood gas generator|Gasoline|Renewable fuels|Solar fuel|Solid fuel|Fuel gas|Producer gas|Liquefied petroleum gas|Liquid fuel|Alternative fuels|Synthetic fuel|Carbon-neutral fuel|Alcohol fuel|Syngas to gasoline plus|Gas to liquids|Water gas|Blast furnace gas|Winter diesel fuel|Ultra-low-sulfur diesel|Aviation fuel|Jet fuel|Motor fuel|Fuel poverty',
    'Diesel engine|Diesel cycle|Petrol engine|Fuel injection|Fuel supply|Fuel pump|Fuel tank|Gasoline direct injection|Air–fuel ratio|Fuel mass fraction|Brake specific fuel consumption|Thrust specific fuel consumption|Emulsified fuel')
add('碳捕集、封存与二氧化碳转化','碳捕集封存、烟气碳处理及能源相关二氧化碳转化。',
    'Carbon capture and storage (timeline)|Carbon capture and storage|Carbon capture|Carbon dioxide removal|Electrochemical reduction of carbon dioxide|Negative carbon dioxide emission',
    'Carbon sequestration|Carbon dioxide reforming|Amine gas treating|Supercritical carbon dioxide|Greenhouse gas removal')
add('能源排放控制与环境治理','能源设施污染控制、烟气治理及能源活动的环境影响。',
    'Flue-gas desulfurization|Flue-gas emissions from fossil-fuel combustion|Environmental impact of the energy industry',
    'Flue gas|Diesel exhaust|Diesel particulate filter|Diesel exhaust fluid|Exhaust gas|Exhaust gas recirculation|Emission standard|Methane emissions|Fugitive emissions|Wastewater|Sewage treatment|Pollutant|Life-cycle assessment')
add('能源碳核算、碳交易与低碳治理','与明确能源对象共现的碳核算、碳交易和排放政策。','',
    'Carbon tax|Carbon price|Carbon market|Carbon credit|Carbon finance|Carbon accounting|Carbon footprint|Carbon offset|Carbon neutrality|Low-carbon economy|Emissions trading|Carbon leakage|Carbon dioxide equivalent|Emission intensity|Emission inventory|Greenhouse gas|Zero emission')
add('能源政策、转型与安全','能源政策、能源转型、能源安全、战略及法规。',
    'Energy policy|Energy transition|Energy security|Energy independence|Energy law|Energy strategy|Nuclear energy policy',
    'Government (linguistics)|Public economics|Subsidy|Politics|Political economy|Geopolitics|Law|Legislation')
add('电力市场、电价与能源经济','电力交易、电价、能源市场及能源经济性。',
    'Electricity market|Electricity price|Electricity pricing|Electricity retailing|Electricity price forecasting|Power market|Energy market|Energy economics|Natural gas prices|Cost of electricity by source|Grid parity|Energy subsidies|Energy tax|Fuel tax|Renewable energy credit',
    'Econometrics|Environmental economics|Finance|Investment (military)|Payback period|Market power|Bidding|Business administration|Business management')
add('能源供需、规划与资源','能源需求、供应、结构、资源及能源规划。',
    'Energy supply|Energy demand|Energy resources|Energy planning|Energy mix|Energy sector|Energy development|Energy poverty|Primary energy|Energy system|Energy engineering|Energy technology|Electric power industry|Electric utility|Electricity generation|Electrification|Rural electrification',
    'Energy source|Energy carrier|Energy accounting|Energy modeling|Water-energy nexus')
add('能源效率、节能与管理','能源消费、节能、能源管理及用能效率。',
    'Efficient energy use|Energy consumption|Energy conservation|Energy management|Energy management system|Electric energy consumption|Electrical efficiency|Energy intensity|Energy performance|Power management system|Power saving',
    'Power consumption|Power management|Power demand|Standby power|Energy recovery|Embodied energy|Energy analysis|Energy conversion efficiency|Energy cost')
add('可再生能源与综合能源系统','可再生能源、清洁能源及间歇性可再生供能。',
    'Renewable energy|Sustainable energy|Clean energy|Alternative energy|Variable renewable energy|Intermittent energy source|New energy',
    'Sustainability|Sustainable development')
add('电能计量与电网通信','智能计量、电力线通信及电网信息交换标准。',
    'Smart meter|Electricity meter|Power-line communication|IEC 61850|Common Information Model (electricity)|Net metering',
    'Advanced metering infrastructure|Metering mode')
add('能源应用中的人工智能与数据分析','明确能源对象同时出现的机器学习、数据科学及智能分析方法。','',
    'Artificial intelligence|Machine learning|Deep learning|Data mining|Data science|Big data|Analytics|Neural network|Artificial neural network|Convolutional neural network|Recurrent neural network|Long short-term memory|Support vector machine|Random forest|Reinforcement learning|Deep reinforcement learning|Federated learning|Transfer learning|Digital twin|Computer vision')
add('能源应用中的优化与控制','明确能源对象同时出现的优化、调度算法及控制方法。','',
    'Mathematical optimization|Optimization problem|Particle swarm optimization|Genetic algorithm|Multi-objective optimization|Mixed integer programming|Linear programming|Nonlinear programming|Dynamic programming|Model predictive control|Robust control|Sliding mode control|Fuzzy control|Adaptive control|Optimal control|Control theory|Control engineering|Control system|PID controller|Kalman filter')
add('能源应用中的通信与网络安全','明确能源对象同时出现的通信、物联网、信息系统及网络安全。','',
    'Internet of Things|Cyber-physical system|Computer security|Cybersecurity|Network security|Blockchain|Cloud computing|Edge computing|Computer network|Wireless sensor network|Telecommunications|Distributed computing|SCADA')
add('能源应用中的电极与电解质材料','明确能源对象同时出现的电极、电解质与电池活性材料。','',
    'Electrode|Cathode|Anode|Electrolyte|Ionic conductivity|Lithium iron phosphate|Lithium cobalt oxide|Lithium titanate|Lithium metal|Separator (oil production)|Ion exchange membrane|Solid electrolyte|Electrocatalyst|Oxygen evolution|Oxygen reduction reaction|Electrolysis|Gas diffusion electrode|Faraday efficiency|Overpotential|Tafel equation|Reversible hydrogen electrode')
add('能源应用中的材料结构与表征','明确能源对象同时出现的多孔、碳、纳米及结构功能材料研究。','',
    'Porosity|Porous medium|Specific surface area|Metal-organic framework|Nanoporous|Carbon nanotube|Carbon nanofiber|Carbon fibers|Activated carbon|Active carbon|Activated charcoal|Graphene|Nanomaterials|Nanoparticle|Nanocomposite|MXenes|Phosphorene|Boron nitride|Semiconductor|Band gap|Crystallinity|Grain boundary|Microstructure|Thin film|Coating|Corrosion')
add('能源应用中的光催化与光电化学','明确能源对象同时出现的光催化、光电化学和相关反应方法。','',
    'Photocatalysis|Photocurrent|Photochemistry|Photoelectrochemistry|Photoelectrochemical cell|Photocatalytic activity|Visible spectrum')

# Synonym consolidation is narrow and explicit; material/medical senses are never merged.
SYNONYM_GROUPS=[
    ['Fuel cells','Fuel cell'],['Supercapacitor','Supercapacitors'],['Solar cell','Solar cells'],
    ['Hydropower','Hydro power','Hydroelectricity'],['Power grid','Electric grid','Electrical grid'],
    ['Lithium-ion battery','Lithium ion batteries','Lithium-ion batteries'],
    ['Sodium-ion battery','Sodium ion batteries'],['Wind power','Wind energy'],
    ['Carbon capture and storage (timeline)','Carbon capture and storage'],
    ['Regenerative brake','Regenerative braking'],['Power-flow study','Power flow study'],
]

BROAD_TERMS='Art|Biology|Business|Chemistry|Computer science|Economics|Engineering|Environmental science|Geography|Geology|History|Linguistics|Materials science|Mathematics|Medicine|Philosophy|Physics|Political science|Psychology|Sociology|Humanities|Nuclear chemistry|Nuclear physics|Organic chemistry|Inorganic chemistry|Chemical engineering|Mechanical engineering|Statistics|Nanotechnology|Optoelectronics|Condensed matter physics|Applied mathematics|Biochemistry|Ecology|Management|Environmental engineering|Analytical Chemistry (journal)|Earth science|Architecture|Civil engineering|Agriculture|Oceanography|Astrophysics|Astronomy|Law and economics|Industrial engineering|Operations research|Computational chemistry|Physical chemistry|Thermodynamics|Quantum mechanics|Classical mechanics|Computer engineering|Electronic engineering|Forestry'.split('|')

# Explicitly inspected misleading or out-of-domain terms. These stay in the audit dictionary.
OUTSIDE_TERMS='Astrobiology|Gynecology|Cardiology|Heart failure|Internal medicine|Traditional medicine|Medicinal chemistry|Animal science|Lithium (medication)|Nuclear medicine|Gastroenterology|Gastrointestinal tract|Motor neuron|Motor learning|Psychomotor learning|Motor coordination|Motor unit|Motor function|Motor activity|Motor vehicle crash|Molecular motor|Fault (geology)|Fault plane|Fault gouge|Fault block|Active fault|Stock (firearms)|Investment (military)|Lightning (connector)|Position (finance)|Government (linguistics)|Competition (biology)|Energy (signal processing)|Energy metabolism|Food energy|Energy expenditure|Electrical conduction system of the heart|Nuclear receptor|Nuclear localization sequence|Mitochondrial fission|mitochondrial fusion|Fusion protein|Fusion center|Sensor fusion|Information fusion|Image fusion|Confusion|Confusion matrix|Nuclear weapon|Nuclear proliferation|Nuclear strategy|Solar wind|Solar flare|Solar physics|Solar System|Solar telescope|Solar observatory|Solar sail|Solar dynamo|Solar eclipse|Solar rotation|Solar radio|Solar atmosphere|Solar radius|Solar energetic particles|Solar prominence|Solar cycle|Solar cycle 22|Solar cycle 23|Solar cycle 24|Solar minimum|Solar maximum|Solar variation|Formation and evolution of the Solar System|Presolar grains|Standard solar model|Power set|Power series|Power law|Power function|Power diagram|Power iteration|Statistical power|Predictive power|Explanatory power|Soft power|Hard power|Great power|Regional power|Economic power|Purchasing power|Purchasing power parity|Social power|Executive power|Separation of powers|Grid computing|Grid cell|Data grid|Semantic grid|Ball grid array|Gridlock|Geogrid|Unstructured grid|Multigrid method|Grid reference|Windows CE|Microsoft Windows|Windows NT|Windows Vista|Windows Server|Windows Workflow Foundation|Windows Rally|Window (computing)|Window function|Sliding window protocol|Therapeutic window|PowerPC|Analog-to-digital converter|Digital-to-analog converter|Time-to-digital converter|Digital down converter|Dielectric resonator antenna|Nuclear magnetic resonance|Nuclear magnetic resonance spectroscopy|Solid-state nuclear magnetic resonance|Carbon-13 NMR|Two-dimensional nuclear magnetic resonance spectroscopy|Nuclear Overhauser effect|Diffusion MRI|Positron emission tomography|Nuclear magnetic resonance crystallography'.split('|')

# Same-spelling sense labels explicitly conflict with benign applications; no trigger.
# Remove these from conditional theme lists rather than silently reinterpreting their senses.
WRONG_SENSES={'Government (linguistics)','Investment (military)','Lithium (medication)','Fault (geology)','Lightning (connector)','Competition (biology)','Stock (firearms)','Position (finance)'}
for topic in TOPICS:
    topic['conditional']=[s for s in topic['conditional'] if s not in WRONG_SENSES]

AUXILIARY_TERMS='Power (physics)|Energy|Hydrogen|Carbon dioxide|Methane|Carbon|Sodium|Lithium|Ethanol|Methanol|Voltage|Electric current|Electrical current|Electric field|Electric potential|Electrical resistance and conductance|Electrical resistivity and conductivity|Electric energy|Electric charge|Electrical conductor|Electrical impedance|Capacitor|Inductor|Inductance|Conductivity|Heat transfer coefficient|Temperature|Thermal|Thermal energy|Heat energy|Energy density|Power density|Surface energy|Kinetic energy|Chemical energy|Energy transformation|Energy transfer|Energy balance|Energy flow|Energy flux|Energy exchange|Energy budget|Energy requirement|Energy value|Total energy|Specific energy|Mechanical energy|Binding energy|Activation energy|Gibbs free energy|Helmholtz free energy|Potential energy|Internal energy|Energy level|Energy landscape|Stored energy|Conservation of energy|Maximum power principle|Power transmission|Power control|Power loss|Power unit|Power Balance|Energy recovery|Fuel cycle|Gas separation|Gas composition|Hydrogen peroxide|Hydrogen bond|Hydrogen atom|Hydrogen molecule|Carbon monoxide|Carbonate|Hydroxide|Hydrocarbon|Plasma|Fusion|Fission|Turbine|Bioreactor|Chemical reactor|Reactor design|Microreactor|Membrane reactor|Photodetector|Photoluminescence|Photoelectric effect|Photodegradation|Methylene blue|Saturation (graph theory)|Type (biology)|Work (physics)|Product (mathematics)|Identification (biology)|Process (computing)|Node (physics)|Point (geometry)|Computational fluid dynamics|Finite element method|Density functional theory|Spectroscopy|Scanning electron microscope|X-ray photoelectron spectroscopy'.split('|')

def synonyms():
    return {normalize(s):normalize(group[0]) for group in SYNONYM_GROUPS for s in group}
