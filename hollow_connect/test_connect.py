import unittest
from unittest.mock import patch
import connect_engine as c

class ConnectTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(c.validate_report('Medical', 7, 'Urgent', 'Person injured')[1], 7)
    def test_bad_level(self):
        with self.assertRaises(ValueError): c.validate_report('Medical', 11, 'Urgent', 'Person injured')
    def test_short_description(self):
        with self.assertRaises(ValueError): c.validate_report('Medical', 2, 'Urgent', 'short')
    def test_bad_urgency(self):
        with self.assertRaises(ValueError): c.validate_report('Medical', 2, 'Extreme', 'Person injured')
    def test_team_mapping(self):
        self.assertEqual(c.recommended_team('Housing'), 'Rescue')
        self.assertEqual(c.recommended_team('Infrastructure'), 'Engineering')
    def test_admin_authorization(self):
        with self.assertRaises(PermissionError): c._coordinator(None, 'A0000001')
        c._coordinator(None, 'admin')

if __name__ == '__main__': unittest.main()
