from refine_common import *
import argparse
p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');p.add_argument('--start',type=int,required=True);p.add_argument('--stop',type=int,required=True);p.add_argument('--body',type=int,default=0);p.add_argument('--compact',action='store_true');p.add_argument('--file')
a=p.parse_args();name=a.file or ('partial_review_samples.json' if a.partial else 'final_review_samples.json')
data=read(BASE/'evidence'/name);records=data['records'][a.start:a.stop];shown=[]
last=None
for r in records:
    if a.compact:
        if last!=r['final_topic_id']:print(r['final_topic_id'],r['final_topic_label']);last=r['final_topic_id']
        print(r['row_id'],r['old_parent_id'],f"{r['semantic_support_cosine']:.3f}",r['title'])
    else:print(r['row_id'],r['old_parent_id'],'->',r['final_topic_id'],r['final_topic_label'],f"{r['semantic_support_cosine']:.3f}",r['title'])
    n=min(a.body,len(r['body_excerpt']))
    if n:print('BODY',r['body_excerpt'][:n])
    shown.append(dict(row_id=r['row_id'],topic_id=r['final_topic_id'],title=r['title'],body_characters_shown=n))
dump(BASE/'evidence'/f'read_log_{Path(name).stem}_{a.start}_{a.stop}_{a.body}.json',dict(records=shown,source=name,source_sha256=sha(BASE/'evidence'/name)))
