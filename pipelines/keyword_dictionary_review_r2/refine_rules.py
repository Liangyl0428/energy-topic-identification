"""Narrow domain-specific conditional terms after the first 142-relation review.

Global energy co-occurrence is sufficient only for supporting method/economy
labels. A generic dielectric is not evidence for power insulation in a solar
cell; generic plasma is not evidence for nuclear fusion in a battery paper.
"""
from curation_additions import *

def move_auxiliary(words, broad=False):
    labels=words.split('|');norm={normalize(w) for w in labels}
    for t in TOPICS:
        for mode in ['direct','conditional']:
            t[mode]=[w for w in t[mode] if normalize(w) not in norm]
    (BROAD_TERMS if broad else AUXILIARY_TERMS).extend(labels)

move_auxiliary('Electrical engineering|Power engineering|Electrical engineering technology|Nuclear engineering|Petroleum engineering',True)
move_auxiliary('Electrical network|Electric network|Separator (oil production)|Metering mode')
for code,word in [(35,'Transmission line'),(41,'Generator (circuit theory)')]:
    t=TOPICS[code-1]
    t['direct'].remove(word);t['conditional'].append(word)

# An empty family means any explicit energy anchor; otherwise these are the
# ONLY allowed direct-topic anchors. Eligibility is evaluated per keyword hit.
GLOBAL_SUPPORT={50,57,58,59,60,61,62,65,66,67,68,69,70}
FAMILIES={
 4:[1,2,3,4,5], 11:[11,12], 13:[13,14], 14:[13,14],
 16:[16,17,18],17:[16,17,18],20:[19,20],22:[22,23],
 26:[26,27,28,29,30,31,34,35,36],27:[26,27,28,29,30,36],
 28:[24,25,26,27,28,29,36],29:[24,25,26,27,28,29,30,36],
 30:[26,27,30,36,37,38],31:[26,27,31,32,34,35,36],
 32:[31,32,33,34,35,36],33:[26,27,31,32,33,34,35,36],
 35:[26,27,31,32,33,34,35,36],
 37:[1,2,6,24,36,37,38,39,40,41,42,44,45],
 38:[1,2,6,24,36,37,38,39,40,41,42,44,45],
 39:[1,2,6,24,36,37,38,39,40,41,42,44,45],
 40:[40,41,42,43,44],41:[6,7,8,9,13,15,41,50,51],
 42:[42,43,44],48:[22,48,49],55:[11,12,52,53,54,55],
 63:[1,2,3,4,5,6,7,8,9,10,11,12,18,24,25,46,47,49,63],
}

def conditional_anchors(topic_code):
    num=int(topic_code.split('T')[-1])
    if num in GLOBAL_SUPPORT:return []
    return [f'KWD-T{i:04d}' for i in FAMILIES.get(num,[num])]

# Second pass: explicit reading of the 130 highest-frequency energy-spelling
# candidates; spelling only selected the review queue, never a membership rule.
extend('KWD-T0054','direct','Crude oil|Oil shale|Enhanced oil recovery|Oil production|Unconventional oil|Oil reserves|Oil field|Shale oil|Water injection (oil production)|Oil supply|Oil sands|Peak oil')
extend('KWD-T0060','direct','Oil price')
extend('KWD-T0055','conditional','Pyrolysis oil|Hydrodeoxygenation|Residual oil')
extend('KWD-T0051','conditional','Oxy-fuel|Reboiler|Nucleate boiling')
extend('KWD-T0068','conditional','Linear sweep voltammetry|Voltammetry|Standard hydrogen electrode|Palladium-hydrogen electrode')
extend('KWD-T0069','conditional','Layered double hydroxides|Cobalt hydroxide|Lithium hydroxide|Superhydrophobic coating')
extend('KWD-T0033','conditional','Soil resistivity')
extend('KWD-T0032','conditional','Dielectric barrier discharge')
# Remaining inspected words are ambiguous/generic, not declared irrelevant.
AUXILIARY_TERMS.extend('Soil science|Soil water|Hydrolysis|Hydrothermal synthesis|Hydrology (agriculture)|Mineralization (soil science)|Electric potential energy|FOIL method|Airfoil|Hydrochloric acid|Magnetohydrodynamic drive|Inert gas|Wind tunnel|Hydrometallurgy|Self-healing hydrogels|Boiling|Hydroxyl radical|Sodium hydroxide|Energy-dispersive X-ray spectroscopy|Turbulence kinetic energy|Gate dielectric|Potassium hydroxide|RF power amplifier|Voltage divider|Anhydrous|Palm oil|Hydrogeology|Electrically powered spacecraft propulsion|Tetrahydrofuran|Gas chromatography|Hydrostatic pressure|Superhydrophilicity|Coalescence (physics)|Electrohydrodynamics|Frequency grid|Soil carbon|Electrical contacts|Gas phase|Voltage reference|Boiling point|Power dividers and directional couplers|High energy|Tetracycline Hydrochloride|Transient voltage suppressor|Mineral oil|Ionization energy|Hydrostatic equilibrium|Hydrotalcite|Electron energy loss spectroscopy|Magnetic energy|Rogowski coil|Soil contamination|Hydroxylation|Photon energy|Hydroquinone|Degenerate energy levels|Hydrofluoric acid|Pulsed power|Ammonium hydroxide|High-κ dielectric|Hydrolysate|Voltage-controlled oscillator|Soil organic matter|Acid gas|Fermi energy|Förster resonance energy transfer|Torsion (gastropod)|Superconducting Coils|Enzymatic hydrolysis|Electrochemical gas sensor|Engine power|Metal hydroxide|Peak inverse voltage|Wilkinson power divider|Power point|Maximum sustained wind|Hydrothermal reaction|Vegetable oil|Shear strength (soil)|5-hydroxymethylfurfural|Low energy|Transmitter power output|Thermal hydrolysis|Power integrity|Radiant energy|Hydroelasticity|Electric light|Constant voltage|Hydrochloride|Industrial gas|Laser power scaling|Hydrogenolysis|Calcium hydroxide|Soil test|Outgassing|Voltage reduction|Soil fertility|Bond-dissociation energy|Soil compaction|Oil spill|High-power impulse magnetron sputtering'.split('|'))

# Generic energy concepts are named honestly, without implying a narrower use.
TOPICS[12]['name']='核能设施与核反应堆工程'
TOPICS[12]['definition']='核能发电、核电厂、核反应堆及裂变系统；通用核能词也可与聚变工程主题重叠。'
TOPICS[22]['name']='储能通用技术与系统集成'
TOPICS[22]['definition']='储能通用概念、并网储能、磁储能及集成；Energy storage词本身不能证明研究处于系统层。'
TOPICS[60]['name']='能源供需、资源与供能系统'
TOPICS[60]['definition']='能源需求、供应、资源、结构、规划、电气化及发电供能系统。'
