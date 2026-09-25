"""Print and log exactly the excerpts inspected for possible whole-cluster merges."""
from common import *
import argparse
import pandas as pd

p = argparse.ArgumentParser()
p.add_argument('clusters', type=int, nargs='+')
p.add_argument('--chars', type=int, default=700)
p.add_argument('--roles', default='center:1,random:1,random:2,boundary:1')
args = p.parse_args()
e = pd.read_parquet(BASE / 'evidence/review_documents.parquet')
topics = pd.read_csv(BASE / 'results/raw_500_topics.csv').set_index('cluster')
names = {int(x[0]): x[1] for x in [l.split('|') for l in (BASE / 'results/review_names.txt').read_text().splitlines()]}
weights = json.loads((BASE / 'models/CLUSTER_AUDIT.json').read_text())['per_document_training_weights']
logpath = BASE / 'evidence/excerpts_inspected.json'
log = json.loads(logpath.read_text()) if logpath.exists() else []
for c in args.clusters:
    t = topics.loc[c]
    counts = dict(paper=int(t.papers), patent=int(t.patents_2026), policy=int(t.policies))
    dominant = max(counts, key=lambda s: counts[s] * weights[s])
    sources = [dominant] + [s for s in counts if s != dominant and counts[s] >= 20 and counts[s] * weights[s] >= .2 * counts[dominant] * weights[dominant]]
    print(f'\nB{c:03d} {names[c]} {counts}')
    print(t.keywords)
    seen = set()
    for source in sources:
        roles = args.roles.split(',') if source == dominant else ['center:1', 'random:1']
        subset = e[e.cluster.eq(c) & e.source.eq(source)]
        for role in roles:
            rows = subset[subset.selection_roles.str.split('|', regex=False).map(lambda rs: role in rs)]
            for r in rows.itertuples():
                if r.row_id in seen:
                    continue
                seen.add(r.row_id)
                body = str(r.body or '')
                text = body[:args.chars].replace('\n', ' ')
                print(f' #{r.row_id} {source} {r.selection_roles} ->B{r.secondary_candidate:03d}: {r.title}')
                print('  ' + (text or '[无正文，仅题名]'))
                log.append(dict(cluster=c, row_id=int(r.row_id), source=source, selection_roles=r.selection_roles, body_chars_shown=min(len(body), args.chars), body_chars_total=len(body), excerpt=text, title=r.title, inspected_utc=now()))
dump(logpath, log)
