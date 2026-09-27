"""Optional same-weight BGE graph fusion; acceptance requires output comparison."""
from common import *
import sys
import time
sys.path[:0]=[str(ROOT/'aaaa/bge_m3/_runtime'),str(ROOT/'aaaa/bge_m3/_core')]
import numpy as np
import onnxruntime as ort
from onnxruntime.transformers.optimizer import optimize_model
from tokenizers import Tokenizer
import pyarrow.parquet as pq


def main():
    target=RUN/'optimized_encoder';target.mkdir(exist_ok=True)
    original=ROOT/'aaaa/bge_m3/models/bge-m3/onnx/model_fp16.onnx'
    path=target/'model.onnx'
    if not path.exists():
        optimized=optimize_model(str(original),model_type='bert',num_heads=16,hidden_size=1024,opt_level=0)
        stats=optimized.get_fused_operator_statistics()
        optimized.save_model_to_file(str(path),use_external_data_format=True)
        dump(target/'FUSION.json',stats)
        del optimized
    tok=Tokenizer.from_file(str(original.parent.parent/'tokenizer.json'))
    tok.enable_truncation(max_length=2048);tok.enable_padding(pad_id=1,pad_token='<pad>')
    sources=[parts()[i] for i in [0,60,120,241,248,258]]
    texts=[]
    for p in sources:
        d=pq.read_table(p,columns=['title','body']).slice(0,64).to_pandas()
        texts.extend((d.title.fillna('')+'\n'+d.body.fillna('')).tolist())
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1;options.log_severity_level=3
    records=[];vectors=[]
    for model in [original,path]:
        s=ort.InferenceSession(str(model),sess_options=options,providers=['CUDAExecutionProvider','CPUExecutionProvider'])
        outputs=[];elapsed=0
        for start in range(0,len(texts),4):
            e=tok.encode_batch(texts[start:start+4])
            inputs={'input_ids':np.array([x.ids for x in e],np.int64),'attention_mask':np.array([x.attention_mask for x in e],np.int64)}
            began=time.time();v=s.run(['sentence_embedding'],inputs)[0];elapsed+=time.time()-began
            outputs.extend(v/np.linalg.norm(v,axis=1,keepdims=True))
        vectors.append(np.asarray(outputs));records.append({'model':str(model),'seconds':elapsed});del s
    cos=np.sum(vectors[0]*vectors[1],axis=1)
    accepted=bool(np.isfinite(vectors[1]).all() and cos.min()>.999 and cos.mean()>.9999)
    dump(target/'VALIDATION.json',{'accepted':accepted,'documents':len(texts),'minimum_cosine':float(cos.min()),'mean_cosine':float(cos.mean()),
        'max_abs_difference':float(np.max(np.abs(vectors[0]-vectors[1]))),'timing':records,
        'note':'same weights, same FP16, graph fusion only; timings are diagnostics while other GPU jobs may run'})
    print((target/'VALIDATION.json').read_text(),flush=True)


if __name__=='__main__':main()
