"""Assemble sibling repositories into a fresh, offline platform delivery."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess

NAMES = ('energy-topic-identification', 'energy-topic-hotspots', 'energy-technology-trl-crl')
REPO = Path(__file__).resolve().parents[1]


def visible_files(repo):
    result = subprocess.check_output(
        ['git', '-C', str(repo), 'ls-files', '-z', '--cached', '--others', '--exclude-standard']
    ).decode().split('\0')
    return sorted({name for name in result if name and (repo / name).is_file()})


def assemble(repos_dir, output):
    repos_dir, output = Path(repos_dir).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite existing output: {output}')
    inventories = {}
    for name in NAMES:
        repo = repos_dir / name
        if not (repo / 'README.md').is_file():
            raise FileNotFoundError(f'Missing sibling repository: {repo}')
        if output.is_relative_to(repo):
            raise ValueError('Output must be outside the source repositories')
        inventories[name] = visible_files(repo)
    source = repos_dir / NAMES[0]
    output.mkdir(parents=True)
    counts = {}
    for name, paths in inventories.items():
        repo = repos_dir / name
        counts[name] = 0
        for relative in paths:
            if relative.startswith('platform/'):
                if name != NAMES[0]:
                    continue
                target = output / Path(relative).relative_to('platform')
            else:
                target = output / name / relative
            item = repo / relative
            if item.is_symlink():
                raise ValueError(f'Symlink is not a portable delivery: {item}')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            counts[name] += 1
    record = {
        'copied_files': counts,
        'source_commits': {name: subprocess.check_output(
            ['git', '-C', str(repos_dir / name), 'rev-parse', 'HEAD'], text=True
        ).strip() for name in NAMES},
        'source_worktree_clean': {name: not subprocess.check_output(
            ['git', '-C', str(repos_dir / name), 'status', '--porcelain'], text=True
        ).strip() for name in NAMES},
        'contains_full_document_exports': False,
        'external_files_manifest': 'EXTERNAL_FILES.json',
        'note': 'No calculation or deployment was performed. Module copies omit Git metadata.',
    }
    (output / 'ASSEMBLY.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repos-dir', type=Path, default=REPO.parent)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(assemble(args.repos_dir, args.output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
