import re
import os
html_path = os.path.join('src','cart','templates','cart','checkout.html')
js_path = os.path.join('src','cart','static','cart','js','checkout.js')
with open(html_path, encoding='utf-8') as f:
    html = f.read()
with open(js_path, encoding='utf-8') as f:
    js = f.read()

# gather ids referenced in js via getElementById
ids = set(re.findall(r"getElementById\(['\"]([A-Za-z0-9_\-]+)['\"]\)", js))
# also dataset selectors
ids.update(re.findall(r"document.getElementById\(['\"]([A-Za-z0-9_\-]+)['\"]\)", js))
print('IDs referenced in JS:', sorted(ids))
missing = [i for i in ids if f'id="{i}"' not in html]
print('Missing in HTML:', missing)
# check city-list exists
print('\ncity-list present in HTML?', 'id="city-list"' in html)
# check event listeners existence
print('citySearch input listener present?', 'citySearch.addEventListener(' in js)
print('filterCities function present?', 'function filterCities' in js)
# check where cities array comes from
print('\nloadCdekCities present?', 'async function loadCdekCities' in js)
print('cdekCities assignments count:', js.count('cdekCities'))
# check if cdekCities possibly overwritten: look for "cdekCities ="
print("cdekCities = occurrences:", [m.start() for m in re.finditer(r'cdekCities\s*=\s*', js)])
