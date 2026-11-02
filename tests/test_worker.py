import pathlib,tempfile,unittest
from unittest.mock import patch
import worker
class WorkerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.p=patch.object(worker,'DATA',pathlib.Path(self.temp.name));self.p.start();worker.initialize()
 def tearDown(self):self.p.stop();self.temp.cleanup()
 def count(self):
  with worker.connect() as db:return db.execute('SELECT COUNT(*) FROM outbox').fetchone()[0]
 def test_first_available_alert_and_persistent_dedup(self):
  s=[{'id':'R250','name':'West 14th','status':'available'}]
  worker.observe('Apple','part',s);worker.initialize();worker.observe('Apple','part',s);self.assertEqual(self.count(),1)
 def test_unknown_does_not_reset_available(self):
  for status in ['available','unknown','available']:worker.observe('Apple','p',[{'id':'a','status':status}])
  self.assertEqual(self.count(),1)
 def test_new_restock_and_product_are_new_events(self):
  for status in ['available','unavailable','available']:worker.observe('Apple','p',[{'id':'a','status':status}])
  worker.observe('Apple','different',[{'id':'a','status':'available'}]);self.assertEqual(self.count(),3)
 def test_unavailable_does_not_alert(self):
  worker.observe('Apple','p',[{'id':'a','status':'unavailable'}]);self.assertEqual(self.count(),0)
if __name__=='__main__':unittest.main()
