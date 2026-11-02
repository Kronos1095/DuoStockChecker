import json, os, urllib.request, urllib.parse, datetime, pathlib, sys
ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/'docs'/'status.json'
PART=os.getenv('APPLE_PART_NUMBER','').strip()
TOPIC=os.getenv('NTFY_TOPIC','').strip()
ZIPS=['10001','10314']
def check(zipcode):
    qs=urllib.parse.urlencode({'pl':'true','location':zipcode,'parts.0':PART})
    req=urllib.request.Request('https://www.apple.com/shop/retail/pickup-message?'+qs,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as r: obj=json.load(r)
    stores=obj.get('body',{}).get('stores')
    if not isinstance(stores,list) or not stores: raise ValueError('No stores in Apple response')
    result={}
    for s in stores:
        a=s.get('partsAvailability',{}).get(PART,{})
        v=a.get('pickupDisplay')
        if v not in ('available','unavailable'): continue
        k=str(s.get('storeNumber') or s.get('storeName'))
        result[k]={'name':s.get('storeName','Apple Store'),'status':v,'storeNumber':k}
    if not result: raise ValueError('No valid availability entries; verify part number')
    return result
def notify(names):
    if not TOPIC or not names: return
    url='https://ntfy.sh/'+urllib.parse.quote(TOPIC,safe='')
    body='iPhone Duo Star White 256GB pickup available: '+', '.join(names)+'\nhttps://www.apple.com/shop/buy-iphone/iphone-duo'
    req=urllib.request.Request(url,data=body.encode(),method='POST',headers={'Title':'iPhone Duo restock!','Priority':'urgent','Tags':'iphone,rotating_light','Click':'https://www.apple.com/shop/buy-iphone/iphone-duo'})
    urllib.request.urlopen(req,timeout=15).read()
def main():
    previous={}
    if OUT.exists():
        try: previous=json.loads(OUT.read_text())
        except (ValueError,OSError): pass
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    if not PART:
        state={'updated':now,'health':'setup_required','message':'Set APPLE_PART_NUMBER to the verified US Star White 256GB part number.','stores':previous.get('stores',[])}
    else:
        try:
            combined={}
            for z in ZIPS: combined.update(check(z))
            old={s['storeNumber']:s['status'] for s in previous.get('stores',[])}
            new=[s['name'] for k,s in combined.items() if s['status']=='available' and old.get(k)!='available']
            # First successful scan establishes a baseline; do not alert on unknown prior state.
            if previous.get('health')=='ok': notify(new)
            state={'updated':now,'health':'ok','message':'Apple pickup lookup succeeded','stores':sorted(combined.values(),key=lambda s:s['name'])}
        except Exception as e:
            state={'updated':now,'health':'error','message':str(e),'stores':previous.get('stores',[])}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(state,indent=2)+'\n')
    print(state['health'],state['message'])
    if state['health']=='error': sys.exit(1)
if __name__=='__main__': main()
