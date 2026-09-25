from refine_common import *
import subprocess,time

def main():
    processes=[];handles=[]
    for a,b in [(0,65),(65,130),(130,195),(195,259)]:
        f=(BASE/'logs'/f'classify_{a}_{b}.log').open('w');handles.append(f)
        processes.append(subprocess.Popen([sys.executable,str(BASE/'src/classify.py'),'--start',str(a),'--stop',str(b)],stdout=f,stderr=subprocess.STDOUT))
    while any(p.poll() is None for p in processes):
        time.sleep(10)
        failed=[p.returncode for p in processes if p.poll() is not None and p.returncode!=0]
        if failed:
            for p in processes:
                if p.poll() is None:p.terminate()
            raise RuntimeError(f'Classification worker failed: {failed}; inspect worker logs')
        complete=len(list((BASE/'logs').glob('part-*.json')))
        progress('all_document_refinement_running',completed_parts=complete,total_parts=259)
    assert all(p.returncode==0 for p in processes)
    for f in handles:f.close()
    progress('all_document_refinement_complete',completed_parts=259,total_parts=259)

if __name__=='__main__':main()
