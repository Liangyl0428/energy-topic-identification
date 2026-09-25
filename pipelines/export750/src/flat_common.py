"""Shared paths and schema for the flat classification export."""
from pathlib import Path
from collections import Counter
import datetime
import hashlib
import json
import os
import sys

FLAT = Path(__file__).resolve().parents[1]
ROOT = FLAT.parents[1]
PREVIOUS = ROOT / 'pipelines/refinement'
CORPUS = ROOT / 'inputs/baseline'
os.environ.setdefault('OMP_NUM_THREADS', '4')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '4')
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                               allow_nan=False, default=str) + '\n')
    temp.replace(path)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 ** 2), b''):
            digest.update(block)
    return digest.hexdigest()


def csv(frame, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding='utf-8-sig')


STATUS = {
    'parent_retained_needs_review': 'retained_needs_review',
    'parent_retained': 'retained_baseline',
    'peripheral_parent_retained': 'peripheral_retained',
    'cross_parent_reclassified': 'reclassified',
    'refined_child': 'reclassified',
    'parent_supported': 'supported_current_label',
    'broader_parent_suggestion_only': 'broader_candidate_pending',
    'cross_parent_margin_pending': 'candidate_margin_pending',
    'abstract_task_pending': 'abstract_task_pending',
    'multiple_tasks_pending': 'multiple_tasks_pending',
    'precision_guard_pending': 'precision_guard_pending',
    'cleaned_pending_reclassification': 'cleaned_pending_reclassification',
    'quality_quarantine': 'quality_quarantine',
    'reclassified_after_cleaning': 'reclassified_after_cleaning',
}
STATUS_CN = {
    'retained_needs_review': '沿用原类别，待复核',
    'retained_baseline': '沿用底稿标签，未重新逐条验收',
    'peripheral_retained': '沿用外围或非研究类别，待复核',
    'reclassified': '依据规则接受类别调整',
    'supported_current_label': '当前类别获规则支持',
    'broader_candidate_pending': '候选过宽，待复核',
    'candidate_margin_pending': '候选语义支持不足，待复核',
    'abstract_task_pending': '任务仅在摘要或正文出现，待复核',
    'multiple_tasks_pending': '多任务冲突，待复核',
    'precision_guard_pending': '自动决定被精度检查撤回，待复核',
    'cleaned_pending_reclassification': '已清理文本，主题待复核',
    'quality_quarantine': '质量隔离',
    'reclassified_after_cleaning': '文本清理后接受类别调整',
}
ORIGIN = {
    'retained_baseline_parent_not_newly_verified': 'retained_baseline_not_newly_verified',
    'automatic_title_rule_and_semantic_support': 'automatic_title_rule_and_semantic_support',
    'quality_quarantine': 'quality_quarantine',
}
ACTION = {
    'unchanged_initial_decision': 'unchanged_initial_decision',
    'guard_reverted': 'guard_reverted',
    'canonical_owner_normalized': 'canonical_label_normalized',
    'editorial_quality_override': 'editorial_quality_override',
}
QUALITY_CN = {
    'title_only': '仅题名可用', 'usable_text': '正文可用',
    'cleaned_title_only': '清理后仅题名可用', 'cleaned_text': '清理后正文可用',
    'unusable_original': '原始文本不可用',
    'insufficient_metadata': '题名摘要不足',
    'nonresearch_editorial': '封面、索引、勘误等非研究正文',
    'unresolved_template': '模板干扰未解除',
}
SOURCE_CN = {'paper': '论文', 'patent': '专利', 'policy': '政策'}


def flat_reason(value):
    """Change hierarchy terminology only; retain the actual review finding."""
    return str(value or '').replace('下级子类', '类别').replace('主类', '类别').replace(
        '父类', '类别').replace('子类', '类别')


SCHEMA = pa.schema([
    ('row_id', pa.int64()), ('doc_id', pa.string()), ('source', pa.string()),
    ('date', pa.string()), ('title', pa.string()),
    ('category_index', pa.int16()), ('category_id', pa.string()),
    ('category_name', pa.string()), ('baseline_category_id', pa.string()),
    ('baseline_category_name', pa.string()), ('baseline_review_status', pa.string()),
    ('assignment_status', pa.string()), ('label_origin', pa.string()),
    ('label_changed', pa.bool_()), ('semantic_label_changed', pa.bool_()),
    ('quarantined', pa.bool_()), ('quarantine_code', pa.string()),
    ('quarantine_reason', pa.string()), ('quality_status', pa.string()),
    ('initial_quality_status', pa.string()), ('quality_flags', pa.string()),
    ('text_cleaned', pa.bool_()), ('retracted', pa.bool_()),
    ('needs_review', pa.bool_()), ('review_reason', pa.string()),
    ('review_priority', pa.int64()), ('priority_cleanup', pa.bool_()),
    ('eligible_for_counts', pa.bool_()), ('eligible_for_supported_analysis', pa.bool_()),
    ('rule_id', pa.string()), ('text_evidence_level', pa.int64()),
    ('semantic_support_cosine', pa.float64()),
    ('semantic_support_cluster1000', pa.float64()), ('raw_cluster1000', pa.int64()),
    ('routing_body_characters', pa.int64()), ('clean_text_nearest1000', pa.float64()),
    ('decision_action', pa.string()),
])
