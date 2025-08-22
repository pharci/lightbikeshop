(function() {
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

// элементы
const dgPickup = $('#dg_pickup');
const dgPvz = $('#dg_pvz');
const pickupPanel = $('#panel-pickup');
const pvzPanel = $('#panel-pvz');
const pickupTiles = $('#pickup-tiles');
const pickupHidden = $('#pickup_location');
const pickupEmpty = $('#pickup-empty');
const methodInput = $('#delivery_method');
const pvzBlock = $('#pvz-cdek-block');
const pvzPicked = $('#pvz-picked');
const pvzAddrInput = $('#pvz_address');
const pvzCodeInput = $('#pvz_code');

// утилиты
const fetchJSON = async (url) => {
  const res =
      await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
  if (!res.ok) throw new Error('Network');
  return res.json();
};
const truncate = (s, n) =>
    !s ? s : (s.length > n ? s.slice(0, n - 1) + '…' : s);

// панели
function showPanel(el) {
  if (el) el.hidden = false;
}
function hidePanel(el) {
  if (el) el.hidden = true;
}
function disableRequired(root) {
  root?.querySelectorAll('[required]')?.forEach(i => {
    i._wasReq = true;
    i.required = false;
  });
}
function restoreRequired(root) {
  root?.querySelectorAll('[name]')?.forEach(i => {
    if (i._wasReq) i.required = true;
  });
}

// переключатели
$$('input[name="delivery_group"]').forEach(r => {
  r.addEventListener('change', () => {
    hidePanel(pickupPanel);
    hidePanel(pvzPanel);
    disableRequired(pickupPanel);
    disableRequired(pvzPanel);
    if (r.value === 'pickup') {
      showPanel(pickupPanel);
      restoreRequired(pickupPanel);
      methodInput.value = 'pickup_store';
    } else if (r.value === 'pvz') {
      showPanel(pvzPanel);
      pvzBlock.hidden = false;
      methodInput.value = '';
    }
  });
});

// плитки самовывоза
function renderPickupTiles(items) {
  pickupTiles.innerHTML = '';
  pickupHidden.value = '';
  const cardPickupDesc =
      dgPickup.closest('label').querySelector('.delivery-card__desc');
  if (!items.length) {
    pickupEmpty.hidden = false;
    cardPickupDesc.textContent = 'из магазина';
    return;
  }
  pickupEmpty.hidden = true;
  items.forEach(p => {
    const card = document.createElement('label');
    card.className = 'delivery-card';
    card.innerHTML = `
        <input type="radio" name="pickup_point">
        <span class="delivery-card__title">${p.title}</span>
        <span class="delivery-card__desc">${p.address}</span>
        ${
        p.schedule ? `<span class="delivery-card__meta">${p.schedule}</span>` :
                     ''}`;
    const input = card.querySelector('input');
    input.addEventListener('change', () => {
      if (input.checked) {
        pickupHidden.value = `${p.title}, ${p.address}`;
        methodInput.value = 'pickup_store';
        cardPickupDesc.textContent = p.title;
        dgPickup.checked = true;
        showPanel(pickupPanel);
      }
    });
    pickupTiles.appendChild(card);
  });
}

// CDEK
const openBtn = $('#open-pvz'), closeBtn = $('#pvz-close');
const modal = $('#pvz-modal');
function loadWidget(cb) {
  if (window.CDEKWidget) return cb();
  const s = document.createElement('script');
  s.src = 'https://cdn.jsdelivr.net/npm/@cdek-it/widget@3';
  s.onload = cb;
  document.body.appendChild(s);
}
function openCDEK() {
  modal.style.display = 'block';
  loadWidget(() => {
    new window.CDEKWidget({
      from: 'Москва',
      root: 'cdek-map',
      apiKey: 'ae068af9-edb0-413f-bfc5-2e6ce196122d',
      servicePath: '/api/cdek-service/',
      defaultLocation: window.cdekDefaultLocation || 'Москва',
      onChoose: (type, tariff, address) => {
        const addr = address?.address || address?.PVZ?.Address || '';
        const code = address?.code || address?.PVZ?.Code || '';
        onPvzChosen({code, address: addr});
        const cardPvzDesc =
            dgPvz.closest('label').querySelector('.delivery-card__desc');
        cardPvzDesc.textContent = addr ? truncate(addr, 46) : 'СДЭК';
        modal.style.display = 'none';
        dgPvz.checked = true;
        showPanel(pvzPanel);
      },
    });
  });
}
openBtn?.addEventListener('click', openCDEK);
closeBtn?.addEventListener('click', () => modal.style.display = 'none');

// выбор ПВЗ
function onPvzChosen({code, address}) {
  if (pvzCodeInput) pvzCodeInput.value = code || '';
  if (pvzAddrInput) pvzAddrInput.value = address || '';
  if (pvzPicked) pvzPicked.textContent = address || code || 'выбрано';
  if (dgPvz) dgPvz.checked = true;
  if (methodInput) methodInput.value = 'pickup_pvz';
}
window.onPvzChosen = onPvzChosen;

// публичный хук: вызывается из city.js
async function afterCitySelected(name) {
  window.cdekDefaultLocation = name || 'Москва';
  try {
    const data =
        await fetchJSON(`/api/pickup-points/?city=${encodeURIComponent(name)}`);
    const items = data.items || [];
    renderPickupTiles(items);
    dgPickup.closest('label').style.display = items.length ? '' : 'none';
    if (!items.length && dgPickup.checked) {
      dgPickup.checked = false;
      hidePanel(pickupPanel);
      pickupHidden.value = '';
      methodInput.value = '';
    }
  } catch {
    renderPickupTiles([]);
    dgPickup.closest('label').style.display = 'none';
  }
  dgPvz.closest('label').style.display = name ? '' : 'none';
  if (dgPvz.checked) showPanel(pvzPanel);
}
window.afterCitySelected = afterCitySelected;

// страховка перед сабмитом
const form = $('#checkout-form');
form?.addEventListener('submit', () => {
  const pvzCode = pvzCodeInput?.value?.trim();
  const pvzAddr = pvzAddrInput?.value?.trim();
  const hasPvz = !!(pvzCode || pvzAddr);
  const hasPickup = !!pickupHidden?.value?.trim();
  if (hasPvz) {
    if (dgPvz) dgPvz.checked = true;
    if (methodInput) methodInput.value = 'pickup_pvz';
  } else if (hasPickup) {
    if (dgPickup) dgPickup.checked = true;
    if (methodInput) methodInput.value = 'pickup_store';
  }
});
})();