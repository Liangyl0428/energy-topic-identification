"""Same sklearn multiplicative updates, caching fixed-H products per W solve."""
import numpy as np
from functools import lru_cache
from scipy import linalg
from sklearn.decomposition import MiniBatchNMF
from sklearn.decomposition._nmf import _multiplicative_update_w
from sklearn.utils.extmath import safe_sparse_dot


class CachedMiniBatchNMF(MiniBatchNMF):
    def _solve_W(self,X,H,max_iter):
        if self._beta_loss!=2:
            return super()._solve_W(X,H,max_iter)
        avg=np.sqrt(X.mean()/self._n_components)
        W=np.full((X.shape[0],self._n_components),avg,dtype=X.dtype)
        buffer=W.copy()
        l1,_,l2,_=self._compute_regularization(X)
        hht=H@H.T
        xht=safe_sparse_dot(X,H.T)
        for _ in range(max_iter):
            W,*_unused=_multiplicative_update_w(X,W,H,self._beta_loss,l1,l2,self._gamma,
                HHt=hht,XHt=xht,update_H=False)
            difference=linalg.norm(W-buffer)/linalg.norm(W)
            if self.tol>0 and difference<=self.tol:
                break
            buffer[:]=W
        return W


class GpuMiniBatchNMF(CachedMiniBatchNMF):
    """Float32 CUDA execution of the same unregularized Frobenius MU steps.

    Model arrays remain NumPy for portable checkpoints. CuPy is optional when
    loading a model on a CPU-only machine; the cached sklearn path is used there.
    """
    @staticmethod
    @lru_cache(maxsize=1)
    def _cuda():
        try:
            import cupy as cp
            if cp.cuda.runtime.getDeviceCount()<1:
                return None
        except ImportError:
            return None
        except Exception:
            # CuPy can be installed on a machine without a working CUDA driver.
            return None
        return cp

    def _gpu_w(self,X,H,max_iter,cp):
        import cupyx.scipy.sparse as cs
        x=cs.csr_matrix(X)
        h=cp.asarray(H)
        avg=np.sqrt(X.mean()/self._n_components)
        w=cp.full((X.shape[0],self._n_components),avg,dtype=X.dtype)
        xht=x@h.T;hht=h@h.T
        for _ in range(max_iter):
            old=w.copy();den=w@hht
            den[den==0]=np.finfo(np.float32).eps
            w*=xht/den
            if self.tol>0 and float(cp.linalg.norm(w-old)/cp.linalg.norm(w))<=self.tol:
                break
        return x,w,h

    def _solve_W(self,X,H,max_iter):
        cp=self._cuda()
        if cp is None or self._beta_loss!=2 or any(self._compute_regularization(X)):
            return super()._solve_W(X,H,max_iter)
        return cp.asnumpy(self._gpu_w(X,H,max_iter,cp)[1])

    def _minibatch_step(self,X,W,H,update_H):
        cp=self._cuda()
        if cp is None or self._beta_loss!=2 or any(self._compute_regularization(X)) or W is not None:
            return super()._minibatch_step(X,W,H,update_H)
        x,w,h=self._gpu_w(X,H,self.fresh_restarts_max_iter,cp)
        if update_H:
            numerator=(x.T@w).T
            denominator=(w.T@w)@h
            denominator[denominator==0]=np.finfo(np.float32).eps
            a=cp.asarray(self._components_numerator)*self._rho + numerator*h
            b=cp.asarray(self._components_denominator)*self._rho + denominator
            H[:]=cp.asnumpy(a/b)
            self._components_numerator[:]=cp.asnumpy(a)
            self._components_denominator[:]=cp.asnumpy(b)
        # partial_fit discards batch_cost; convergence diagnostics are separately
        # recomputed from the actual factorization after each full epoch.
        return 0.0
