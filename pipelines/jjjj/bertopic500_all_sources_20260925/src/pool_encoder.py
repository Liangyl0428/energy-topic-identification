from common import *
import onnx, numpy as np
from onnx import helper, numpy_helper, TensorProto

M = BASE / 'models/multilingual_minilm/onnx'
model = onnx.load(str(M / 'model_O4.onnx'))
opset = next(x.version for x in model.opset_import if not x.domain)
assert 13 <= opset < 18, opset
hidden = model.graph.output[0].name
model.graph.initializer.extend([
    numpy_helper.from_array(np.array([1], dtype=np.int64), 'pool_axis'),
    numpy_helper.from_array(np.array([2], dtype=np.int64), 'pool_unsqueeze_axis'),
    numpy_helper.from_array(np.array(1e-9, dtype=np.float32), 'pool_eps')
])
model.graph.node.extend([
    helper.make_node('Cast', ['attention_mask'], ['pool_mask_f'], to=TensorProto.FLOAT),
    helper.make_node('Unsqueeze', ['pool_mask_f', 'pool_unsqueeze_axis'], ['pool_mask']),
    helper.make_node('Mul', [hidden, 'pool_mask'], ['pool_masked']),
    helper.make_node('ReduceSum', ['pool_masked', 'pool_axis'], ['pool_sum'], keepdims=0),
    helper.make_node('ReduceSum', ['pool_mask_f', 'pool_axis'], ['pool_count'], keepdims=1),
    helper.make_node('Clip', ['pool_count', 'pool_eps'], ['pool_count_safe']),
    helper.make_node('Div', ['pool_sum', 'pool_count_safe'], ['pool_mean']),
    helper.make_node('ReduceL2', ['pool_mean'], ['pool_norm'], axes=[1], keepdims=1),
    helper.make_node('Clip', ['pool_norm', 'pool_eps'], ['pool_norm_safe']),
    helper.make_node('Div', ['pool_mean', 'pool_norm_safe'], ['sentence_embedding'])
])
del model.graph.output[:]
model.graph.output.extend([helper.make_tensor_value_info('sentence_embedding', TensorProto.FLOAT, ['batch_size', 384])])
# The official ORT-optimized graph uses LayerNormalization with opset14,
# accepted by ORT but predating its registration in the generic ONNX checker.
# Verify execution and numerical parity in encode.py instead of changing opsets.
out = M / 'model_O4_pooled.onnx'
onnx.save(model, str(out))
dump(BASE / 'models/POOL_CONVERSION.json', {'source_sha256': sha(M / 'model_O4.onnx'), 'output_sha256': sha(out), 'opset': opset, 'change': 'append masked mean pooling and L2 normalization on GPU; encoder architecture/weights unchanged', 'created_utc': now()})
print('POOLED_MODEL_READY', out, flush=True)
