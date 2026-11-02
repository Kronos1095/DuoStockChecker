import unittest
import monitor
class ParserTests(unittest.TestCase):
 def test_explicit_negative(self):
  self.assertEqual(monitor.parse({'error':{'errorId':'UIS-INV-00003'}},'10001')['status'],'unavailable')
 def test_error_unknown(self):
  self.assertEqual(monitor.parse({'error':{'errorId':'ACCESS_DENIED'}},'10001')['status'],'unknown')
 def test_missing_data_unknown(self):
  self.assertEqual(monitor.parse({},'10001')['status'],'unknown')
 def test_quantity_and_state(self):
  result=monitor.parse({'content':{'storeList':[{'id':'1','region':'NY','availableQuantity':'2'},{'id':'2','region':'NJ'},{'id':'3','region':'PA','availableQuantity':9}]}},'10001')
  self.assertEqual([s['status'] for s in result['stores']],['available','unknown'])
if __name__=='__main__': unittest.main()

