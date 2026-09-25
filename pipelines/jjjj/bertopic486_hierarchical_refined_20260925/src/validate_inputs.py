from refine_common import *

def main():
    checks=[];failures=[]
    for s in read(BASE/'INPUT_SNAPSHOT.json')['inputs']:
        d=Path(s['directory']);m=d/'DELIVERY_MANIFEST.json'
        ok=sha(m)==s['delivery_manifest_sha256']
        if not ok:failures.append(str(m))
        files=read(m);items=files.get('artifacts',files.get('files',[]))
        for x in items:
            f=d/x['path'];passed=f.exists() and sha(f)==x['sha256']
            checks.append(dict(path=str(f),passed=passed))
            if not passed:failures.append(str(f))
        print(d.name,'delivery entries checked',len(items),flush=True)
    parts=read(OLD/'data/INPUT_MANIFEST.json')['parts']
    for i,p in enumerate(parts):
        f=OLD/p['file'];ok=sha(f)==p['sha256']
        checks.append(dict(path=str(f),passed=ok))
        if not ok:failures.append(str(f))
        if i%25==0:print('corpus_checked',i+1,len(parts),flush=True)
    dump(BASE/'review/INPUT_INTEGRITY.json',dict(created_utc=now(),passed=not failures,checked_files=len(checks),
        snapshot_manifests_unchanged=True if not failures else None,failures=failures,checks=checks,
        scope='Three prior delivery manifests and every referenced artifact; all 259 original corpus parts against their stored hashes. Original embeddings are read-only references, not copied.'))
    assert not failures,failures
    print('INPUT_INTEGRITY_PASSED',len(checks),flush=True)

if __name__=='__main__':main()
