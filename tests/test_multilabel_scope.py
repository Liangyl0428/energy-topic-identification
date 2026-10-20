"""Behavioral checks for scale invariance, abstention and reversible filtering."""
import sys
from pathlib import Path
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipelines/multilabel_scope'))
from run import base
from apply_scope import scope_membership


class MembershipTests(unittest.TestCase):
    def test_nmf_scaling_does_not_change_contribution(self):
        w=np.array([[1.,2.,3.]],dtype=np.float32)
        h=np.array([[1.,0.],[0.,2.],[1.,1.]],dtype=np.float32)
        scale=np.array([.1,10.,2.],dtype=np.float32)
        np.testing.assert_allclose(base.relative_contributions(w,h),base.relative_contributions(w/scale,h*scale[:,None]),rtol=1e-6)

    def test_exclusion_preserves_other_memberships_without_renormalization(self):
        ids,weights=scope_membership([0,1,2],[.60,.25,.15],['exclude','keep_core','keep_supporting'])
        self.assertEqual(ids,[1,2]);self.assertEqual(weights,[.25,.15]);self.assertAlmostEqual(sum(weights),.4)

    def test_exact_threshold_is_included_and_there_is_no_top_n_cap(self):
        ids,weights=scope_membership(range(8),[.125]*8,['keep_core']*8,threshold=.125)
        self.assertEqual(len(ids),8)

    def test_no_primary_fallback_or_forced_assignment(self):
        self.assertEqual(scope_membership([0],[.09],['keep_core']),([],[]))
        self.assertEqual(scope_membership([0],[.9],['review']),([],[]))
        self.assertEqual(scope_membership([0],[.9],['keep_core'],qualified=False),([],[]))

    def test_zero_feature_contributions_remain_zero(self):
        np.testing.assert_array_equal(base.relative_contributions(np.zeros((2,3)),np.ones((3,4))),np.zeros((2,3)))


if __name__=='__main__':unittest.main()
