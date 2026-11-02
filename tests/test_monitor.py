import importlib.util, pathlib, tempfile, unittest
from unittest.mock import patch
import monitor, stock_common, run_all
ROOT=pathlib.Path(__file__).resolve().parents[1]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
att=module('att','retailers/ATTduoStockChecker/monitor.py')
bb=module('bb','retailers/BestBuyDuoStockChecker/monitor.py')
class ReliabilityTests(unittest.TestCase):
 def test_only_known_negative_to_positive_alerts(self):
  prev={'product':'x','stores':[{'id':'a','status':'unavailable'},{'id':'b','status':'unknown'},{'id':'d','status':'unavailable','stale':True}]}
  curr={'product':'x','stores':[{'id':x,'status':'available'} for x in ['a','b','c','d']]}
  self.assertEqual([s['id'] for s in stock_common.transitions(prev,curr)],['a'])
  curr['product']='other';self.assertEqual(stock_common.transitions(prev,curr),[])
 def test_att_failure_never_sold_out(self):
  for obj in [{},{'error':{'errorId':'DENIED'}}]:self.assertEqual(att.parse(obj,'10001')['status'],'unknown')
  self.assertEqual(att.parse({'error':{'errorId':'UIS-INV-00003'}},'10001')['status'],'unavailable')
 def test_att_nonfinite_quantities_unknown(self):
  d={'content':{'storeList':[{'id':'x','region':'NY','availableQuantity':'NaN'}]}}
  self.assertEqual(att.parse(d,'10001')['stores'][0]['status'],'unknown')
 def test_apple_malformed_response_fails(self):
  with patch.object(monitor,'fetch_json',return_value={'body':{'stores':[]}}):
   with self.assertRaises(ValueError):monitor.check('10001')
 def test_apple_filters_non_target_states_and_keeps_unknown(self):
  d={'body':{'stores':[{'storeNumber':'a','state':'NY','partsAvailability':{monitor.PART:{'pickupDisplay':'unexpected'}}},{'storeNumber':'b','state':'PA'}]}}
  with patch.object(monitor,'fetch_json',return_value=d):self.assertEqual(monitor.check('10001')['a']['status'],'unknown');self.assertNotIn('b',monitor.check('10001'))
 def test_atomic_save(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)/'out.json';stock_common.save(p,{'health':'ok'});self.assertEqual(run_all.read(p),{'health':'ok'});self.assertFalse(p.with_suffix('.json.tmp').exists())
 def test_timeout_replaces_current_stock(self):
  with tempfile.TemporaryDirectory() as t:
   root=pathlib.Path(t);(root/'docs').mkdir();stock_common.save(root/'docs/x.json',{'product':'x','updated':'old','stores':[{'id':'a','status':'available'}]})
   with patch.object(run_all,'ROOT',root),patch.object(run_all.subprocess,'run',side_effect=TimeoutError):run_all.run(('Test','a.py','x.json'))
   d=run_all.read(root/'docs/x.json');self.assertEqual(d['health'],'error');self.assertEqual(d['stores'],[]);self.assertEqual(len(d['lastKnownStores']),1)
 def test_bestbuy_missing_key_explicit(self):
  with tempfile.TemporaryDirectory() as t,patch.dict('os.environ',{},clear=True),patch.object(bb,'OUT',pathlib.Path(t)/'status.json'):
   bb.main();d=run_all.read(bb.OUT);self.assertEqual(d['health'],'setup_required');self.assertEqual(d['stores'],[])
 def test_auth_failures_are_not_retried(self):
  import urllib.error
  error=urllib.error.HTTPError('https://example.test',403,'denied',{},None)
  with patch.object(stock_common.urllib.request,'urlopen',side_effect=error) as request:
   with self.assertRaises(urllib.error.HTTPError):stock_common.fetch_json('https://example.test')
   self.assertEqual(request.call_count,1)
 def test_long_retry_after_is_not_hammered(self):
  import urllib.error
  error=urllib.error.HTTPError('https://example.test',429,'slow down',{'Retry-After':'120'},None)
  with patch.object(stock_common.urllib.request,'urlopen',side_effect=error) as request,patch.object(stock_common.time,'sleep') as sleep:
   with self.assertRaises(urllib.error.HTTPError):stock_common.fetch_json('https://example.test')
   self.assertEqual(request.call_count,1);sleep.assert_not_called()
if __name__=='__main__':unittest.main()
