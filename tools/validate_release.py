"""Validate current full-corpus artifacts and Git-visible release checksums."""
import json
from check_current_release import ROOT, validate, verify_hashes

def main():
    report=validate(require_tracked=False)
    verify_hashes(ROOT,json.loads((ROOT/'provenance/SHA256SUMS.json').read_text()))
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
