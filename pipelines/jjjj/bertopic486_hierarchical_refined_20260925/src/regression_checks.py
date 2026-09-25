"""Meaningful negative controls drawn from actual pilot errors, plus template recovery."""
from classify import Refiner
from text_quality import process
from refine_common import *
from decision_guards import guard

def main():
    engine=Refiner();p=read(OLD/'data/INPUT_MANIFEST.json')['parts'][0]
    rows=pq.read_table(OLD/p['file']).to_pylist();v=np.load(OLD/'models/embeddings/part-00000.npy').astype(np.float32)
    checks=[]
    forbidden={4304:'M007.coating',5982:'M166.multijunction',5844:'M130.manufacturing',17015:'M290.fusion'}
    for rid,tid in forbidden.items():
        r=rows[rid];q=process(r['title'],r['body'],r['usable']);out=engine.one(r,q,v[rid])
        assert out['final_topic_id']!=tid,(rid,out)
        checks.append(dict(row_id=rid,forbidden_topic=tid,actual_topic=out['final_topic_id'],status=out['assignment_status']))
    r=rows[12699];q=process(r['title'],r['body'],r['usable']);out=engine.one(r,q,v[12699])
    assert out['needs_review'],out
    checks.append(dict(row_id=12699,requirement='multi-purpose hydrogen production and pollutant oxidation must not be forced into a single child',actual_status=out['assignment_status']))
    q=process('锂电池','',True);assert q['quality']!='insufficient_metadata'
    q=process('10.1016/example123','',True);assert q['quality']=='insufficient_metadata'
    q=process('ChemInform Abstract: Electrochemical hydrogen evolution','ChemInform is a weekly Abstracting Service, delivering concise information at a glance that was extracted from about 100 leading journals. To access a ChemInform Abstract of an article which was published elsewhere, please select a “Full Text” option. The original article is trackable via the “References” option.',True)
    assert not q['body'] and q['title']=='Electrochemical hydrogen evolution' and q['text_changed']
    assert guard(dict(assignment_status='refined_child',rule_id='M389.shipping',title='Relationship between energy and fuel prices'))
    dump(BASE/'review/REGRESSION_CHECKS.json',dict(created_utc=now(),passed=True,actual_document_negative_controls=checks,
        other_checks=['short meaningful Chinese titles retained','DOI-only empty records quarantined','ChemInform template removed without removing scientific title','word-internal shipping false positive vetoed']))
    print('REGRESSION_CHECKS_PASSED',len(checks)+4)

if __name__=='__main__':main()
