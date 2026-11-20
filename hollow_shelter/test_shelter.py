import unittest
from shelter_engine import assess_level, rank_destinations

class ShelterTests(unittest.TestCase):
    def test_critical_housing(self):
        self.assertEqual(assess_level({'housing': 12, 'oxygen': 90})['status'], 'unsafe')
    def test_warning(self):
        self.assertEqual(assess_level({'housing': 40, 'oxygen': 90})['status'], 'caution')
    def test_missing_data(self):
        self.assertEqual(assess_level({'housing': 100})['status'], 'unknown')
    def test_safe_only_and_capacity(self):
        rows=[{'level': 2,'capacity': 10,'occupied': 4,'reserved': 3,'statuses': {'housing': 95,'oxygen': 95}},
              {'level': 3,'capacity': 50,'occupied': 0,'reserved': 0,'statuses': {'housing': 10,'oxygen': 95}},
              {'level': 4,'capacity': 5,'occupied': 5,'reserved': 0,'statuses': {'housing': 95,'oxygen': 95}}]
        self.assertEqual([(r['level'],r['free']) for r in rank_destinations(1, rows)], [(2,3)])
    def test_nearest_first(self):
        rows=[{'level': 5,'capacity': 10,'occupied': 0,'reserved': 0,'statuses': {'housing': 95,'oxygen': 95}},
              {'level': 3,'capacity': 10,'occupied': 0,'reserved': 0,'statuses': {'housing': 95,'oxygen': 95}}]
        self.assertEqual(rank_destinations(2, rows)[0]['level'],3)
    def test_reject_zero(self):
        with self.assertRaises(ValueError): rank_destinations(1, [], 0)

if __name__=='__main__': unittest.main()
