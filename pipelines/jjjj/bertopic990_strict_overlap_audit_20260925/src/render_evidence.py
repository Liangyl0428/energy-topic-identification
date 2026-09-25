from audit_metrics import *
import argparse

p=argparse.ArgumentParser()
p.add_argument('--start',type=int,required=True)
p.add_argument('--stop',type=int,required=True)
p.add_argument('--chars',type=int,default=200)
a=p.parse_args()
e=read(AUDIT/'evidence/audit_samples.json')
t=pd.read_csv(BASE/'results/final_topics.csv').fillna('').set_index('final_topic_id')
records=[]
for case in e['cases'][a.start:a.stop]:
    print('\nCASE',case['case_id'],case['title'])
    for tid in case['topics']:
        row=t.loc[tid]
        print(tid,'N=',row.documents,'KW:',row.keywords)
        for r in e['records']:
            if r['topic_id']!=tid:continue
            n=min(a.chars,len(r['body_excerpt'])) if r['selection'].startswith('existing') else 0
            print(r['row_id'],r['selection'],r['source'],r['title'])
            if n:print('  '+r['body_excerpt'][:n].replace('\n',' '))
            records.append(dict(row_id=r['row_id'],topic_id=tid,title=r['title'],selection=r['selection'],body_characters_shown=n))
dump(AUDIT/f'evidence/read_log_{a.start}_{a.stop}_{a.chars}.json',dict(records=records,
    cases=[x['case_id'] for x in e['cases'][a.start:a.stop]],scope='full titles, leading body excerpt only for existing center records'))
