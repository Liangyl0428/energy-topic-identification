from refine_common import *
from tokenizers import Tokenizer
import onnxruntime as ort

class LocalEncoder:
    def __init__(self):
        model=OLD/'models/multilingual_minilm'
        self.tok=Tokenizer.from_file(str(model/'tokenizer.json'))
        self.tok.no_padding();self.tok.no_truncation()
        opts=ort.SessionOptions();opts.intra_op_num_threads=2;opts.inter_op_num_threads=1
        opts.enable_mem_pattern=False;opts.log_severity_level=3
        self.session=ort.InferenceSession(str(model/'onnx/model_O4_pooled.onnx'),sess_options=opts,
            providers=[('CUDAExecutionProvider',{'gpu_mem_limit':14000*1024**2,'arena_extend_strategy':'kSameAsRequested'}),'CPUExecutionProvider'])
        assert self.session.get_providers()[0]=='CUDAExecutionProvider',self.session.get_providers()

    def encode(self,records):
        encoded=self.tok.encode_batch([x for r in records for x in (r['title'],r.get('body',''))],add_special_tokens=False)
        sequences=[];owners=[];weights=[]
        for i,r in enumerate(records):
            title=encoded[2*i].ids;body=encoded[2*i+1].ids
            if not title and not body:continue
            if len(title)+len(body)<=125:
                sequences.append([0]+title+([2] if body else [])+body+[2]);owners.append(i);weights.append(max(1,len(title)+len(body)))
            else:
                prefix=title[:24];remaining=title[24:]+body;width=125-len(prefix);covered=0
                for j in range(0,len(remaining),width):
                    piece=remaining[j:j+width];newly=len(piece)+(len(prefix) if j==0 else 0);weight=newly
                    if r.get('source')=='policy':
                        total=len(title)+len(body);main=min(total,4096);main_new=min(newly,max(0,main-covered))
                        weight=.4*newly/total+.6*main_new/main
                    sequences.append([0]+prefix+[2]+piece+[2]);owners.append(i);weights.append(weight);covered+=newly
        result=np.zeros((len(records),384),np.float32)
        lengths=np.array([len(s) for s in sequences]);order=np.argsort(lengths,kind='stable')
        for start in range(0,len(order),32):
            ix=order[start:start+32];width=int((lengths[ix].max()+15)//16*16)
            ids=np.ones((len(ix),width),np.int64);mask=np.zeros_like(ids)
            for k,j in enumerate(ix):ids[k,:lengths[j]]=sequences[j];mask[k,:lengths[j]]=1
            out=self.session.run(['sentence_embedding'],{'input_ids':ids,'attention_mask':mask,'token_type_ids':np.zeros_like(ids)})[0]
            np.add.at(result,np.array(owners)[ix],out*np.array(weights,dtype=np.float32)[ix,None])
        norm=np.linalg.norm(result,axis=1,keepdims=True)
        result/=np.maximum(norm,1e-12)
        assert np.isfinite(result).all()
        return result
