import sqlite3
import tempfile
import unittest
from pathlib import Path
import explore
import hollow_db

class ExploreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'test.sqlite3'
        self.con=hollow_db.build_database(path=str(self.path),n=300)
        explore.init(self.con)
        self.m=explore.missions(self.con)[0]
        # Pick an eligible resident and give them enough health for a demo
        job=self.m['preferred_jobs'].split(',')[0]
        self.r=self.con.execute('SELECT id FROM residents WHERE work=? LIMIT 1',(job,)).fetchone()[0]
        self.con.execute('UPDATE residents SET health=90 WHERE id=?',(self.r,));self.con.commit()
    def tearDown(self):self.con.close();self.tmp.cleanup()
    def test_map_and_missions(self):
        self.assertEqual(len(explore.map_data(self.con)),7)
        self.assertEqual(len(explore.missions(self.con)),3)
    def test_non_destructive_init(self):
        a=explore.apply(self.con,self.r,self.m['id']);explore.init(self.con)
        self.assertEqual(explore.applications(self.con,self.r)[0]['id'],a['application_id'])
    def test_lifecycle_and_pay_once(self):
        initial=explore.resident(self.con,self.r)['money']
        a=explore.apply(self.con,self.r,self.m['id'])['application_id']
        explore.decide(self.con,a,'approved');explore.start(self.con,a)
        explore.submit_report(self.con,a,'Water samples collected and labeled','water')
        report=explore.reports(self.con)[0]['id']
        self.assertEqual(explore.verify_report(self.con,report,True)['paid'],self.m['base_reward']+50)
        self.assertEqual(explore.resident(self.con,self.r)['money'],initial+self.m['base_reward']+50)
        with self.assertRaises(ValueError):explore.verify_report(self.con,report,True)
    def test_ineligible(self):
        self.con.execute('UPDATE residents SET health=10 WHERE id=?',(self.r,));self.con.commit()
        with self.assertRaises(ValueError):explore.apply(self.con,self.r,self.m['id'])
    def test_no_reward_before_verified(self):
        initial=explore.resident(self.con,self.r)['money']
        a=explore.apply(self.con,self.r,self.m['id'])['application_id']
        explore.decide(self.con,a,'approved');explore.start(self.con,a)
        explore.submit_report(self.con,a,'I observed an abandoned bridge','none')
        self.assertEqual(explore.resident(self.con,self.r)['money'],initial)
    def test_equipment_reserve(self):
        self.assertTrue(explore.equipment(2,10)['return_reserve_ok'])
        self.assertFalse(explore.equipment(8,100)['return_reserve_ok'])
    def test_report_validation(self):
        with self.assertRaises(ValueError):explore.submit_report(self.con,999,'tiny','none')
    def test_rejected_application_cannot_start(self):
        a=explore.apply(self.con,self.r,self.m['id'])['application_id']
        explore.decide(self.con,a,'rejected')
        with self.assertRaises(ValueError):explore.start(self.con,a)

if __name__=='__main__':unittest.main()
