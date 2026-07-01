"""Trim large JSON asset files for browser performance."""
import json, os

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      '..', 'frontend', 'src', 'assets', 'data')
ASSETS = os.path.normpath(ASSETS)
print('Assets dir:', ASSETS)

def trim(fname, key, limit, total_key='total'):
    path = os.path.join(ASSETS, fname)
    if not os.path.exists(path):
        print(f'  SKIP {fname} (not found)')
        return
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    # If already wrapped
    if isinstance(data, dict) and key in data:
        items = data[key][:limit]
        data[key] = items
        data[total_key] = len(items)
    elif isinstance(data, list):
        total = len(data)
        items = data[:limit]
        data = {total_key: total, 'page': 1, 'page_size': 25, key: items}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    size = os.path.getsize(path) / 1024
    n = len(data[key]) if isinstance(data, dict) and key in data else len(data)
    print(f'  {fname}: {n} rows, {size:.0f} KB')

trim('applicants.json', 'applicants', 500)
trim('loans.json', 'loans', 500)

# transactions_sample - wrap if needed
path = os.path.join(ASSETS, 'transactions_sample.json')
if os.path.exists(path):
    with open(path, encoding='utf-8') as f: d = json.load(f)
    if isinstance(d, list):
        wrapped = {'total': len(d), 'page': 1, 'page_size': 20, 'transactions': d[:500]}
        with open(path, 'w', encoding='utf-8') as f: json.dump(wrapped, f)
        print(f'  transactions_sample.json: {len(wrapped["transactions"])} rows, {os.path.getsize(path)/1024:.0f} KB')

total = sum(os.path.getsize(os.path.join(ASSETS, f))
            for f in os.listdir(ASSETS) if f.endswith('.json'))
print(f'Total assets: {total/1024/1024:.1f} MB')
