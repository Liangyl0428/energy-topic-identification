import unittest
import numpy as np
from semantic_mapping import make_mapping,map_labels

def g(members,name='x',did='D1'):return dict(members=members,canonical_name=name,decision_id=did)
class MappingSafetyTests(unittest.TestCase):
    def test_unusable_and_unknown_negative(self):
        _,lookup,_=make_mapping([g([1,3])],5)
        self.assertEqual(map_labels(np.array([-2,0,1,2,3,4]),lookup).tolist(),[-2,0,1,2,1,3])
        with self.assertRaises(ValueError):map_labels(np.array([-1]),lookup)
    def test_overlap_is_not_transitive_auto_merge(self):
        with self.assertRaises(ValueError):make_mapping([g([1,2]),g([2,3],'y','D2')],5)
    def test_malformed_group_fails(self):
        for members in [[1],[1,1],[-2,2],[1,5],[1,2.0]]:
            with self.assertRaises(ValueError):make_mapping([g(members)],5)
    def test_out_of_range_and_float_label_fail(self):
        _,lookup,_=make_mapping([],5)
        for labels in [np.array([5]),np.array([1.2])]:
            with self.assertRaises(ValueError):map_labels(labels,lookup)
    def test_groups_are_order_independent_and_names_unique(self):
        a=make_mapping([g([4,2])],6)[0];b=make_mapping([g([2,4])],6)[0]
        np.testing.assert_array_equal(a,b)
        with self.assertRaises(ValueError):make_mapping([g([0,1]),g([2,3],did='D2')],5)
if __name__=='__main__':unittest.main()
