"""Best Buy official API monitor. Requires BESTBUY_API_KEY; never logs URLs."""
import datetime, json, os, pathlib, urllib.parse, urllib.request

SKU = '6525566'  # iPhone Duo, Star White, 256GB, AT&T
OUT = pathlib.Path(__file__).parent / 'status.json'

def request(path, params):
    params = dict(params, apiKey=os.environ['BESTBUY_API_KEY'])
    with urllib.request.urlopen('https://api.bestbuy.com/v1/' + path + '?' + urllib.parse.urlencode(params), timeout=30) as response:
        return json.load(response)

def scan():
    inventory = []
    for state in ('NY', 'NJ'):
        page = 1
        while True:
            data = request('stores(region=' + state + ')', dict(format='json', show='storeId,name,city,region', pageSize=100, page=page))
            if not isinstance(data.get('stores'), list) or not isinstance(data.get('totalPages'), int):
                raise ValueError('Malformed store directory')
            inventory.extend(data['stores'])
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
            results.append(dict(store, status='available' if found else 'unavailable'))
        except Exception:
            results.append(dict(store, status='unknown'))
    return results

def main():
    state = dict(updated=datetime.datetime.now(datetime.timezone.utc).isoformat(), sku=SKU, stores=[])
    if not os.getenv('BESTBUY_API_KEY'):
        state.update(health='setup_required', message='Add BESTBUY_API_KEY as a GitHub Actions secret.')
    else:
        try:
            state['stores'] = scan()
            unknown = sum(s['status'] == 'unknown' for s in state['stores'])
            state.update(health='partial' if unknown else 'ok', checked=len(state['stores'])-unknown, total=len(state['stores']))
        except Exception:
            state.update(health='error', message='Best Buy API request failed. Check key, API access and response schema.')
    OUT.write_text(json.dumps(state, indent=2)+'\n')
    print(state['health'])
    return int(state['health'] in ('error', 'partial'))

if __name__ == '__main__':
    raise SystemExit(main())
