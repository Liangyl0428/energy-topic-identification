"""K=500 data-driven topics, multiple memberships and reversible scope review.

Run from any directory with the project's .venv-hotspots Python. Immutable
inputs are the frozen corpus, TF-IDF matrices and earlier controlled experiment.
This release has its own IDs; it never overwrites F500 or RBK200 assignments.
"""
import os
os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '4')
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import sys
import time
from datetime import datetime, timezone

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from runtime_config import load_runtime
RUNTIME = load_runtime()
ROOT = RUNTIME.path('data_root')
PRIOR = ROOT / 'work/nmf_remove_broad_k_multilabel_20261019'
OUT = ROOT / 'work/nmf500_multilabel_scope_20261019'
FROZEN = RUNTIME.path('classification_run')
CORPUS = RUNTIME.path('corpus_dir')
CONTROLLED = Path(__file__).resolve().parent / 'controlled'
sys.path.insert(0, str(CONTROLLED))
spec = importlib.util.spec_from_file_location('controlled_nmf', CONTROLLED / 'experiment.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.OUT = OUT
base.ROOT = ROOT
base.RUN = FROZEN
base.CORPUS = CORPUS
base.OLD = ROOT / "work/nmf_keyword_control_20261019"
base.THRESHOLDS = [.05, .10, .15]

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.decomposition._nmf import _initialize_nmf
from threadpoolctl import threadpool_limits
from fast_nmf import GpuMiniBatchNMF

K, SEED, EPOCHS, BATCH = 500, 17, 5, 4096
write, sha, progress = base.write, base.sha, base.progress


def prepare():
    if (OUT / 'PROTOCOL.json').exists():
        return
    shutil.copy2(PRIOR / 'broad_mask.npy', OUT / 'broad_mask.npy')
    shutil.copy2(PRIOR / 'removed_keywords.csv', OUT / 'removed_keywords.csv')
    from zipfile import ZipFile
    from xml.etree import ElementTree as E
    tender = ROOT / 'docs/Dian-Wang-Qing-Bao-Mian-Ban-Zhao-Biao-Shu-_v1.docx'
    with ZipFile(tender) as z:
        document = E.fromstring(z.read('word/document.xml'))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paragraphs = [{'paragraph': i, 'text': ''.join(t.text or '' for t in p.findall('.//w:t', ns))}
                  for i, p in enumerate(document.findall('.//w:p', ns))]
    write(OUT / 'tender_paragraphs.json', paragraphs)
    write(OUT / 'PROTOCOL.json', {
        'created_at': base.stamp(), 'k': K, 'seed': SEED, 'epochs': EPOCHS,
        'selection': 'User-authorized engineering compromise after the five-K content audit; not a proven optimum.',
        'input_corpus': str(CORPUS), 'input_matrices': str(FROZEN / 'matrices'),
        'broad_terms': base.BROAD, 'broad_mask_sha256': sha(OUT / 'broad_mask.npy'),
        'humanities_note': 'Humanities remains in the learned model and is handled by content/scope review, not silently removed.',
        'paper_contribution': 'p_ij=W_ij*L2(H_j)/sum_k(W_ik*L2(H_k))',
        'thresholds': [.05, .10, .15], 'default_threshold': .10,
        'membership': 'Every contribution >= threshold; no top-N cap or forced primary fallback.',
        'scope': 'Post-model keep_core / keep_supporting / review / exclude; never renormalize after exclusion.',
        'scope_authority': 'Assistant review of tender and sampled records, not human expert approval.',
        'scope_review': 'Record topic-level rationale and actual supporting documents. Uncertain topics remain review.',
        'tender_sha256': sha(tender), 'tender_scope_paragraphs': [5, 296, 312, 326, 328, 341, 372],
        'source_hashes': {str(p.relative_to(REPO)): sha(p) for p in [Path(__file__), CONTROLLED/'experiment.py', CONTROLLED/'fast_nmf.py']},
        'prior_models_and_raw_data_modified': False,
        'cross_source': 'Patents/policies lack the same OpenAlex keyword observations. Their transfer scores will be separately labeled and evaluated; they are not direct NMF W or probabilities.'})


def train():
    folder = OUT / 'full_model'
    folder.mkdir(exist_ok=True)
    if (folder / 'TRAINING_COMPLETE.json').exists():
        return
    mask = np.load(OUT / 'broad_mask.npy')
    paths = sorted((FROZEN / 'matrices').glob('part-*.npz'))
    model = GpuMiniBatchNMF(n_components=K, init='custom', random_state=SEED,
        batch_size=BATCH, max_iter=1, max_no_improvement=None, tol=1e-4,
        forget_factor=1., fresh_restarts=False, transform_max_iter=200)
    checkpoint = folder / 'checkpoint.joblib'
    start_epoch, visits, history = 0, 0, []
    if checkpoint.exists():
        state = joblib.load(checkpoint)
        model, start_epoch, visits, history = (state[x] for x in ['model', 'epoch', 'visits', 'history'])
    started = time.monotonic()
    for epoch in range(start_epoch, EPOCHS):
        order = np.random.default_rng(1700 + epoch).permutation(len(paths))
        for j, i in enumerate(order):
            x = base.clean(sparse.load_npz(paths[i]), mask)
            ix = np.flatnonzero(base.nonzero(x))
            np.random.default_rng(170000 + epoch * 1000 + int(i)).shuffle(ix)
            for lo in range(0, len(ix), BATCH):
                batch = x[ix[lo:lo+BATCH]]
                if visits == 0:
                    w0, h0 = _initialize_nmf(batch, n_components=K, init='random', random_state=SEED)
                    h0[:, mask] = 0
                    model.partial_fit(batch, W=w0, H=h0)
                else:
                    model.partial_fit(batch)
                visits += batch.shape[0]
            if j % 30 == 0:
                progress('k500_full_training', epoch=epoch+1, part=j+1, parts=len(paths),
                         visits=visits, elapsed_seconds=round(time.monotonic()-started, 1))
        h = model.components_
        z = base.clean(sparse.load_npz(paths[0]), mask)
        z = z[np.flatnonzero(base.nonzero(z))[:2048]]
        w = model.transform(z)
        sq = float(z.multiply(z).sum())
        err = sq - 2*float(np.sum(w*(z@h.T))) + float(np.sum((w@(h@h.T))*w))
        history.append({'epoch': epoch+1, 'relative_diagnostic_error': float(np.sqrt(max(0, err)/sq)), 'visits': visits})
        joblib.dump({'epoch': epoch+1, 'visits': visits, 'model': model, 'history': history}, checkpoint)
        progress('k500_epoch_complete', **history[-1])
    expected = base.read(PRIOR/'PREPARED.json')['full_corpus_totals']['remaining_nonzero']*EPOCHS
    assert visits == expected and (model.components_[:, mask] == 0).all()
    joblib.dump(model, folder/'model.joblib', compress=1)
    np.save(folder/'components.npy', model.components_)
    write(folder/'TRAINING_COMPLETE.json', {'k': K, 'seed': SEED, 'epochs': EPOCHS,
        'visits': visits, 'history': history, 'training_population': expected//EPOCHS,
        'model_sha256': sha(folder/'model.joblib'), 'completed_at': base.stamp(),
        'note': 'Five fixed epochs preserve the prior experiment schedule; this does not establish convergence.'})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['train', 'papers', 'train-papers'])
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with threadpool_limits(limits=4):
        prepare()
        if args.stage in ['train', 'train-papers']:
            train()
        if args.stage in ['papers', 'train-papers']:
            base.export_full()


if __name__ == '__main__':
    main()
