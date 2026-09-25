"""Check ONNX pooling against an independent masked-mean calculation."""
from pathlib import Path
import importlib
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import onnx
import onnxruntime as ort
from onnx import helper, TensorProto

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipelines/embedding/src'))
import embedding_common
import pool_encoder


class PoolTests(unittest.TestCase):
    def test_padding_is_excluded_and_vectors_are_normalized(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            model_dir = base / 'models/multilingual_minilm/onnx'
            model_dir.mkdir(parents=True)
            # Replace only the expensive encoder with a known tensor output.
            graph = helper.make_graph(
                [helper.make_node('Identity', ['hidden_input'], ['hidden'])],
                'synthetic_encoder',
                [helper.make_tensor_value_info('hidden_input', TensorProto.FLOAT, ['batch', 'tokens', 384]),
                 helper.make_tensor_value_info('attention_mask', TensorProto.INT64, ['batch', 'tokens'])],
                [helper.make_tensor_value_info('hidden', TensorProto.FLOAT, ['batch', 'tokens', 384])],
            )
            model = helper.make_model(graph, opset_imports=[helper.make_opsetid('', 14)])
            model.ir_version = 9
            onnx.save(model, model_dir / 'model_O4.onnx')
            with patch.object(pool_encoder, 'BASE', base):
                pool_encoder.main()
            session = ort.InferenceSession(str(model_dir / 'model_O4_pooled.onnx'),
                                           providers=['CPUExecutionProvider'])
            hidden = np.random.default_rng(8).normal(size=(2, 4, 384)).astype(np.float32)
            mask = np.array([[1, 1, 0, 0], [1, 1, 1, 0]], dtype=np.int64)
            hidden[mask == 0] = 10000  # A masked token must not dominate the output.
            actual = session.run(None, {'hidden_input': hidden, 'attention_mask': mask})[0]
            expected = (hidden * mask[..., None]).sum(axis=1) / mask.sum(axis=1, keepdims=True)
            expected /= np.linalg.norm(expected, axis=1, keepdims=True)
            np.testing.assert_allclose(actual, expected, atol=2e-7)
            np.testing.assert_allclose(np.linalg.norm(actual, axis=1), np.ones(2), atol=2e-7)

    def test_importing_entrypoints_does_not_start_encoding_or_downloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / 'absent'
            with patch.object(embedding_common, 'BASE', base):
                for name in ('download_encoder', 'encode'):
                    module = importlib.import_module(name)
                    self.assertTrue(callable(module.main))
                self.assertFalse(base.exists())


if __name__ == '__main__':
    unittest.main()
