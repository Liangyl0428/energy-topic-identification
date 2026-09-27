"""Resumable full BGE-M3 encoding; run with workspace Python 3.10 runtime."""
from common import *
import sys
import time
import argparse
sys.path[:0] = [str(ROOT/'aaaa/bge_m3/_runtime'), str(ROOT/'aaaa/bge_m3/_core')]
import numpy as np
import pyarrow.parquet as pq
from tokenizers import Tokenizer
import onnxruntime as ort


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--optimized',action='store_true',help='Use validated same-weight ONNX fusion')
    parser.add_argument('--token-budget',type=int,default=16384)
    args=parser.parse_args()
    out = RUN/'embeddings'
    out.mkdir(parents=True, exist_ok=True)
    model = ROOT/'aaaa/bge_m3/models/bge-m3'
    model_path=model/'onnx/model_fp16.onnx'
    execution='original_fp16'
    if args.optimized:
        validation=json.loads((RUN/'optimized_encoder/VALIDATION.json').read_text())
        if not validation['accepted'] or validation['documents']<300:
            raise ValueError('Expanded graph-fusion validation must pass first')
        model_path=RUN/'optimized_encoder/model.onnx'
        execution='same_weight_fp16_graph_fusion'
    tok = Tokenizer.from_file(str(model/'tokenizer.json'))
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.enable_mem_pattern = False
    options.log_severity_level = 3
    session = ort.InferenceSession(str(model_path),sess_options=options,
        providers=[('CUDAExecutionProvider',{'gpu_mem_limit':18000*1024**2,'arena_extend_strategy':'kNextPowerOfTwo'}),'CPUExecutionProvider'])
    if 'CUDAExecutionProvider' not in session.get_providers():
        raise RuntimeError('BGE GPU provider unavailable')
    config = {'encoder':'BAAI/bge-m3','revision':'5617a9f61b028005a4858fdac845db406aefb181','dimension':1024,'precision':'FP16','saved_dtype':'float32',
        'max_tokens':2048,'paper_text':'title + newline + abstract; first 2048 tokens',
        'transfer_text':'title up to192 tokens plus body head/middle/tail within2044-token budget; decoded and encoded with special tokens',
        'pooling':'official CLS sentence_embedding, L2 normalized','input_corpus':str(CORPUS)}
    signature=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    if (out/'METHOD.json').exists() and json.loads((out/'METHOD.json').read_text()) != config:
        raise ValueError('Embedding method changed; choose a fresh run')
    dump(out/'METHOD.json',config)
    started=time.time()
    dump(out/f'EXECUTION_{time.time_ns()}.json',{'backend':execution,'model_path':str(model_path),
        'onnx_sha256':sha(model_path),'token_budget':args.token_budget,'max_batch':128,
        'note':'Identical model weights and text view; FP16 graph fusion can differ in floating-point rounding.'})
    for p in parts():
        dest=out/(p.stem+'.npy'); audit=out/(p.stem+'.json')
        source_hash=sha(p)
        if dest.exists() and audit.exists():
            old=json.loads(audit.read_text())
            if old['input_sha256'] != source_hash or old['method_sha256'] != signature:
                raise ValueError('Cached embedding provenance mismatch')
            continue
        frame=pq.read_table(p,columns=['row_id','source','title','body','usable']).to_pandas()
        tok.no_truncation(); tok.no_padding()
        texts=[]
        truncated=0
        for r in frame.itertuples():
            title=str(r.title or ''); body=str(r.body or '')
            if r.source=='paper':
                texts.append(title+'\n'+body)
            else:
                tt=tok.encode(title,add_special_tokens=False).ids[:192]
                bb=tok.encode(body,add_special_tokens=False).ids
                budget=2044-len(tt)
                if len(bb)>budget:
                    truncated+=1; a=budget//3; mid=len(bb)//2
                    bb=bb[:a]+bb[mid-a//2:mid-a//2+a]+bb[-(budget-2*a):]
                texts.append(tok.decode(tt+bb,skip_special_tokens=True))
        tok.enable_truncation(max_length=2048)
        encoded=[]
        for i in range(0,len(texts),512):
            encoded.extend(tok.encode_batch(texts[i:i+512]))
        lengths=np.array([len(e.ids) for e in encoded])
        valid=frame.usable.to_numpy() & np.array([bool(t.strip()) for t in texts])
        order=np.flatnonzero(valid)
        order=order[np.argsort(lengths[order],kind='stable')]
        partial=out/(p.stem+'.partial.npy'); checkpoint=out/(p.stem+'.checkpoint.json')
        pos=0
        executions=[execution]
        if partial.exists() and checkpoint.exists():
            cp=json.loads(checkpoint.read_text())
            if cp['input_sha256']!=source_hash or cp['method_sha256']!=signature:
                raise ValueError('Checkpoint provenance mismatch')
            pos=cp['position']; arr=np.lib.format.open_memmap(partial,mode='r+')
            executions=sorted(set(cp.get('execution_backends',['original_fp16'])+[execution]))
        else:
            arr=np.lib.format.open_memmap(partial,mode='w+',dtype=np.float32,shape=(len(frame),1024)); arr[:]=0
        last=0
        while pos<len(order):
            upper=lengths[order[min(pos+127,len(order)-1)]]
            size=max(1,min(128,args.token_budget//max(32,int(upper))))
            ix=order[pos:pos+size]
            width=int(lengths[ix].max())
            ids=np.full((len(ix),width),1,np.int64); mask=np.zeros_like(ids)
            for j,i in enumerate(ix):
                ids[j,:lengths[i]]=encoded[i].ids; mask[j,:lengths[i]]=1
            vec=session.run(['sentence_embedding'],{'input_ids':ids,'attention_mask':mask})[0]
            norm=np.linalg.norm(vec,axis=1,keepdims=True)
            if not np.isfinite(vec).all() or (norm<=1e-12).any():
                raise ValueError('Invalid BGE output')
            arr[ix]=vec/norm; pos+=len(ix)
            if time.time()-last>30 or pos==len(order):
                arr.flush(); cp={'part':p.stem,'position':pos,'part_documents':len(frame),'input_sha256':source_hash,'method_sha256':signature,'seconds_process':time.time()-started}
                cp['execution_backends']=executions
                dump(checkpoint,cp); dump(RUN/'ENCODING_PROGRESS.json',cp)
                print('ENCODE',p.stem,pos,'/',len(order),'elapsed',round(time.time()-started),flush=True); last=time.time()
        arr.flush(); del arr; partial.replace(dest)
        dump(audit,{'documents':len(frame),'valid_embeddings':int(valid.sum()),'unusable':int((~valid).sum()),'transfer_long_text_sampled':truncated,
            'execution_backends':executions,
            'input_sha256':source_hash,'method_sha256':signature,'embedding_sha256':sha(dest),'row_ids_sha256':hashlib.sha256(frame.row_id.to_numpy().tobytes()).hexdigest()})
    audits=[json.loads((out/(p.stem+'.json')).read_text()) for p in parts()]
    dump(RUN/'ENCODING_COMPLETE.json',{'documents':sum(a['documents'] for a in audits),'valid_embeddings':sum(a['valid_embeddings'] for a in audits),'parts':len(audits),'method':config,
        'execution_backends':sorted({e for a in audits for e in a.get('execution_backends',['original_fp16'])})})
    print('FULL ENCODING COMPLETE',flush=True)


if __name__=='__main__':
    main()
