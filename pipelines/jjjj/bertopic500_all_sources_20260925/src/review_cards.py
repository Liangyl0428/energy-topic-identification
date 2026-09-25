from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument('start',type=int);p.add_argument('end',type=int);args=p.parse_args()
cards=json.loads((BASE/'evidence/cluster_review_cards.json').read_text())
audit=json.loads((BASE/'models/CLUSTER_AUDIT.json').read_text());weights=audit['per_document_training_weights']
shown={}
for r in cards[args.start:args.end]:
    n={'paper':r['papers'],'patent':r['patents_2026'],'policy':r['policies']}
    major=max(n,key=lambda s:n[s]*weights[s])
    selected=[x for x in r['examples'] if x['source']==major]
    selected += [x for x in r['examples'] if x['source']!=major and x['role']=='center:1' and n[x['source']]>=min(20,max(1,r['documents']*.01))]
    shown[str(r['cluster'])]=[x['row_id'] for x in selected]
    keywords='/'.join(r['keywords'].split(' | ')[:5])
    print(f"{r['raw_topic_id']} [{n['paper']}/{n['patent']}/{n['policy']}] {keywords}")
    for x in selected:
        content=x['title'] or x['body_preview']
        source_code={'paper':'L','patent':'A','policy':'G'}[x['source']]
        print(f" {source_code}{x['role'][0]}#{x['row_id']}: {content[:115]}")
dump(BASE/f'evidence/displayed_rows_{args.start:03d}_{args.end:03d}.json',shown)
