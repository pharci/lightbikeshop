(function() {
const cityInput = document.getElementById('city');
if (!cityInput) return;

// создать/найти контейнер dropdown
let dd = document.querySelector('.suggest__dropdown');
if (!dd) {
  dd = document.createElement('div');
  dd.className = 'suggest__dropdown';
  Object.assign(dd.style, {
    position: 'absolute',
    left: 0,
    right: 0,
    top: '100%',
    zIndex: 10,
    display: 'none'
  });
  const wrap = cityInput.parentElement;
  if (wrap && getComputedStyle(wrap).position === 'static')
    wrap.style.position = 'relative';
  wrap?.appendChild(dd);
}

// a11y
dd.setAttribute('role', 'listbox');
cityInput.setAttribute('role', 'combobox');
cityInput.setAttribute('aria-autocomplete', 'list');
cityInput.setAttribute('aria-expanded', 'false');
cityInput.setAttribute('aria-controls', 'city-suggest-list');
dd.id = 'city-suggest-list';

// state
let aborter = null, activeIdx = -1, itemsState = [];
const cache = new Map();

// utils
const debounce = (fn, ms) => {
  let t;
  return (...a) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...a), ms);
  };
};
const esc = s => s.replace(
    /[&<>"]/g,
    m => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[m]));

function clearDD() {
  dd.innerHTML = '';
  dd.style.display = 'none';
  cityInput.setAttribute('aria-expanded', 'false');
  activeIdx = -1;
  itemsState = [];
}

function render(items, q) {
  dd.innerHTML = '';
  itemsState = items;
  activeIdx = -1;
  const rx = q ?
      new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'i') :
      null;
  items.forEach((it, i) => {
    const el = document.createElement('div');
    el.className = 'suggest__item';
    el.setAttribute('role', 'option');
    el.dataset.name = it.name;
    const nameHTML =
        rx ? esc(it.name).replace(rx, '<mark>$1</mark>') : esc(it.name);
    const regionHTML = it.region ?
        `, <span class="muted region">${esc(it.region)}</span>` :
        '';
    el.innerHTML = `${nameHTML}${regionHTML}`;
    el.addEventListener('pointerdown', e => {
      e.preventDefault();
      choose(i);
    });
    dd.appendChild(el);
  });
  dd.style.display = items.length ? 'block' : 'none';
  cityInput.setAttribute('aria-expanded', String(!!items.length));
}

function choose(idx) {
  const it = itemsState[idx];
  if (!it) return;
  cityInput.value = it.name;
  clearDD();
  window.afterCitySelected?.(it.name);
}

function moveActive(dir) {
  if (!itemsState.length) return;
  activeIdx = (activeIdx + dir + itemsState.length) % itemsState.length;
  [...dd.children].forEach((el, i) => {
    el.classList.toggle('active', i === activeIdx);
    if (i === activeIdx) el.scrollIntoView({block: 'nearest'});
  });
}

async function fetchSuggest(q) {
  const key = q.toLowerCase();
  if (cache.has(key)) return cache.get(key);
  aborter?.abort();
  aborter = new AbortController();
  const url = `/api/city-suggest/?q=${encodeURIComponent(q)}`;
  const p = fetch(url, {signal: aborter.signal, credentials: 'same-origin'})
                .then(r => r.ok ? r.json() : Promise.reject(r.status))
                .then(j => (j.items || []).slice(0, 20))
                .catch(() => []);
  cache.set(key, p);
  return p;
}

const suggest = debounce(async () => {
  const q = cityInput.value.trim();
  if (!q) return clearDD();
  const items = await fetchSuggest(q);
  if (q !== cityInput.value.trim()) return;  // устаревший ответ
  render(items, q);
}, 200);

cityInput.addEventListener('input', suggest);
cityInput.addEventListener('keydown', e => {
  if (dd.style.display !== 'block') return;
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    moveActive(1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    moveActive(-1);
  } else if (e.key === 'Enter') {
    if (activeIdx >= 0) {
      e.preventDefault();
      choose(activeIdx);
    }
  } else if (e.key === 'Escape') {
    clearDD();
  }
});
document.addEventListener('pointerdown', e => {
  if (!dd.contains(e.target) && e.target !== cityInput) clearDD();
});

// дефолт из data-атрибута и гео
(async () => {
  const def = (cityInput.dataset.defaultCity || '').trim();
  if (def && !cityInput.value) {
    cityInput.value = def;
    window.afterCitySelected?.(def);
  }
  const secure = location.protocol === 'https:' ||
      ['localhost', '127.0.0.1', '0.0.0.0'].includes(location.hostname);
  if (!secure || !('geolocation' in navigator)) return;

  // быстрая гео с общим таймаутом
  const pos = await new Promise(resolve => {
    let done = false;
    const finish = p => {
      if (done) return;
      done = true;
      resolve(p);
    };
    const overall = setTimeout(() => finish(null), 8000);
    navigator.geolocation.getCurrentPosition(
        p => {
          clearTimeout(overall);
          finish(p);
        },
        () => {
          clearTimeout(overall);
          finish(null);
        },
        {enableHighAccuracy: false, timeout: 3000, maximumAge: 15 * 60 * 1000});
  });
  if (!pos || cityInput.value) return;
  try {
    const {latitude: lat, longitude: lon} = pos.coords;
    const r = await fetch(
        `/api/whereami/?lat=${encodeURIComponent(lat)}&lon=${
            encodeURIComponent(lon)}`,
        {credentials: 'same-origin'});
    if (!r.ok) return;
    const {city} = await r.json();
    if (city && !cityInput.value) {
      cityInput.value = city;
      window.afterCitySelected?.(city);
    }
  } catch {
  }
})();
})();
