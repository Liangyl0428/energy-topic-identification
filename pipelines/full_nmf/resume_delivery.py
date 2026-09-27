"""Explicitly resume a failed BEFORE-COMMIT delivery after approved additions.

Archives old scheduler records, never stops processes, never repeats tag deletion.
Rejects partial publication: reconciling an interrupted commit/push needs review.
"""
from after_full import *


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--resume-failed-and-push',action='store_true');a=p.parse_args()
    if not a.resume_failed_and_push:p.error('Explicit publication authorization required')
    lock=(JOB/'LOCK').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    old=json.loads((JOB/'CONFIG.json').read_text())
    state=json.loads((JOB/'STATUS.json').read_text())
    if not state['stage'].startswith('failed'):raise ValueError('Only failed scheduler may be resumed')
    if (JOB/'PUSH_RECEIPTS.json').exists() or (RUN/'FULL_DELIVERY_AND_PUSH_COMPLETE.json').exists():
        raise ValueError('Partial or completed publication exists; manual reconciliation required')
    if not (RUN/'ALL_REPOSITORIES_COMPLETE.json').exists():raise ValueError('Base must already be complete')
    for name,r in old['repositories'].items():
        if git(ROOT/name,'rev-parse','HEAD')!=r['head'] or remote_tip(ROOT/name,r['branch'])!=r['remote_tip']:
            raise ValueError('Local or remote history changed since failed precommit delivery')
    # Newly authorized evaluation additions get a NEW freeze; old freeze retained.
    config={'base_pid':old['base_pid'],'created_unix':time.time(),
        'repositories':{n:capture(ROOT/n) for n in NAMES},
        'expected_model_sha256':old['expected_model_sha256'],'reuse_verified_experiments':True,
        'authorized_workflow':'Add retrospective topic evaluation, validate, commit and non-force push all three existing main branches'}
    archive=JOB/('failed_precommit_'+str(time.time_ns()));archive.mkdir()
    for name in ['CONFIG.json','STATUS.json','TAG_STATUS.json']:
        if (JOB/name).exists():shutil.copy2(JOB/name,archive/name)
    dump(JOB/'CONFIG.json',config)
    try:
        with (JOB/'runner.log').open('a',buffering=1) as log:
            os.dup2(log.fileno(),1);os.dup2(log.fileno(),2)
            execute(config)
    except Exception as exc:
        status('failed_no_further_publication',error_type=type(exc).__name__,error=str(exc))
        raise


if __name__=='__main__':main()
