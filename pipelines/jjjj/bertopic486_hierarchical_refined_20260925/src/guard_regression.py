"""Regression checks from independently read diagnostic cases; not an accuracy score."""
from refine_common import *
from decision_guards import guard

def main():
    sample=read(BASE/'evidence/partial_review_samples.json')['records']
    byid={r['row_id']:r for r in sample}
    old=pd.read_csv(OLD/'results/merged_topics.csv').set_index('merged_topic_id').status.to_dict()
    negative=[2668016,2611587,2692,2629002,2687298,2835694,86817,1561225,3933923,4143372,
              2616484,3912639,4171968,4070820,1645644,4091146,4034135,42197,263164,427817,
              2773768,1527037,1500831,4101112,213036,2943209,2794166,4105740]
    checks=[]
    for rid in negative:
        r=dict(byid[rid],old_parent_status=old.get(byid[rid]['old_parent_id'],''))
        reason=guard(r);assert reason,(rid,r)
        checks.append(dict(row_id=rid,expected='abstain',reason=reason))
    for rid in [4006773,2766427,4054240,3964824,4091607,48851,2674294,2632077,3973951,4106204,2733635,334519]:
        r=byid[rid];assert guard(r) is None,(rid,guard(r))
        checks.append(dict(row_id=rid,expected='not_vetoed_by_precision_guards'))
    dump(BASE/'review/GUARD_REGRESSION_CHECKS.json',dict(created_utc=now(),passed=True,checks=checks,
        scope='Real-document negative/positive regression controls; no inference of general accuracy.'))
    print('GUARD_REGRESSION_PASSED',len(checks))

if __name__=='__main__':main()
