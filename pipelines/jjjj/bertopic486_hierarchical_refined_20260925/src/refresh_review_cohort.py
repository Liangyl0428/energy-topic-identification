"""Keep the reviewed cohort fixed, and expose final accepted OR deferred outcomes."""
from refine_common import *

def main():
    original=read(BASE/'evidence/round3_review_samples.json');selected={r['row_id']:r for r in original['records']}
    for p in read(BASE/'results/ASSIGNMENT_MANIFEST.json')['parts']:
        ids=sorted(r for r in selected if p['first_row']<=r<p['first_row']+p['n'])
        if not ids:continue
        tab=pq.read_table(BASE/p['file'])
        for row in tab.take(pa.array([i-p['first_row'] for i in ids])).to_pylist():
            prev=selected[row['row_id']]
            extras={k:prev[k] for k in ['original_title','body_excerpt','url','source_part']}
            extras.update(sampled_topic_id=prev['final_topic_id'],sampled_assignment_status=prev['assignment_status'])
            selected[row['row_id']]=dict(row,**extras)
    original.update(created_utc=now(),records=sorted(selected.values(),key=lambda r:(r['sampled_topic_id'],r['row_id'])),
        scope='Frozen reviewed cohort with refreshed final decisions, including newly deferred or quarantined records. Adaptive diagnostic sample, not a held-out accuracy test.',
        topics=len({r['sampled_topic_id'] for r in selected.values()}))
    dump(BASE/'evidence/final_review_samples.json',original)
    print('REFRESHED_REVIEW_COHORT',len(selected))

if __name__=='__main__':main()
