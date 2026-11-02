"""Always-on worker: independent polling lanes and a persistent notification outbox."""
import concurrent.futures, datetime, json, os, pathlib, signal, sqlite3, subprocess, sys, threading, time, urllib.parse, urllib.request, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import monitor
from stock_common import save
ROOT=pathlib.Path(__file__).resolve().parent
DATA=pathlib.Path(os.getenv('STOCK_DATA_DIR','/data'))
STOP=threading.Event()
DB_LOCK=threading.Lock()

def connect():
    db=sqlite3.connect(DATA/'alerts.sqlite',timeout=10)
    db.execute('PRAGMA journal_mode=WAL')
    return db

def initialize():
    DATA.mkdir(parents=True,exist_ok=True)
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS observed (key TEXT PRIMARY KEY,status TEXT,seen REAL)')
        db.execute('CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY,created REAL,title TEXT,body TEXT,link TEXT,sent REAL,attempts INTEGER DEFAULT 0)')

def observe(retailer,product,stores,now=None):
    now=time.time() if now is None else now
    with DB_LOCK,connect() as db:
        for s in stores:
            status=s.get('status');sid=s.get('id')
            if not sid or status not in ('available','unavailable'):continue
            key=f'{retailer}:{product}:{sid}'
            old=db.execute('SELECT status FROM observed WHERE key=?',(key,)).fetchone()
            if status=='available' and (old is None or old[0]!='available'):
                link='https://www.apple.com/shop/buy-iphone/iphone-duo' if retailer=='Apple' else 'https://www.att.com/buy/phones/apple-iphone-duo-256gb-star-white.html'
                body=f"{retailer}: {s.get('name') or sid} — Star White 256GB reported available. Open the retailer to confirm and reserve."
                db.execute('INSERT INTO outbox(id,created,title,body,link) VALUES(?,?,?,?,?)',(str(uuid.uuid4()),now,'Duo pickup available',body,link))
            db.execute('INSERT OR REPLACE INTO observed VALUES(?,?,?)',(key,status,now))

def publish(title,body,link):
    topic=os.getenv('NTFY_TOPIC','').strip()
    if not topic:raise RuntimeError('Notification topic not configured')
    headers={'Title':title,'Priority':'urgent','Tags':'iphone,rotating_light','Click':link,'Content-Type':'text/plain; charset=utf-8'}
    token=os.getenv('NTFY_TOKEN','').strip()
    if token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request('https://ntfy.sh/'+urllib.parse.quote(topic,safe=''),data=body.encode(),headers=headers,method='POST')
    with urllib.request.urlopen(req,timeout=8) as response:
        if response.status!=200:raise RuntimeError('Push service rejected alert')
        response.read()

def alert_loop():
    if os.getenv('NTFY_TOPIC') and os.getenv('SEND_TEST_ON_START','true').lower()=='true':
        try:
            publish('Duo Stock Watch test','TEST: continuous worker started. Confirm this arrives promptly while your iPad is locked.','https://www.apple.com/shop/buy-iphone/iphone-duo')
            save(DATA/'notification-health.json',dict(testAcceptedAt=time.time(),delivery='Accepted by push server; device receipt requires confirmation.'))
        except Exception:save(DATA/'notification-health.json',dict(error='Startup notification failed',updated=time.time()))
    while not STOP.is_set():
        with connect() as db: rows=db.execute('SELECT id,title,body,link FROM outbox WHERE sent IS NULL AND created>? AND attempts<4 ORDER BY created LIMIT 10',(time.time()-120,)).fetchall()
        for key,title,body,link in rows:
            try:
                publish(title,body,link)
                with connect() as db:db.execute('UPDATE outbox SET sent=?,attempts=attempts+1 WHERE id=?',(time.time(),key))
                save(DATA/'notification-health.json',dict(lastAcceptedAt=time.time(),delivery='Accepted by push server; no device receipt tracking.'))
            except Exception:
                with connect() as db:db.execute('UPDATE outbox SET attempts=attempts+1 WHERE id=?',(key,))
                save(DATA/'notification-health.json',dict(updated=time.time(),error='Alert send failed; bounded retry pending.'))
        STOP.wait(5)

def repeat(name,interval,fn):
    failures=0
    while not STOP.is_set():
        started=time.monotonic()
        try:fn();failures=0
        except Exception:failures+=1
        save(DATA/(name+'-heartbeat.json'),dict(updated=time.time(),failures=failures))
        delay=max(1,interval-(time.monotonic()-started)) if not failures else min(300,interval*2**min(failures,4))
        STOP.wait(delay)

def fast_apple():
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        stores=list(monitor.check(os.getenv('APPLE_HOT_ZIP','10001')).values())
        # Alerts are queued before the dashboard is updated.
        observe('Apple',monitor.PART,stores)
        save(DATA/'apple-fast-status.json',dict(updated=now,health='ok',message='Nearby Apple pickup scan',product=monitor.PART,coverage='Nearby stores returned for ZIP '+os.getenv('APPLE_HOT_ZIP','10001')+'; wider NY/NJ scan runs separately.',stores=stores,notifications='configured' if os.getenv('NTFY_TOPIC') else 'not configured'))
    except Exception:
        save(DATA/'apple-fast-status.json',dict(updated=now,health='error',message='Apple request failed; backing off. No current inventory.',stores=[]));raise

def regional(script,filename,retailer):
    env=dict(os.environ,PYTHONPATH=str(ROOT),STOCK_DATA_DIR=str(DATA))
    target=DATA/filename;before=target.stat().st_mtime_ns if target.exists() else None
    proc=subprocess.run([sys.executable,str(ROOT/script)],cwd=ROOT,env=env,capture_output=True,timeout=150)
    if not target.exists() or target.stat().st_mtime_ns==before:raise RuntimeError('No fresh output')
    d=json.loads(target.read_text())
    # Regional Apple scans do not feed alerts: a slower snapshot must not rewind fast-lane state.
    if retailer!='Apple':observe(retailer,d.get('product'),d.get('stores',[]))
    if proc.returncode:raise RuntimeError('Partial scan; back off')

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        path=urllib.parse.urlsplit(self.path).path
        if path=='/health':
            fast=DATA/'apple-fast-heartbeat.json'
            healthy=fast.exists() and time.time()-fast.stat().st_mtime<600
            payload=json.dumps({'worker':'running','appleLane':'responsive' if healthy else 'starting_or_stale','notificationsConfigured':bool(os.getenv('NTFY_TOPIC'))}).encode()
            self.send_response(200 if healthy else 503);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(payload);return
        allowed={'/':'index.html','/index.html':'index.html','/status.json':'apple-fast-status.json','/att-status.json':'att-status.json','/bestbuy-status.json':'bestbuy-status.json','/apple-regional-status.json':'status.json','/notification-health.json':'notification-health.json'}
        if path not in allowed:self.send_error(404);return
        file=ROOT/'docs/index.html' if allowed[path]=='index.html' else DATA/allowed[path]
        if not file.exists():self.send_error(503,'Waiting for first scan');return
        self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8' if path in ('/','/index.html') else 'application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(file.read_bytes())

def main():
    initialize()
    signal.signal(signal.SIGTERM,lambda *_:STOP.set());signal.signal(signal.SIGINT,lambda *_:STOP.set())
    lanes=[('apple-fast',max(30,int(os.getenv('APPLE_POLL_SECONDS','30'))),fast_apple),('apple-regional',300,lambda:regional('monitor.py','status.json','Apple')),('att',max(60,int(os.getenv('ATT_POLL_SECONDS','120'))),lambda:regional('retailers/ATTduoStockChecker/monitor.py','att-status.json','AT&T'))]
    if os.getenv('BESTBUY_API_KEY'):lanes.append(('bestbuy',300,lambda:regional('retailers/BestBuyDuoStockChecker/monitor.py','bestbuy-status.json','Best Buy')))
    else:save(DATA/'bestbuy-status.json',dict(updated=datetime.datetime.now(datetime.timezone.utc).isoformat(),health='setup_required',message='Best Buy API key required.',stores=[]))
    for name,interval,fn in lanes:threading.Thread(target=repeat,args=(name,interval,fn),daemon=True).start()
    threading.Thread(target=alert_loop,daemon=True).start()
    server=ThreadingHTTPServer(('0.0.0.0',int(os.getenv('PORT','8080'))),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    STOP.wait();server.shutdown()
if __name__=='__main__':main()
