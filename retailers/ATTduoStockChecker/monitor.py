"""AT&T public PDP pickup lookup. ZIP results are not all-store coverage."""
import concurrent.futures, datetime, json, pathlib
from stock_common import fetch_json, save
BILL_CODE = '6050G'
SKU = 'sku57765v2'
ZIPS = ['10001','10314','10451','11201','11373','11530','11746','11755','10601','10954','12203','13204','14225','14564','07001','07601','07470','07866','08807','07728','08648','08002','08053','08401']
OUT = pathlib.Path(__file__).resolve().parents[2] / 'docs' / 'att-status.json'

def parse(data, zipcode):
    error = data.get('error')
    if error:
        code = str(error.get('errorId','')).upper()
        if code == 'UIS-INV-00003':
            return dict(zip=zipcode, status='unavailable', message='AT&T reports items out of stock for this ZIP search.', stores=[])
        return dict(zip=zipcode, status='unknown', message='AT&T error: '+code, stores=[])
    stores = data.get('content',{}).get('storeList')
    if not isinstance(stores,list) or not stores:
        return dict(zip=zipcode,status='unknown',message='No validated store results.',stores=[])
    results = []
    for s in stores:
        if s.get('region') not in ('NY','NJ'): continue
        quantity = s.get('availableQuantity')
        try:
            quantity = float(quantity) if not isinstance(quantity,bool) else -1
            if not __import__('math').isfinite(quantity): quantity=-1
        except (ValueError,TypeError): quantity = -1
        results.append(dict(id=str(s.get('inv_id') or s.get('id','')), inventoryId=s.get('inv_id'), name=s.get('mystore_name') or s.get('name'), state=s.get('region'), city=s.get('city'), postal=s.get('postal'), status='available' if quantity>0 else 'unavailable' if quantity==0 else 'unknown', reportedQuantity=quantity if quantity>=0 else None))
    return dict(zip=zipcode,status='checked' if results else 'unknown',stores=results)

def check(zipcode):
    url='https://www.att.com/msapi/sales/uis/v1/inventory/storeavailability?zipCode='+zipcode
    try:
        data=fetch_json(url,{'itemDetails':[{'category':'phone','billCode':BILL_CODE}]})
        return parse(data,zipcode)
    except Exception:
        return dict(zip=zipcode,status='unknown',message='Request failed or invalid response.',stores=[])

def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool: searches=list(pool.map(check,ZIPS))
    stores={}
    for search in searches:
        for store in search['stores']:
            key=store['inventoryId'] or store['id']
            if key in stores and stores[key]['status']!=store['status']: store=dict(store,status='unknown')
            stores[key]=store
    unknown=sum(s['status']=='unknown' for s in searches)
    state=dict(updated=datetime.datetime.now(datetime.timezone.utc).isoformat(),retailer='AT&T',sku=SKU,billCode=BILL_CODE,health='partial' if unknown else 'ok',coverage='ZIP searches only; complete NY/NJ store coverage is not verified.',searchesChecked=len(searches)-unknown,searchesTotal=len(searches),searches=searches,stores=list(stores.values()))
    OUT.parent.mkdir(exist_ok=True,parents=True)
    state['product']=SKU
    state['message']='AT&T ZIP-level pickup searches'
    save(OUT,state)
    print(f"AT&T: {len(searches)-unknown}/{len(searches)} ZIP searches succeeded; {len(stores)} individual store results")
    return int(unknown>0)

if __name__=='__main__': raise SystemExit(main())

