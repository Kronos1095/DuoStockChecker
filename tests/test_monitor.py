import unittest, pathlib, json, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import monitor
class TestConfig(unittest.TestCase):
 def test_zips(self): self.assertEqual(monitor.ZIPS,['10001','10314'])
 def test_dashboard_exists(self): self.assertTrue((monitor.ROOT/'docs'/'index.html').exists())
 def test_baseline_valid(self): self.assertEqual(json.loads((monitor.ROOT/'docs'/'status.json').read_text())['health'],'setup_required')
if __name__=='__main__': unittest.main()
