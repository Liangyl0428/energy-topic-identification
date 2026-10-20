"""Frozen, sequential name-reading ledger. No automatic semantic decisions.

`show` presents every term in a batch. `commit` only persists the assistant's
explicit reading decision supplied as JSON; frequency/spelling never sets it.
Future contexts can resume from PROGRESS.json without resetting evidence.
"""
from pathlib import Path
import json, hashlib, argparse
import pandas as pd

from common import ROOT, WORK

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def read(path):return json.loads(path.read_text())

REASONS={
 'boundary':('general_auxiliary','known_energy_boundary_not_activated',
   '词义已读且存在广义能源关联，但当前主题或业务边界不足以支持可靠归属；明确保留边界复核，不强塞到邻近主题。'),
 'auxiliary_context':('general_auxiliary','non_specific_or_context_dependent',
   '逐项读过词名；该词不足以独立指认能源电力技术主题，暂不设触发关系。是否在具体文献中属于能源应用需结合语境；不等同与能源无关。'),
 'outside':('excluded','explicit_non_energy_sense',
   '逐项读过词名；该词所指对象或词义为非能源领域，不用作能源主题触发；保留词和含词论文。'),
 'broad':('broad_auxiliary','broad_field',
   '逐项读过词名；属于学科、行业或过宽领域，不能独立指认具体能源技术主题。'),
 'uncertain':('general_auxiliary','term_meaning_requires_context',
   '已读词名，但缩写、专名或多义性无法仅据词名可靠判断；保持不触发并记录语义待核。'),
 'keep':(None,'explicit_recheck_of_existing_decision',
   '逐项重读词名并复核既有词典决策；保留既有处理，不据词名声称所有论文语境准确。'),
}

def indices(text):
    out=[]
    for p in text.replace(' ','').split(','):
        if not p:continue
        if '-' in p:
            a,b=map(int,p.split('-'));out.extend(range(a,b+1))
        else:out.append(int(p))
    assert len(out)==len(set(out)), 'Repeated index within one group'
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['show','commit','status'])
    ap.add_argument('--size',type=int,default=600);ap.add_argument('--spec');args=ap.parse_args()
    progress=read(WORK/'PROGRESS.json')
    assert sha(Path(progress['source_dictionary']))==progress['source_sha256']
    if args.action=='status':print(json.dumps(progress,ensure_ascii=False,indent=2));return
    batchno=len(progress['batch_manifest'])+1
    batchpath=WORK/'batches'/f'batch_{batchno:03d}_input.json'
    if args.action=='show':
        if not batchpath.exists():
            q=pd.read_parquet(WORK/'frozen_review_queue.parquet')
            frame=q.iloc[progress['reviewed_in_this_full_pass']:progress['reviewed_in_this_full_pass']+args.size]
            write(batchpath,{'batch':batchno,'source_dictionary_sha256':progress['source_sha256'],
              'terms':frame[['review_index','keyword_code','display_name','canonical_name','document_frequency','decision','topic_code']].to_dict('records')})
        data=read(batchpath)
        print('BATCH',batchno,'SHA256',sha(batchpath),'TERMS',len(data['terms']))
        for r in data['terms']:
            extra = "" if r["decision"]=="unreviewed" else f" [{r['decision']}:{r['topic_code']}]"
            print(f"{r['review_index']} {r['display_name']}{extra}")
        return
    assert args.spec and batchpath.exists(),'Show the batch and read it before committing'
    spec=read(Path(args.spec));data=read(batchpath)
    assert spec['input_sha256']==sha(batchpath),'Wrong cohort hash'
    assert spec['read_all_names'] is True and spec['summary'].strip()
    decisions={}
    for r in data['terms']:
        state,meaning,reason=REASONS[spec['default']]
        decisions[r['review_index']]={**r,'prior_decision':r['decision'],'prior_topic_code':r['topic_code'],
          'decision':state or r['decision'],'topic_code':r['topic_code'] if state is None else '',
          'semantic_category':meaning,'reason':reason,'review_scope':'term_name_only',
          'reviewer':'assistant','batch':batchno,'input_sha256':sha(batchpath),'expert_approved':False}
    seen=set()
    for group in spec.get('groups',[]):
        for i in indices(group['indices']):
            assert i in decisions and i not in seen, i
            seen.add(i);d=decisions[i]
            if group.get('kind') in REASONS:
                state,meaning,reason=REASONS[group['kind']]
                d.update(decision=state or d['prior_decision'],topic_code=d['prior_topic_code'] if state is None else '',semantic_category=meaning,reason=group.get('reason',reason))
            else:
                assert group['decision'] in ['direct','conditional'] and group['topic_code'].startswith('KWD-T')
                d.update(decision=group['decision'],topic_code=group['topic_code'],semantic_category='explicit_energy_mapping_candidate',reason=group['reason'])
                d['requires_article_sample_review']=True
    out=WORK/'batches'/f'batch_{batchno:03d}_review.json'
    assert not out.exists(),'Already committed'
    write(out,{'batch':batchno,'input_sha256':sha(batchpath),'reading_statement':spec['summary'],
       'automatic_semantic_assignment':False,'read_all_names':True,'decisions':list(decisions.values())})
    progress['reviewed_in_this_full_pass']+=len(decisions)
    progress['batch_manifest'].append({'batch':batchno,'terms':len(decisions),'input_sha256':sha(batchpath),
      'review_file':str(out.relative_to(WORK)),'review_sha256':sha(out)})
    write(WORK/'PROGRESS.json',progress)
    frames=[pd.DataFrame(read(WORK/b['review_file'])['decisions']) for b in progress['batch_manifest']]
    pd.concat(frames,ignore_index=True).to_csv(WORK/'term_review_ledger.csv',index=False,encoding='utf-8-sig')
    print(json.dumps({'batch_committed':batchno,'read_in_full_pass':progress['reviewed_in_this_full_pass'],
      'total_terms':progress['total_terms'],'remaining':progress['total_terms']-progress['reviewed_in_this_full_pass'],
      'proposed_states':pd.DataFrame(decisions.values()).decision.value_counts().to_dict()},ensure_ascii=False))

if __name__=='__main__':main()
