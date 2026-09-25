from common import *
import numpy as np
from tokenizers import Tokenizer
import onnxruntime as ort

pairs = [
('光伏出力预测', 'Short-term photovoltaic power generation forecasting using weather and irradiance data.', '基于天气与辐照度数据的光伏发电短期出力预测。'),
('光伏最大功率跟踪', 'Maximum power point tracking control for photovoltaic panels under partial shading.', '局部阴影条件下光伏组件最大功率点跟踪控制。'),
('钙钛矿光伏器件', 'Defect passivation and charge recombination in perovskite solar cells.', '钙钛矿太阳能电池中的缺陷钝化与电荷复合。'),
('风电出力预测', 'Probabilistic wind power forecasting using numerical weather prediction.', '基于数值天气预报的风力发电功率概率预测。'),
('风机尾流控制', 'Wind turbine wake steering and wind farm aerodynamic optimization.', '风力发电机尾流转向控制与风电场气动优化。'),
('风机齿轮箱诊断', 'Fault diagnosis of wind turbine gearboxes using vibration signals.', '利用振动信号诊断风电机组齿轮箱故障。'),
('电池荷电状态', 'State of charge estimation of lithium-ion batteries using an extended Kalman filter.', '利用扩展卡尔曼滤波估计锂离子电池荷电状态。'),
('电池健康状态', 'State of health estimation and remaining useful life prediction for lithium-ion batteries.', '锂离子电池健康状态估计与剩余使用寿命预测。'),
('电池热失控', 'Thermal runaway propagation and fire suppression in lithium-ion battery packs.', '锂离子电池组热失控传播与火灾抑制。'),
('固态电池电解质', 'Solid electrolytes and electrode interface resistance in all-solid-state lithium batteries.', '全固态锂电池的固态电解质与电极界面电阻。'),
('钠离子电池', 'Cathode materials and sodium ion transport in sodium-ion batteries.', '钠离子电池正极材料与钠离子传输。'),
('锂硫电池', 'Polysulfide shuttle suppression in lithium-sulfur batteries.', '锂硫电池多硫化物穿梭效应抑制。'),
('质子交换膜电解水', 'Proton exchange membrane water electrolysis for green hydrogen production.', '质子交换膜电解水制取绿氢。'),
('碱性电解水', 'Alkaline water electrolysis using nickel-based catalysts for hydrogen production.', '采用镍基催化剂的碱性电解水制氢。'),
('固体氧化物电解', 'High temperature steam electrolysis using solid oxide electrolysis cells.', '利用固体氧化物电解池进行高温蒸汽电解。'),
('质子交换膜燃料电池', 'Water management and durability of proton exchange membrane fuel cells.', '质子交换膜燃料电池水管理与耐久性。'),
('配电网继电保护', 'Adaptive relay protection and fault location in active distribution networks.', '有源配电网自适应继电保护与故障定位。'),
('电网暂态稳定', 'Transient stability assessment of power systems following severe grid faults.', '严重电网故障后的电力系统暂态稳定评估。'),
('构网型变流器', 'Grid-forming inverter control and frequency stability in low-inertia power systems.', '低惯量电力系统中的构网型逆变器控制与频率稳定。'),
('电价预测', 'Day-ahead electricity price forecasting in wholesale electricity markets.', '批发电力市场日前电价预测。'),
('电力负荷预测', 'Short-term electricity load forecasting using historical demand and temperature.', '基于历史需求与气温的短期电力负荷预测。'),
('需求响应', 'Residential demand response and flexible load scheduling under dynamic electricity tariffs.', '动态电价下的居民需求响应与柔性负荷调度。'),
('虚拟电厂', 'Virtual power plant aggregation and coordinated dispatch of distributed energy resources.', '虚拟电厂分布式能源聚合与协调调度。'),
('碳排放测量', 'Measurement, reporting and verification of greenhouse gas emissions from energy systems.', '能源系统温室气体排放的测量、报告与核证。'),
('碳捕集封存', 'Carbon dioxide capture from flue gas and geological storage in saline aquifers.', '烟气二氧化碳捕集与咸水层地质封存。'),
('核裂变反应堆', 'Neutron transport and safety analysis of nuclear fission reactors.', '核裂变反应堆中子输运与安全分析。'),
('核聚变等离子体', 'Plasma confinement and magnetohydrodynamic instabilities in tokamak fusion reactors.', '托卡马克核聚变装置的等离子体约束与磁流体不稳定性。'),
('热泵', 'Refrigerant selection and coefficient of performance of air-source heat pumps.', '空气源热泵制冷剂选择与性能系数。'),
('地热开发', 'Enhanced geothermal systems and hydraulic stimulation of hot dry rock reservoirs.', '增强型地热系统与干热岩储层水力改造。'),
('生物质气化', 'Biomass gasification and tar removal for synthesis gas production.', '生物质气化与焦油去除制备合成气。'),
('超高压绝缘', 'Insulation coordination and partial discharge detection in ultra-high-voltage equipment.', '特高压设备绝缘配合与局部放电检测。'),
('电力现货市场', 'Electricity spot market clearing rules and generation capacity remuneration mechanisms.', '电力现货市场出清规则与发电容量补偿机制。')
]
M = BASE / 'models/multilingual_minilm'
tok = Tokenizer.from_file(str(M / 'tokenizer.json')); tok.enable_padding(pad_id=1,pad_token='<pad>'); tok.enable_truncation(max_length=128)
texts = [r[1] for r in pairs] + [r[2] for r in pairs]
e = tok.encode_batch(texts)
feed = {'input_ids': np.array([x.ids for x in e],dtype=np.int64),'attention_mask':np.array([x.attention_mask for x in e],dtype=np.int64),'token_type_ids':np.array([x.type_ids for x in e],dtype=np.int64)}
opt=ort.SessionOptions();opt.intra_op_num_threads=2;opt.log_severity_level=3
sess=ort.InferenceSession(str(M/'onnx/model_O4_pooled.onnx'),sess_options=opt,providers=['CUDAExecutionProvider','CPUExecutionProvider'])
v=sess.run(None,feed)[0];n=len(pairs);sim=v[:n]@v[n:].T
result=[]
for i,r in enumerate(pairs):
    order=np.argsort(sim[i])[::-1]
    result.append({'direction':r[0],'english':r[1],'chinese':r[2],'paired_cosine':float(sim[i,i]),'retrieved_direction':pairs[order[0]][0],'paired_rank':int(np.flatnonzero(order==i)[0])+1,'closest_other':pairs[next(int(j) for j in order if j!=i)][0]})
audit={'pairs':n,'english_to_chinese_top1':float(np.mean(np.argmax(sim,axis=1)==np.arange(n))),'chinese_to_english_top1':float(np.mean(np.argmax(sim,axis=0)==np.arange(n))),'purpose':'handwritten cross-language technical retrieval sanity check only; not corpus classification accuracy or independent gold validation','results':result,'created_utc':now()}
dump(BASE/'models/MULTILINGUAL_SANITY_CHECK.json',audit)
print({k:v for k,v in audit.items() if k!='results'})
for r in result:
    if r['paired_rank']>1: print('MISMATCH',r)
