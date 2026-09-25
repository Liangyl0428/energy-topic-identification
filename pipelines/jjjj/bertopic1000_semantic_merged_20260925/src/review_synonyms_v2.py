"""Render explicitly selected candidates; similarity scores never decide merges."""
from merge_common import *
import argparse
import pyarrow.parquet as pq

CANDIDATES = [
    [0,252], [51,115,443,894], [78,334], [104,791], [159,376],
    [171,922], [281,682], [297,720], [381,615,876], [350,703],
    [253,526,879], [558,963], [324,692,713], [470,549], [451,536],
    [59,268,603,650,773,858,900], [199,776,850], [341,685],
    [130,939], [264,759,864], [393,498,966], [66,220,384,787],
    [360,534,608], [140,158,843,974], [29,977], [6,632],
    [48,388,452], [347,729,946,983], [593,880], [538,638,641],
    [598,689], [112,308,438,495,768,866], [203,933,950], [131,990],
    [323,626], [43,259,649,750], [482,627,762,942,964],
    [623,772,785], [274,702,805], [333,435,679], [462,833],
    [577,634,848], [610,982], [212,683,803], [604,985],
    [668,744], [169,348,375,893], [563,644], [738,953],
    [616,948], [142,177],
]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--start',type=int,default=0)
    p.add_argument('--stop',type=int,default=len(CANDIDATES))
    p.add_argument('--chars',type=int,default=0)
    p.add_argument('--topics',nargs='+',type=int)
    a=p.parse_args()
    cards=read(BASE/'review/topic_cards.json')
    evidence=pq.read_table(RAW/'evidence/review_documents.parquet').to_pandas()
    selected=CANDIDATES[a.start:a.stop] if a.topics is None else [a.topics]
    records=[]
    for ix,g in enumerate(selected,a.start):
        print(f'\nCANDIDATE {ix}: {g}')
        for i in g:
            t=cards[i]
            print(f"T{i:04d} n={t['documents']} KW:{t['keywords']}")
            dominant=max([('paper',t['papers']),('patent',t['patents']),('policy',t['policies'])],key=lambda s:s[1])[0]
            v=evidence[(evidence.cluster==i)&(evidence.source==dominant)]
            for r in v.itertuples():
                if not set(r.selection_roles.split('|'))&{'center:1','center:2','random:1','random:2','boundary:1'}:
                    continue
                print(f' {r.row_id} {r.source} {r.selection_roles}: {r.title}')
                if a.chars:
                    print('  '+str(r.body)[:a.chars].replace('\n',' '))
                records.append(dict(topic=i,row_id=int(r.row_id),source=r.source,title=r.title,
                    selection_roles=r.selection_roles,body_excerpt=str(r.body)[:a.chars],
                    body_characters_shown=min(a.chars,len(str(r.body))),body_sha256=r.body_sha256,
                    source_part=r.source_part))
    tag=f'{a.start:02d}_{a.stop:02d}' if a.topics is None else 'topics_'+'_'.join(map(str,a.topics))
    dump(BASE/f'evidence/synonyms_v2_{tag}_{a.chars}.json',dict(created_utc=now(),
        scope='dominant-source full titles plus the explicitly shown leading body excerpts',
        candidate_groups=selected,records=records))

if __name__=='__main__':
    main()
