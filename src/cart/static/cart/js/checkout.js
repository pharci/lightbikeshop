(function() {
// DOM
const cityInput = document.getElementById('city');
const cityCaption = document.getElementById('city-caption');

const openCityModalBtn = document.getElementById('open-city-modal');
const cityModal = document.getElementById('city-modal');
const citySearch = document.getElementById('city-search');
const cityList = document.getElementById('city-list');

const methodGroup = document.getElementById('method-group');
const panelPvz = document.getElementById('panel-pvz');
const panelCourier = document.getElementById('panel-courier');
const deliveryMethod = document.getElementById('delivery_method');
const addressLine = document.getElementById('address_line');
const pvzCode = document.getElementById('pvz_code');
const pvzAddress = document.getElementById('pvz_address');
const picked = document.getElementById('pvz-picked');

const mapWrap =
    document.getElementById('pvz-map-wrap');  // wrapper с классом .collapsible
const changePvzBtn =
    document.getElementById('change-pvz');  // кнопка «Изменить пункт»

// Состояние карты
let map, clusterShop, clusterCdek, lastCity = '';
let citiesLoaded = false;

// ----- Модалка городов -----
openCityModalBtn.addEventListener('click', () => {
  cityModal.style.display = 'flex';
  if (!citiesLoaded) {
    // AJAX подгрузка городов (кэшируй на сервере)
    fetch('/api/pvz/cities/')
        .then(r => r.json())
        .then(data => {
          cityList.innerHTML = '';
          data.forEach(c => {
            const div = document.createElement('div');
            div.className = 'city-item';
            div.dataset.city = c.city;
            div.textContent = c.city;
            cityList.appendChild(div);
          });
          citiesLoaded = true;
          filterCities('');
        })
        .catch(() => {});
  }
  citySearch.value = '';
  filterCities('');
});

cityModal.addEventListener('click', (e) => {
  if (e.target === cityModal) cityModal.style.display = 'none';
});

citySearch.addEventListener('input', e => filterCities(e.target.value));

function filterCities(q) {
  const v = (q || '').trim().toLowerCase();
  [...cityList.children].forEach(el => {
    const show = (el.dataset.city || '').toLowerCase().includes(v);
    el.style.display = show ? '' : 'none';
  });
}

cityList.addEventListener('click', (e) => {
  const item = e.target.closest('.city-item');
  if (!item) return;
  const city = item.dataset.city;
  setCity(city);
  cityModal.style.display = 'none';
  resetPvzSelection();
  if (!panelPvz.hidden) ensureMap();
});

function setCity(city) {
  cityInput.value = city;
  cityCaption.textContent = 'г. ' + city;
  try {
    localStorage.setItem('city', city);
  } catch (e) {
  }

  // сброс выбранного ПВЗ и пересоздание карты
  resetPvzSelection();
  if (!panelPvz.hidden) ensureMap();
}

// ----- Автоподстановка города (геолокация) -----
(function initCity() {
  // 1) уже проставлено в hidden?
  const serverVal = (cityInput.value || '').trim();
  if (serverVal) {
    setCity(serverVal);
    return;
  }

  // 2) сохранённое в localStorage
  const saved = (localStorage.getItem('city') || '').trim();
  if (saved) {
    setCity(saved);
    return;
  }

  // 3) дефолт из разметки
  const fallback =
      (openCityModalBtn.dataset.defaultCity || '').trim() || 'Москва';

  // 4) пробуем гео, при отказе → fallback
  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(pos => {
      const lat = pos.coords.latitude;
      const lon = pos.coords.longitude;
      fetch(`/api/whereami/?lat=${lat}&lon=${lon}`)
          .then(r => r.json())
          .then(data => setCity((data && data.city) ? data.city : fallback))
          .catch(() => setCity(fallback));
    }, () => setCity(fallback), {timeout: 5000, maximumAge: 300000});
  } else {
    setCity(fallback);
  }
})();

// ----- Переключение карточек доставки -----
methodGroup.addEventListener('click', (e) => {
  const label = e.target.closest('.delivery-card');
  if (!label) return;

  // если input disabled — игнор
  const radio = label.querySelector('input[type="radio"]');
  if (radio && radio.disabled) return;

  document.querySelectorAll('.delivery-card')
      .forEach(el => el.classList.remove('delivery-card--active'));
  label.classList.add('delivery-card--active');

  const tgt = label.getAttribute('data-target');
  panelPvz.hidden = tgt !== 'panel-pvz';
  panelCourier.hidden = tgt !== 'panel-courier';

  if (tgt === 'panel-pvz') {
    deliveryMethod.value = 'pvz';
    pvzCode.required = true;
    if (addressLine) addressLine.required = false;
    // если ещё не выбрано ПВЗ — раскрываем карту
    if (!pvzCode.value) {
      expandMap();
      changePvzBtn.hidden = true;
    }
    ensureMap();
  } else {
    deliveryMethod.value = 'courier';
    pvzCode.required = false;
    if (addressLine) addressLine.required = true;
  }
});

// ----- Коллапс/экспанд карты -----
function collapseMap() {
  if (!mapWrap) return;
  if (!mapWrap.classList.contains('is-collapsed')) {
    mapWrap.classList.add('is-collapsed');
  }
  if (changePvzBtn) changePvzBtn.hidden = false;
}

function expandMap() {
  if (!mapWrap) return;
  mapWrap.classList.remove('is-collapsed');
  // подстройка вьюпорта
  setTimeout(() => {
    try {
      if (map && map.container) map.container.fitToViewport();
    } catch (e) {
    }
  }, 220);
}

if (changePvzBtn) {
  changePvzBtn.addEventListener('click', () => {
    expandMap();
  });
}

function resetPvzSelection() {
  pvzCode.value = '';
  pvzAddress.value = '';
  picked.textContent = 'не выбрано';
  if (changePvzBtn)
    changePvzBtn.hidden = true;  // если используешь кнопку «Изменить пункт»
  expandMap && expandMap();  // раскрыть карту, если скрывал
  setShippingAndTotal(null);  // <<< СБРОС СТОИМОСТИ ДОСТАВКИ
}

// ----- Карта и метки -----
function ensureMap() {
  const city = (cityInput.value || '').trim();
  if (!city) return;

  ymaps.ready(() => {
    ymaps.geocode(city, {results: 1}).then(res => {
      const first = res.geoObjects.get(0);
      const center =
          first ? first.geometry.getCoordinates() : [55.751244, 37.618423];

      if (!map) {
        map = new ymaps.Map(
            'pvz-map', {center, zoom: 11, controls: ['zoomControl']});

        clusterShop = new ymaps.Clusterer({preset: 'islands#blueClusterIcons'});
        clusterCdek = new ymaps.Clusterer({preset: 'islands#redClusterIcons'});
        map.geoObjects.add(clusterShop);
        map.geoObjects.add(clusterCdek);
      } else {
        map.setCenter(center, 11);
        clusterShop.removeAll();
        clusterCdek.removeAll();
      }

      loadPoints(city);
    });
  });
}

function createPlacemark(p, preset) {
  // Кастомный balloon
  const BalloonLayout =
      ymaps.templateLayoutFactory.createClass(`<div class="pvz-balloon">
         <div class="pvz-balloon__title">${escapeHtml(p.name || '')}</div>
         <div class="pvz-balloon__address">${escapeHtml(p.address || '')}</div>
         <button type="button" class="pvz-balloon__btn" id="pick-${
          p.provider}-${p.id}">Выбрать</button>
       </div>`);

  const pm = new ymaps.Placemark([p.lat, p.lon], {}, {
    preset: preset,
    balloonContentLayout: BalloonLayout,
    balloonPanelMaxMapArea: 0
  });

  pm.events.add('balloonopen', () => {
    // привязываем обработчик «Выбрать»
    const btn = document.getElementById(`pick-${p.provider}-${p.id}`);
    if (btn) btn.onclick = () => pickPoint(p);
  });

  return pm;
}

function pickPoint(p) {
  pvzCode.value = `${p.provider}: ${p.id}`;
  pvzAddress.value = p.address || '';
  picked.textContent = p.address || p.name || 'выбрано';
  collapseMap();

  // только для СДЭК — считаем доставку склад-склад
  if (p.provider === 'cdek') {
    const body = new URLSearchParams({
      pvz_code: p.id,
      to_city_code: p.city_code ? String(p.city_code) : '',
    });

    fetch('/api/cdek/price/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body
    })
        .then(r => r.json())
        .then(data => {
          if (data.ok && typeof data.price === 'number') {
            setShippingAndTotal(data.price);
            // можешь также показать срок: data.period_min–data.period_max
          } else {
            setShippingAndTotal(null);  // прочерк
            // при желании: показать алерт
          }
        })
        .catch(() => setShippingAndTotal(null));
  } else {
    // свои ПВЗ — своя логика цены, либо 0
    setShippingAndTotal(0);
  }
}

function setShippingAndTotal(price) {
  const shipEl = document.getElementById('summary-shipping');
  const totalEl = document.getElementById('summary-total');
  const subEl = document.getElementById('summary-subtotal');
  const discEl =
      document.getElementById('summary-discount');  // может отсутствовать

  const subtotal = parseMoney(subEl?.textContent);
  const discount = parseMoney(discEl?.textContent);  // может быть с минусом
  const shipping = (price == null) ? 0 : Number(price);

  // UI доставка
  shipEl.textContent = (price == null) ? '—' : formatMoney(shipping) + ' ₽';

  // Итого = subtotal - |discount| + shipping
  const total = subtotal - Math.abs(discount) + shipping;
  totalEl.textContent = formatMoney(total) + ' ₽';
}

function parseMoney(txt) {
  if (!txt) return 0;
  // удалить пробелы, ₽, заменить запятые
  const s = String(txt).replace(/\s|₽/g, '').replace(',', '.');
  const n = Number(s);
  return isFinite(n) ? n : 0;
}

function formatMoney(n) {
  return new Intl
      .NumberFormat(
          'ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2})
      .format(n || 0);
}



function loadPoints(city) {
  // Наши ПВЗ
  fetch(`/api/pvz/shop/`)
      .then(r => r.json())
      .then(points => {
        clusterShop.removeAll();
        const placemarks =
            points.filter(v => isFinite(v.lat) && isFinite(v.lon))
                .map(p => createPlacemark(p, 'islands#blueIcon'));
        clusterShop.add(placemarks);
      })
      .catch(() => {});

  // СДЭК ПВЗ
  fetch(`/api/pvz/cdek/?city=${encodeURIComponent(city)}`)
      .then(r => r.json())
      .then(points => {
        clusterCdek.removeAll();
        const placemarks =
            points.filter(v => isFinite(v.lat) && isFinite(v.lon))
                .map(p => createPlacemark(p, 'islands#redIcon'));
        clusterCdek.add(placemarks);
      })
      .catch(() => {});
}

// ----- Утилиты -----
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, ch => ({
                                 '&': '&amp;',
                                 '<': '&lt;',
                                 '>': '&gt;',
                                 '"': '&quot;',
                                 '\'': '&#39;'
                               }[ch]));
}

// Если стартуем уже на «Самовывоз» — сразу рисуем карту
const radioPvz = document.getElementById('dg_pvz');
if (radioPvz && radioPvz.checked && !panelPvz.hidden) ensureMap();
})();