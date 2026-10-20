from curation import *
from common import WORK
import pandas as pd

# Reproduce the exact 170 remaining high-frequency names inspected in this review.
_known={normalize(s) for t in TOPICS for m in ['direct','conditional'] for s in t[m]}
_known|={normalize(s) for s in OUTSIDE_TERMS+BROAD_TERMS+AUXILIARY_TERMS}
_v=pd.read_csv(WORK/'all_raw_keywords.csv')
_reviewed_aux=_v[~_v.normalized_name.isin(_known)].sort_values('document_frequency',ascending=False).head(170)
AUXILIARY_TERMS.extend(_reviewed_aux.raw_name.tolist())

def extend(code,mode,words):
    next(t for t in TOPICS if t['topic_code']==code)[mode].extend(s.strip() for s in words.split('|') if s.strip())

extend('KWD-T0013','direct','Clementine (nuclear reactor)')
extend('KWD-T0014','direct','Chernobyl Nuclear Accident')
extend('KWD-T0019','direct','Nanoarchitectures for lithium-ion batteries')
extend('KWD-T0026','direct','Mains electricity|Transmission tower')
extend('KWD-T0027','conditional','Synchronization (alternating current)|Direct current|Alternating current|Load rejection')
extend('KWD-T0028','conditional','Automatic frequency control|Frequency deviation|Frequency regulation|Low-frequency oscillation|Load sharing')
extend('KWD-T0029','conditional','Load profile|Load shifting|Peak demand|Peak load|Dynamic demand|Demand management|Demand reduction')
extend('KWD-T0030','direct','Volt-ampere reactive|Power conditioner')
extend('KWD-T0031','conditional','Inrush current')
extend('KWD-T0034','direct','Sweep frequency response analysis')
extend('KWD-T0037','direct','PWM rectifier')
extend('KWD-T0037','conditional','Topology (electrical circuits)|Rectification|Commutation cell|Load regulation')
extend('KWD-T0038','conditional','Switching frequency|Pulse-frequency modulation')
extend('KWD-T0040','direct','Variable-frequency drive')
extend('KWD-T0040','conditional','Electrical steel')
extend('KWD-T0044','direct','Traction substation')
extend('KWD-T0045','direct','Resonant inductive coupling')
extend('KWD-T0048','direct','Absorption refrigerator|Vapor-compression refrigeration|Chiller|Heating system|Water chiller|Water heater|Storage water heater|Water heating|Storage heater|Magnetic refrigeration|Radiant heating|Renewable heat|Hybrid heat')
extend('KWD-T0048','conditional','Cooling load|Heat load|Heating degree day')
extend('KWD-T0050','direct','Brayton cycle|Thermoacoustic heat engine')
extend('KWD-T0050','conditional','Heat pipe|Heat sink|Heat flux|Heat engine|Carnot cycle|Heat transfer enhancement|Convective heat transfer|Heat transfer fluid|Heat spreader|Enhanced heat transfer|Sensible heat|Dynamic scraped surface heat exchanger')
extend('KWD-T0051','conditional','Turbomachinery|Air preheater|Superheater|Feedwater heater|Superheated steam|Heat of combustion')
extend('KWD-T0052','conditional','Coal field|Problems in coal mining|Coal water')
extend('KWD-T0055','direct','Heating oil')
extend('KWD-T0065','conditional','Rectifier (neural networks)')
extend('KWD-T0066','conditional','Fuzzy logic|Nonlinear system|Algorithm')
extend('KWD-T0068','direct','Electrochemical energy conversion')
extend('KWD-T0068','conditional','Electrochemistry|Polarization (electrochemistry)|Electrochemical window|Electrochemical cell|Electrochemical kinetics|Cyclic voltammetry|Electrochemical potential')
extend('KWD-T0069','conditional','Graphitic carbon nitride|Carbon nitride|Carbon black|Graphite|Carbonization|Pyrolytic carbon|Amorphous carbon|Glassy carbon|Carbon quantum dots|Carbon nanofoam|Carbide-derived carbon|Carbon nanotube supported catalyst|Composite material|Alloy|Mesoporous material|Nanostructure|Nanorod|Nanocrystal|Heterojunction|Perovskite (structure)|Thermal stability')
add('电热与工业电气化','电阻、感应、微波等电热过程及工业电热设备。',
    'Electric heating|Induction heating|Dielectric heating|Electric arc furnace|Electromagnetic heating',
    'Joule heating|Microwave heating|Heating element|Electric resistance welding|Infrared heater')
AUXILIARY_TERMS.extend('Voltage source|Threshold voltage|Low voltage|Supply and demand|Ethylene carbonate|Propylene carbonate|Electric arc|Charcoal|Gaseous diffusion|Ambipolar diffusion|Dropout voltage|Hydrogenase|Overheating (electricity)|Frequency response|Frequency domain|Radio frequency|Chemical oxygen demand|Carbonation|Carbon film|Carbon steel|Carbon cycle|Carbon sink|Carbon stock|Hydrogen sulfide|Hydrogen embrittlement|Electrolytic capacitor|Decoupling capacitor|Film capacitor|Filter capacitor|Ceramic capacitor|Polymer capacitor|Tantalum capacitor|Ferroelectricity|Transmission system|Hydraulic machinery|Direct-buried cable|Cable gland|Shielded cable|High-resolution transmission electron microscopy'.split('|'))
