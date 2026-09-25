"""Finish output checks and exports once deterministic labeling has completed."""
from refine_common import *
import subprocess,time

def run(script):
    p=subprocess.run([sys.executable,str(BASE/'src'/script)],check=True)

def main():
    for _ in range(120):
        if read(BASE/'PROGRESS.json')['stage']=='finalization_complete':break
        time.sleep(5)
    else:raise RuntimeError('Finalization did not complete; inspect its log')
    handles=[];processes=[]
    for name in ['validate_output.py','refresh_review_cohort.py']:
        handle=(BASE/'logs'/f'seal_{Path(name).stem}.log').open('w');handles.append(handle)
        processes.append(subprocess.Popen([sys.executable,str(BASE/'src'/name)],stdout=handle,stderr=subprocess.STDOUT))
    for p in processes:assert p.wait()==0,'Output validation or cohort refresh failed; inspect logs'
    for h in handles:h.close()
    run('semantic_review_record.py')
    run('build_delivery.py')
    manifest=read(BASE/'DELIVERY_MANIFEST.json')
    assert len(manifest['files'])>1000
    assert all((BASE/x['path']).stat().st_size==x['bytes'] for x in manifest['files'])
    assert read(BASE/'VALIDATION.json')['passed'] and read(BASE/'review/WORKBOOK_VALIDATION.json')['passed']
    print('SEALED_AND_CHECKED',len(manifest['files']),'files',flush=True)

if __name__=='__main__':main()
