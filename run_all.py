"""Run isolated retailer adapters concurrently, then publish/notify once."""
import concurrent.futures, datetime, json, os, pathlib, subprocess, sys, urllib.parse, urllib.request
from stock_common import save, transitions
ROOT=pathlib.Path(__file__).resolve().parent
ADAPTERS=[('Apple','monitor.py','status.json'),('AT&T','retailers/ATTduoStockChecker/monitor.py','att-status.json'),('Best Buy','retailers/BestBuyDuoStockChecker/monitor.py','bestbuy-status.json')]

def read(path):
    try: return json.loads(path.read_text())
    except (ValueError,OSError): return {}

def run(adapter):
    name,script,filename=adapter;path=ROOT/'docs'/filename;previous=read(path)
    env=dict(os.environ,PYTHONPATH=str(ROOT))
    try:
        proc=subprocess.run([sys.executable,str(ROOT/script)],cwd=ROOT,env=env,capture_output=True,text=True,timeout=180)
        current=read(path)
        if current.get('updated')==previous.get('updated') or not current.get('updated'): raise RuntimeError('Adapter did not publish fresh status')
    except Exception:
        current=dict(health='error',updated=datetime.datetime.now(datetime.timezone.utc).isoformat(),message='Adapter failed or exceeded its time budget.',stores=[],product=previous.get('product'))
    current['retailer']=name
    current['lastSuccess']=current['updated'] if current.get('health')=='ok' else previous.get('lastSuccess')
    current['notifications']='not configured' if not os.getenv('NTFY_TOPIC') else 'configured'
    # Retain prior snapshots only in a clearly marked history field, never as current inventory.
    if current['health'] in ('error','setup_required'): current['lastKnownStores']=previous.get('stores') or previous.get('lastKnownStores',[])
    alerts=transitions(previous,current)
    topic=os.getenv('NTFY_TOPIC','').strip()
    if topic and alerts:
        message=name+' iPhone Duo pickup: '+', '.join(s.get('name',s['id']) for s in alerts)
        req=urllib.request.Request('https://ntfy.sh/'+urllib.parse.quote(topic,safe=''),data=message.encode(),headers={'Title':'Duo restock','Tags':'iphone'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=10) as response: response.read()
        except Exception: current['notifications']='send failed; inventory result remains valid'
    save(path,current)
    return dict(retailer=name,health=current['health'])

def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool: results=list(pool.map(run,ADAPTERS))
    print(json.dumps(results))
    return int(any(s['health'] in ('error','partial') for s in results))
if __name__=='__main__': raise SystemExit(main())
