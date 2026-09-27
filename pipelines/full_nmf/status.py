"""Read-only progress report; a running job is never reported as delivered."""
from common import *


def report():
    def read(name):
        path=RUN/name
        return json.loads(path.read_text()) if path.exists() else None
    training=read('TRAINING_PROGRESS.json')
    prepared=read('PREPARE_COMPLETE.json')
    audits=[json.loads(p.read_text()) for p in (RUN/'embeddings').glob('part-*.json') if '.checkpoint.' not in p.name]
    completed=sum(a['documents'] for a in audits)
    current=read('ENCODING_PROGRESS.json')
    encoded=completed
    if current and not (RUN/'embeddings'/(current['part']+'.json')).exists():
        encoded+=current['position']
    result={'status':'complete' if (RUN/'ALL_REPOSITORIES_COMPLETE.json').exists() else 'in_progress_or_interrupted',
        'run_directory':str(RUN),'training_progress':training,
        'encoding_completed_part_records':completed,'encoding_visited_including_partial':encoded,
        'encoding_completed_parts':len(audits),'encoding_progress':current,
        'completed_stages':[p.stem for p in sorted(RUN.glob('*COMPLETE.json'))]}
    if prepared:
        result['paper_population']=prepared['paper_count']
        result['nonzero_keyword_papers']=prepared['nonzero_papers']
    if training and prepared:
        result['training_visit_fraction']=training['paper_visits']/(training['epochs']*prepared['nonzero_papers'])
    if (RUN/'SUMMARY.json').exists():result['classification_summary']=read('SUMMARY.json')
    result['postprocess']=read('postprocess/STATUS.json')
    result['remote_delivery_complete']=read('FULL_DELIVERY_AND_PUSH_COMPLETE.json')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':report()
