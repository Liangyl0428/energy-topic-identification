# OpenAlex keywords: TF-IDF + NMF

This pipeline is the reproducible candidate for a roughly 500-topic paper taxonomy.
It does not replace the released 750-topic result until the candidate metrics and
topic catalogue have been reviewed.

## Current v0.2.1 delivery

The frozen 500-component H is retained, not refitted or reselected. All splits now
use the same fixed-H transform and compare `W[:, j] * ||H[j]||₂`, not raw W.
These contributions are scale-invariant reconstruction weights, not probabilities.
The corrected delivery has 499 active topics; N0069 is explicitly inactive.
30,359 of 142,000 labels differ from the v0.2.0 production delivery.

Current validation silhouette is -0.07970 and keyword/BGE top-1 agreement is 35.67%.
These still indicate substantial overlap, not proven classification accuracy.
Use [current results](../assets/nmf500/REPORT.md) and the
[strict audit](V0.2.1_AUDIT.md). The grid, selection rule and stability figures
below are historical v0.2.0 experiments; they were not rerun for v0.2.1.

## Separation of roles

1. Topic discovery uses only score-weighted OpenAlex keyword phrases attached to
   papers. Keyword phrases and OpenAlex keyword IDs remain intact; titles,
   abstracts, patents, and policies are not features in the NMF fit.
2. The frozen 2010--2023 paper sample fits TF-IDF and NMF. The 2024 sample selects
   K. The 2025--2026Q2 replay sample does not select K.
3. BGE-M3 paper embeddings measure the geometry of keyword-derived labels and form
   one normalized centroid per active topic.
4. Patent and policy BGE-M3 embeddings receive top-3 topics by cosine similarity to
   those paper centroids. They never enter topic discovery.

## Candidate selection

The grid is K = 400, 450, 500, 550, 600. K=400 and K=600 diagnose boundary
behaviour; selection is constrained to 450--550 to respect the requested resolution.
The selected candidate minimizes the mean rank of six metrics, with a small
distance-to-500 penalty. Scores within 0.05 of the best score are treated as a
practical tie; the candidate closest to the requested K=500 wins that tie:

- sampled cosine silhouette on 6,000 validation-paper embeddings (higher);
- centroid/simplified silhouette on all covered validation papers (higher);
- Davies--Bouldin on validation-paper embeddings (lower);
- nearest topic-centre cosine among training centres (lower);
- empty component fraction (lower);
- ARI between keyword-NMF labels and embedding-nearest-centre labels (higher).

The report also includes active topics, topic-size quantiles and Gini, effective
topic count, validation coverage, NMF reconstruction error, negative simplified
silhouette fraction, and keyword/embedding top-1 agreement.

These geometry metrics are not expert-label accuracy. They are suitable for model
comparison, not a substitute for reviewing the resulting keyword catalogue.

## Confidence and stability

Production topic embeddings average all labelled paper embeddings after K is fixed.
Transfer records include top-1/top-2/top-3 cosine scores and the top-1 minus top-2
margin. `similarity_filter_passed` compares both values to tenth percentiles
measured on 2024 validation papers against training-only topic centres.
Every patent/policy link remains `needs_review=true`, including links that pass
this numerical filter. Paper-domain quantiles do not calibrate cross-domain accuracy.

The selected K is refitted with seed 29 and with a fixed 80% training subsample.
Hungarian component matching reports keyword-component cosine and validation ARI.
MiniBatchNMF reuses the batch coefficients between updates (`fresh_restarts=False`)
and allows at most 30 passes over the training matrix; the observed pass count is
recorded for every candidate.

## Run

From the source-project root, using an environment containing numpy, pandas, scipy,
scikit-learn, pyarrow, and joblib:

```bash
.venv-hotspots/bin/python \
  energy-topic-identification/pipelines/keyword_nmf/src/run_pipeline.py all \
  --output energy-topic-identification/work/nmf-new-grid
```

This runs a new grid; it is not the frozen-H v0.2.1 replay. Use a fresh output
directory: old cached grids have a different inference method and are rejected.
The frozen model is stored locally under `pipelines/keyword_nmf/results/`.
To replay the current release, first run the sibling hotspot build/review/validate
pipeline, then `audit_current.py` and `export_snapshot.py` in this pipeline.
Large local inputs are required and are not included in Git.

## Historical v0.2.0 grid (2026-09-26)

All five models used the same 112,000-paper training split, seed 17, batch size
4,096, and at most 30 passes. Geometry was evaluated on the independent
12,000-paper 2024 validation split.

| K | active | sampled silhouette | simplified silhouette | DB | nearest-centre cosine | keyword/embedding ARI | relative reconstruction error |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 400 | 400 | -0.071073 | -0.050431 | 5.104130 | 0.956157 | 0.162118 | 0.757811 |
| 450 | 450 | -0.076327 | -0.054191 | 4.941442 | 0.955340 | 0.151015 | 0.744202 |
| **500** | **500** | **-0.086628** | **-0.057064** | **4.835184** | **0.955289** | **0.150399** | **0.728737** |
| 550 | 550 | -0.096538 | -0.058961 | 4.716086 | 0.954754 | 0.144317 | 0.718402 |
| 600 | 600 | -0.095765 | -0.061371 | 4.585985 | 0.955029 | 0.140612 | 0.705892 |

K=450 and K=500 had selection scores 1.9833 and 2.0000, respectively, so they
fell inside the documented 0.05 practical-tie band. K=500 was selected because it
matches the requested resolution. The negative silhouettes and low
keyword/embedding ARI show substantial overlap in the BGE-M3 geometry; the result
should be treated as an exploratory fine-grained taxonomy, not as evidence of naturally
separated semantic clusters.

The selected model assigned 141,895 of 142,000 papers; 105 papers had no usable
in-vocabulary keyword representation. Both stability fits matched all 500
components. The seed-29 fit achieved mean matched-component cosine 0.9009 and
validation ARI 0.7342; the 80% training subsample achieved 0.8502 and 0.6030.

Transfer classification covered 17,918 patents and 5,865 policies. Mean top-1
cosine was 0.6994 for patents and 0.6355 for policies. The validation-calibrated
review rule marked 37.6% of patents and 86.3% of policies, or 49.6% overall, as
low-confidence. The policy rate is direct evidence of domain shift and warrants
manual review or a later policy-specific calibration/model.
