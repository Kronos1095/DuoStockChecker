"""Apple regional pickup adapter; failures never mean sold out."""
import concurrent.futures, datetime, os, pathlib, urllib.parse
from stock_common import fetch_json, save
ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/'docs'/'status.json'
PART=os.getenv('APPLE_PART_NUMBER','').strip() or 'MK1E4LL/A'
ZIPS=['10001','10314','11530','11755','10601','10954','12203','13204','14225','14564','07601','07866','08807','07728','08648','08002']

def check(zipcode):
    qs=urllib.parse.urlencode({'pl':'true','location':zipcode,'parts.0':PART})
    obj=fetch_json('https://www.apple.com/shop/retail/pickup-message?'+qs)
    stores=obj.get('body',{}).get('stores')
    if not isinstance(stores,list) or not stores: raise ValueError('No Apple stores returned')
    result={}
    for s in stores:
        a=s.get('partsAvailability',{}).get(PART,{})
        v=a.get('pickupDisplay'); key=s.get('storeNumber')
        state=s.get('state') or s.get('address',{}).get('state')
        if state not in ('NY','NJ'): continue
        if not key: continue
        result[key]={'id':key,'name':s.get('storeName','Apple Store'),'status':v if v in ('available','unavailable') else 'unknown','storeNumber':key,'state':state}
    if not result: raise ValueError('No matching Apple store records')
    return result

def main():
    stores={};failed=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        work={pool.submit(check,z):z for z in ZIPS}
        for future in concurrent.futures.as_completed(work):
            try:
                for key,s in future.result().items():
                    if key in stores and stores[key]['status']!=s['status']: s=dict(s,status='unknown')
                    stores[key]=s
            except Exception: failed.append(work[future])
    unknown=sum(s['status']=='unknown' for s in stores.values())
    health='error' if not stores else 'partial' if failed or unknown else 'ok'
    save(OUT,dict(updated=datetime.datetime.now(datetime.timezone.utc).isoformat(),product=PART,health=health,message='Apple regional pickup searches',coverage='Regional ZIP searches; complete NY/NJ coverage is not independently verified.',searchesChecked=len(ZIPS)-len(failed),searchesTotal=len(ZIPS),failedSearches=failed,stores=sorted(stores.values(),key=lambda s:s['name'])))
    return int(health!='ok')
if __name__=='__main__': raise SystemExit(main())
