"""Run all three repositories; checkpoints survive interruptions.

The parent runner must stay alive until child stages and full coverage validation
finish. --attach-preparation is for an already running prepare/encode pair.
"""
from common import *
import argparse
import subprocess
import sys
import time


def run(script,python=None,extra=()):
    command=[python or sys.executable,'-u',str(script),*map(str,extra)]
    print('RUN', ' '.join(command),flush=True)
    subprocess.run(command,check=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--attach-preparation',action='store_true');a=p.parse_args()
    RUN.mkdir(parents=True,exist_ok=True)
    here=Path(__file__).resolve().parent
    env=os.environ.copy()
    env['LD_LIBRARY_PATH']=str(ROOT/'aaaa/bge_m3/_runtime/nvidia/cudnn/lib')+':/usr/local/cuda/lib64'+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    workers=[]
    if not a.attach_preparation:
        workers.append(subprocess.Popen([sys.executable,'-u',str(here/'prepare.py')]))
        encoder=['/usr/bin/python3','-u',str(here/'encode.py')]
        validation=RUN/'optimized_encoder/VALIDATION.json'
        if validation.exists():
            checked=json.loads(validation.read_text())
            if checked.get('accepted') and checked.get('documents',0)>=300:
                encoder.append('--optimized')
        workers.append(subprocess.Popen(encoder,env=env))
    def wait_for(marker):
        while not (RUN/marker).exists():
            for proc in workers:
                if proc.poll() not in (None,0):
                    raise RuntimeError(f'Preparation subprocess failed: {proc.pid}')
            dump(RUN/'PIPELINE_PROGRESS.json',{'waiting_for':marker,'updated_unix':time.time(),'status':'running'})
            time.sleep(15)
    wait_for('PREPARE_COMPLETE.json')
    dump(RUN/'PIPELINE_PROGRESS.json',{'stage':'training_and_paper_inference','updated_unix':time.time(),'status':'running'})
    run(here/'train.py')
    wait_for('ENCODING_COMPLETE.json')
    run(here/'finalize.py')
    run(ROOT/'energy-topic-hotspots/pipelines/full_nmf/build.py',extra=['--classification',RUN])
    run(ROOT/'energy-technology-trl-crl/pipelines/full_nmf/build.py',extra=['--classification',RUN])
    run(here/'publish_local.py')
    dump(RUN/'ALL_REPOSITORIES_COMPLETE.json',{'status':'complete','classification':str(RUN),
        'hotspots':str(ROOT/'energy-topic-hotspots/outputs/full_nmf500_20260926'),
        'maturity':str(ROOT/'energy-technology-trl-crl/results/full_nmf500_20260926')})
    dump(RUN/'PIPELINE_PROGRESS.json',{'stage':'all_repositories','updated_unix':time.time(),'status':'complete'})


if __name__=='__main__':main()
