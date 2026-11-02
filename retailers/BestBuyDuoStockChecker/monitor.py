"""Best Buy official API monitor. Requires BESTBUY_API_KEY; never logs URLs."""
import datetime, json, os, pathlib, urllib.parse, time
from stock_common import fetch_json, save

SKU = '6525566'  # iPhone Duo, Star White, 256GB, AT&T
OUT = pathlib.Path(__file__).resolve().parents[2] / 'docs' / 'bestbuy-status.json'

def request(path, params):
    params = dict(params, apiKey=os.environ['BESTBUY_API_KEY'])
    time.sleep(0.25)  # At most four sequential API calls/sec, below the documented five/sec limit.
    return fetch_json('https://api.bestbuy.com/v1/' + path + '?' + urllib.parse.urlencode(params))

def scan():
    inventory = []
    for state in ('NY', 'NJ'):
        page = 1
        while page <= 20:
            data = request('stores(region=' + state + ')', dict(format='json', show='storeId,name,city,region', pageSize=100, page=page))
            if not isinstance(data.get('stores'), list) or not isinstance(data.get('totalPages'), int):
                raise ValueError('Malformed store directory')
            inventory.extend(data['stores'])
            if data['totalPages']>20: raise ValueError('Directory pagination exceeded safety limit')
            if page >= data['totalPages']: break
            page += 1
    if not inventory: raise ValueError('Empty store directory')
    results = []
    for store in inventory:
        try:
            data = request('products/' + SKU + '/stores.json', dict(storeId=store['storeId']))
            if not isinstance(data.get('stores'), list) or not isinstance(data.get('ispuEligible'), bool):
                raise ValueError('Malformed stock response')
            found = any(str(s.get('storeID')) == str(store['storeId']) for s in data['stores'])
            results.append(dict(store, id=str(store['storeId']), status='available' if found else 'unavailable'))
        except Exception:
            results.append(dict(store, id=str(store['storeId']), status='unknown'))
    return results

def main():
    state = dict(updated=datetime.datetime.now(datetime.timezone.utc).isoformat(), sku=SKU, product=SKU, stores=[])
    if not os.getenv('BESTBUY_API_KEY'):
        state.update(health='setup_required', message='API key required. Public website fulfillment returned authorization code 401 during keyless testing; no keyless stock results are claimed.')
    else:
        try:
            state['stores'] = scan()
            unknown = sum(s['status'] == 'unknown' for s in state['stores'])
            state.update(health='partial' if unknown else 'ok', checked=len(state['stores'])-unknown, total=len(state['stores']))
        except Exception:
            state.update(health='error', message='Best Buy API request failed. Check key, API access and response schema.')
    save(OUT,state)
    print(state['health'])
    return int(state['health'] in ('error', 'partial'))

if __name__ == '__main__':
    raise SystemExit(main())

