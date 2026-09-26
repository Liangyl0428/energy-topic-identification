"""Refresh checksums for Git-visible release files, excluding this manifest itself."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')
    manifest={}
    for relative in sorted(set(paths)):
        if not relative or relative=='provenance/SHA256SUMS.json':
            continue
        path=ROOT/relative
        if not path.is_file() or path.is_symlink() or path.stat().st_size>=10*1024**2:
            raise ValueError('Unexpected release file: '+relative)
        manifest[relative]=hashlib.sha256(path.read_bytes()).hexdigest()
    (ROOT/'provenance/SHA256SUMS.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print('Manifest:',len(manifest),'files')


if __name__=='__main__':
    main()
