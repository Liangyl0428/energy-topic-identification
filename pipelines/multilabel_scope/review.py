"""Build a reproducible evidence packet; scope decisions are a separate ledger."""
from run import *
import re

DIR=OUT/'review'
ENERGY_PATTERN = re.compile(
    r'\b(?:electric(?:al)? (?:power|grid|energy|network)|electricity|power (?:grid|system|generation|plant|transmission|distribution|converter)|'
    r'smart grid|microgrid|photovoltaic|solar (?:cell|power|energy|panel|thermal)|wind (?:power|turbine|farm|energy)|'
    r'fuel cell|hydrogen (?:production|storage|energy)|hydrogen evolution|water splitting|'
    r'energy (?:storage|transition|efficiency|policy|market|system|management|security|consumption|saving|harvesting)|'
    r'renewable (?:energy|power)|batter(?:y|ies)|supercapacitor|lithium.ion|sodium.ion|'
    r'electrocataly|electroly[sz]|power electronic|inverter|converter|electric vehicle|charging station|'
    r'demand response|load forecasting|optimal power flow|high.voltage|HVDC|heat pump|'
    r'geothermal|hydropower|hydroelectric|biofuel|biodiesel|biogas|nuclear (?:power|reactor)|'
    r'thermoelectric|carbon (?:capture|trading|pricing|neutral)|decarboni[sz]|coal.fired|combustion|gas turbine|steam turbine)\w*\b'
    r'|电网|电力|发电|光伏|风电|风能|储能|电池|燃料电池|制氢|储氢|电解水|能源|充电|逆变|换流|特高压|碳中和|碳交易|碳捕集', re.I)


def make_packet():
    DIR.mkdir(parents=True, exist_ok=True)
    if (DIR/'PACKET_COMPLETE.json').exists():return
    h=np.load(OUT/'full_model/components.npy')
    vocab=pd.read_csv(FROZEN/'vocabulary.csv')
    p=np.load(OUT/'transfer/reference_contributions.npy',mmap_mode='r')
    m=pd.read_parquet(OUT/'transfer/reference_metadata.parquet')
    valid=np.load(OUT/'transfer/reference_valid.npy')
    text=m.title.fillna('')+' '+m.body_excerpt.fillna('')
    hit=text.str.contains(ENERGY_PATTERN).to_numpy()
    samples=[];catalog=[]
    for t in range(K):
        top=np.argsort(-h[t],kind='stable')[:15]
        support=np.flatnonzero((p[:,t]>=.10)&valid)
        high=support[np.argsort(-p[support,t],kind='stable')[:3]]
        random=np.random.default_rng(20261019+t).choice(support,size=min(5,len(support)),replace=False)
        indices=list(dict.fromkeys([*high,*random]))
        if not indices:
            indices=[int(np.argmax(p[:,t]))]
        for j in indices:
            r=m.iloc[j]
            samples.append({'topic_id':t,'topic_code':f'RBK500-T{t+1:04d}','row_id':int(r.row_id),
                'doc_id':r.doc_id,'title':r.title,'body_excerpt':r.body_excerpt,'date':r.date,'title_only':bool(r.title_only),
                'contribution':float(p[j,t]),'sample_kind':'high_contribution' if j in high else 'fixed_random',
                'energy_anchor_present':bool(hit[j]),'energy_anchor_matches':' | '.join(dict.fromkeys(x.group(0) for x in ENERGY_PATTERN.finditer(text.iloc[j]))),
                'url':r.url})
        catalog.append({'topic_id':t,'topic_code':f'RBK500-T{t+1:04d}',
            'name':' / '.join(vocab.display_name.iloc[top[:3]]),'top_keywords':' | '.join(vocab.display_name.iloc[top]),
            'reference_support_010':len(support),'energy_anchor_fraction_reference':float(hit[support].mean()) if len(support) else None,
            'top_keyword_squared_norm_fraction':float(h[t,top[0]]**2/np.maximum((h[t]**2).sum(),1e-20)),
            'scope_state':'review','reviewer':'not_yet_reviewed','scope_reason':'Await content review',
            'evidence_doc_ids':' | '.join(m.doc_id.iloc[indices]),
            'screening_note':'Energy-anchor fraction is a reading aid; absence is not evidence of irrelevance.'})
    pd.DataFrame(catalog).to_csv(DIR/'topic_review_packet.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(samples).to_parquet(DIR/'topic_evidence.parquet',index=False)
    pd.DataFrame(samples).to_csv(DIR/'topic_evidence.csv',index=False,encoding='utf-8-sig')
    write(DIR/'PACKET_COMPLETE.json',{'topics':K,'evidence_rows':len(samples),
        'sampling':'Up to 3 highest contributions and 5 fixed random qualifying reference papers per topic, deduplicated. Reference population is a fixed 200000-paper sample, not all papers.',
        'scope_rule':'Use tender paragraphs and content, not energy-anchor hits alone; preserve uncertain topics as review.'})


def show(lo,hi,details=False):
    topics=pd.read_csv(DIR/'topic_review_packet.csv').fillna('')
    samples=pd.read_parquet(DIR/'topic_evidence.parquet')
    for r in topics.iloc[lo:hi].itertuples():
        print(f'\n{r.topic_code}: {r.name}; 支持={r.reference_support_010}; 锚点比例={r.energy_anchor_fraction_reference}')
        print('关键词:',r.top_keywords)
        own=samples[samples.topic_id==r.topic_id]
        shown=own if details else pd.concat([own.head(1),own[own.sample_kind=='fixed_random'].head(2)]).drop_duplicates('doc_id')
        for s in shown.itertuples():
            print(f'  {s.doc_id} p={s.contribution:.3f} [{s.sample_kind}] {s.title}')
            if details:print('   ',str(s.body_excerpt)[:1000])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['packet','show']);parser.add_argument('--start',type=int,default=0);parser.add_argument('--end',type=int,default=50);parser.add_argument('--details',action='store_true');args=parser.parse_args()
    if args.stage=='packet':make_packet()
    else:show(args.start,args.end,args.details)
