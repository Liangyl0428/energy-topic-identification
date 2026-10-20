"""Present and persist assistant readings of actual source-paper contexts."""
from common import *
import argparse
from review_batches import indices

OUTCOMES = {
    'wrong_topic': '词语或文章虽有能源关联，但所示语境不支持原拟主题的特定义项；不能据此解释为全局非能源。',
    'energy_supported': '所示题名/摘要明确支持该词在能源技术或能源应用中的所拟词义；仍不等于独立准确率或文章主旨判定。',
    'non_energy_sense': '所示语境表明当前实例为非能源词义/应用；不由本例推断该词所有文献都无能源关联。',
    'generic_method': '所示语境支持通用方法或材料词义，但未证明本实例有能源应用；不能作为独立能源触发证据。',
    'background_only': '所示语境仅支持背景、对比或实验设备关联，不足以据此认定论文研究对象。',
    'source_label_unsupported': '所示题名/可用摘要与来源词标签不符或无支持；需保留来源并另记触发限制，不能补造来源标签。',
    'boundary': '所示能源关联可理解，但超出当前具体主题/业务边界；保持不触发或独立边界标记。',
    'inconclusive': '已阅读所示内容，证据不足以可靠判断词义或能源应用；不将其当作支持激活的语义证据。',
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['show', 'expand', 'commit', 'status'])
    ap.add_argument('--size', type=int, default=60)
    ap.add_argument('--body-chars', type=int, default=0)
    ap.add_argument('--ids')
    ap.add_argument('--spec')
    args = ap.parse_args()
    prepared = read(WORK / 'CONTEXT_PREPARED.json')
    assert sha(WORK / 'frozen_context_queue.parquet') == prepared['context_queue_sha256']
    progress = read(WORK / 'CONTEXT_PROGRESS.json')
    if args.action == 'status':
        print(json.dumps(progress, ensure_ascii=False, indent=2)); return
    q = pd.read_parquet(WORK / 'frozen_context_queue.parquet').fillna('')
    if args.action == 'expand':
        chosen = q[q.context_index.isin(indices(args.ids))].copy()
        assert len(chosen) == len(indices(args.ids))
        m = pd.read_parquet(WORK / 'context_metadata.parquet').fillna('')
        chosen = chosen.merge(m[['row_id','body']], on='row_id', validate='many_to_one')
        source = pd.read_parquet(WORK / 'context_source_keywords.parquet')
        out = []
        for r in chosen.to_dict('records'):
            src = source[source.evidence_id == r['evidence_id']]
            body = str(r['body'])
            out.append({'context_index':int(r['context_index']), 'evidence_id':r['evidence_id'],
                        'keyword_code':r['keyword_code'], 'display_name':r['display_name'],
                        'title':r['title'], 'body':body[:args.body_chars] if args.body_chars else body,
                        'body_full_length':len(body),
                        'source_keywords':src[['keyword_code','raw_name','score']].to_dict('records')})
        payload = {'contexts':out, 'body_chars_requested':args.body_chars}
        digest = hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        path = WORK / 'context_expansions' / f'{digest[:16]}.json'
        write(path, payload)
        print('EXPANSION',path.relative_to(WORK),'SHA256',sha(path))
        for r in out:
            print(f"{r['context_index']} {r['display_name']} | {r['title']}")
            print('BODY',r['body'])
            print('SOURCE', ' | '.join(k['raw_name'] for k in r['source_keywords']))
        return
    no = len(progress['batch_manifest']) + 1
    path = WORK / 'context_batches' / f'batch_{no:03d}_input.json'
    if args.action == 'show':
        if not path.exists():
            own = q.iloc[progress['reviewed']:progress['reviewed'] + args.size].copy()
            if args.body_chars:
                m = pd.read_parquet(WORK / 'context_metadata.parquet').fillna('')
                own = own.merge(m[['row_id','body']],on='row_id',validate='many_to_one')
                own['body_full_length'] = own.body.str.len()
                own['body_excerpt'] = own.body.str[:args.body_chars]
                own = own.drop(columns='body')
            source = pd.read_parquet(WORK / 'context_source_keywords.parquet')
            reviewed_codes = q.set_index('evidence_id').keyword_code.to_dict()
            other = source[source.baseline_decision.eq('direct') & source.keyword_code.ne(source.evidence_id.map(reviewed_codes))]
            anchor = other.groupby('evidence_id').raw_name.agg(list).to_dict()
            own['baseline_anchor_words'] = own.evidence_id.map(lambda i: anchor.get(i,[]))
            write(path, {'batch':no, 'queue_sha256':prepared['context_queue_sha256'],
                         'body_chars':args.body_chars, 'contexts':own.to_dict('records')})
        data = read(path)
        print('CONTEXT BATCH',no,'SHA256',sha(path),'CASES',len(data['contexts']),'BODY_CHARS',data['body_chars'])
        for r in data['contexts']:
            print(f"{r['context_index']} {r['display_name']} [{r['decision']}:{r['topic_code']}] | {r['title']}")
            if data['body_chars']:
                print('BODY',r['body_excerpt'])
            print('OTHER_BASELINE_ANCHORS', ' / '.join(r['baseline_anchor_words']) or '(none)')
        return
    assert path.exists() and args.spec
    data, spec = read(path), read(Path(args.spec))
    assert spec['input_sha256'] == sha(path) and spec['read_all_displayed_contexts'] is True
    assert spec['summary'].strip() and spec['default'] in OUTCOMES
    expanded = set()
    for f in spec.get('expansion_files',[]):
        assert sha(WORK / f['path']) == f['sha256']
        expanded.update(r['context_index'] for r in read(WORK / f['path'])['contexts'])
    decisions = {}
    for r in data['contexts']:
        decisions[r['context_index']] = {**r, 'outcome':spec['default'],
            'review_reason':OUTCOMES[spec['default']], 'reviewer':'assistant',
            'review_scope':'title_and_displayed_body_excerpt' if data['body_chars'] else 'title_and_baseline_anchor_labels',
            'expanded_body_read':r['context_index'] in expanded,
            'batch':no, 'input_sha256':sha(path), 'expert_approved':False}
    seen = set()
    for g in spec.get('groups',[]):
        assert g['outcome'] in OUTCOMES
        for i in indices(g['indices']):
            assert i in decisions and i not in seen, i
            seen.add(i)
            decisions[i].update(outcome=g['outcome'],review_reason=g.get('reason',OUTCOMES[g['outcome']]))
    target = WORK / 'context_batches' / f'batch_{no:03d}_review.json'
    assert not target.exists()
    write(target, {'batch':no,'input_sha256':sha(path),'reading_statement':spec['summary'],
                   'expansion_files':spec.get('expansion_files',[]), 'automatic_semantic_assignment':False,
                   'decisions':list(decisions.values())})
    progress['reviewed'] += len(decisions)
    progress['batch_manifest'].append({'batch':no,'cases':len(decisions),
        'input_sha256':sha(path),'review_file':str(target.relative_to(WORK)),'review_sha256':sha(target)})
    write(WORK / 'CONTEXT_PROGRESS.json',progress)
    frames = [pd.DataFrame(read(WORK / b['review_file'])['decisions']) for b in progress['batch_manifest']]
    pd.concat(frames,ignore_index=True).to_parquet(WORK / 'context_review_ledger.parquet',index=False)
    print(json.dumps({'batch_committed':no,'contexts_reviewed':progress['reviewed'],
                     'remaining':progress['total_contexts']-progress['reviewed'],
                     'outcomes':pd.DataFrame(decisions.values()).outcome.value_counts().to_dict()},ensure_ascii=False))


if __name__ == '__main__':
    main()
