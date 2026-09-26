# OpenAlex keyword TF-IDF + NMF report

## Selection

- Selected nominal K: 500
- Active paper topics: 500
- Candidate window: 400, 450, 500, 550, 600; selection was restricted to 450--550.
- Sampled validation cosine silhouette: -0.086628
- Simplified validation silhouette: -0.057064
- Davies--Bouldin: 4.835184
- Mean nearest-center cosine: 0.955289
- Keyword-label/embedding-nearest-center ARI: 0.150399

NMF was fitted only on score-weighted OpenAlex keyword TF-IDF from training papers. Patent and policy text never entered NMF fitting or candidate selection.

### Candidate comparison

|   requested_k |   active_topics |   sampled_cosine_silhouette |   simplified_silhouette_mean |   davies_bouldin |   nearest_center_cosine_mean |   keyword_embedding_ari |   nmf_relative_reconstruction_error | selected   |
|--------------:|----------------:|----------------------------:|-----------------------------:|-----------------:|-----------------------------:|------------------------:|------------------------------------:|:-----------|
|           400 |             400 |                  -0.0710729 |                   -0.0504311 |          5.10413 |                     0.956157 |                0.162118 |                            0.757811 | False      |
|           450 |             450 |                  -0.0763272 |                   -0.0541906 |          4.94144 |                     0.95534  |                0.151015 |                            0.744202 | False      |
|           500 |             500 |                  -0.0866278 |                   -0.057064  |          4.83518 |                     0.955289 |                0.150399 |                            0.728737 | True       |
|           550 |             550 |                  -0.0965381 |                   -0.0589615 |          4.71609 |                     0.954754 |                0.144317 |                            0.718402 | False      |
|           600 |             600 |                  -0.0957645 |                   -0.061371  |          4.58599 |                     0.955029 |                0.140612 |                            0.705892 | False      |

## Transfer confidence

- Validation cosine p10 threshold: 0.677844
- Validation top1--top2 margin p10 threshold: 0.001710
- A patent/policy record is marked `needs_review` when either threshold is missed.

| source   |   documents |   top1_cosine_mean |   top1_cosine_median |   margin_mean |   needs_review_fraction |
|:---------|------------:|-------------------:|---------------------:|--------------:|------------------------:|
| patent   |       17918 |           0.699383 |             0.700068 |    0.0107117  |                0.375544 |
| policy   |        5865 |           0.635549 |             0.638623 |    0.00956314 |                0.863086 |

## Stability

| variant     |   seed |   fit_documents |   fit_seconds |   matched_topics |   component_cosine_mean |   component_cosine_p10 |   validation_ari | convergence_warnings                                                         |
|:------------|-------:|----------------:|--------------:|-----------------:|------------------------:|-----------------------:|-----------------:|:-----------------------------------------------------------------------------|
| seed29      |     29 |          111943 |       320.44  |              500 |                0.900892 |               0.64329  |         0.734204 | nan                                                                          |
| subsample80 |     17 |           89638 |       484.852 |              500 |                0.850202 |               0.203498 |         0.603035 | Maximum number of iterations 30 reached. Increase it to improve convergence. |

## Interpretation limits

Silhouette and Davies--Bouldin quantify geometry in the BGE-M3 embedding space; they are not expert-label accuracy. OpenAlex keyword assignment and BGE-M3 each introduce model/platform preferences. Low-confidence transfer records should not be treated as reliably classified without review.
