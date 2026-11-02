"""Bounded HTTP retries, atomic JSON writes, and transition-only alerts."""
import datetime, email.utils, json, os, pathlib, random, time, urllib.error, urllib.request

def fetch_json(url, payload=None, timeout=12):
    data=None if payload is None else json.dumps(payload).encode()
    for attempt in range(2):
        try:
            req=urllib.request.Request(url,data=data,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json','Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=timeout) as response:
                result=json.load(response)
                if not isinstance(result,dict): raise ValueError('Expected JSON object')
                return result
        except urllib.error.HTTPError as exc:
            if exc.code not in (429,500,502,503,504) or attempt: raise
            delay=2
            retry=exc.headers.get('Retry-After','')
            try: delay=float(retry)
            except ValueError:
                try: delay=email.utils.parsedate_to_datetime(retry).timestamp()-time.time()
                except (ValueError,TypeError): pass
            if delay>15: raise  # Leave longer throttling delays to the next scheduled run.
            time.sleep(max(1,delay)+random.random())
        except (TimeoutError,urllib.error.URLError):
            if attempt: raise
            time.sleep(1+random.random())

def save(path,data):
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,indent=2)+'\n');os.replace(tmp,path)

def transitions(previous,current):
    if previous.get('product')!=current.get('product'): return []
    old={s['id']:s for s in previous.get('stores',[]) if s.get('id')}
    return [s for s in current.get('stores',[]) if s.get('id') in old and s.get('status')=='available' and old[s['id']].get('status')=='unavailable' and not s.get('stale') and not old[s['id']].get('stale')]
