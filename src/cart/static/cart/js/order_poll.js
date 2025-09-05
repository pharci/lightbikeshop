(function() {
const root = document.querySelector('#OrderPage');
const ORDER_ID = root?.dataset.orderId;
if (!ORDER_ID) return;

const KEY = `order:${ORDER_ID}:reloaded`;
if (sessionStorage.getItem(KEY) === '1')
  return;  // уже перезагружались — больше не трогаем

let timer = null, inflight = false, stopped = false;

async function poll() {
  if (stopped || inflight) return;
  inflight = true;
  try {
    const r = await fetch(`/orders/${ORDER_ID}/status`, {cache: 'no-store'});
    if (!r.ok) return;
    const {status} = await r.json();
    if (status === 'paid' || status === 'canceled') {
      stopped = true;
      clearTimeout(timer);
      sessionStorage.setItem(KEY, '1');  // пометили одноразовую перезагрузку
      const url = new URL(location.href);  // cache-bust
      url.searchParams.set('_t', Date.now());
      location.replace(url.toString());
      return;
    }
  } finally {
    inflight = false;
    if (!stopped) timer = setTimeout(poll, 3000);
  }
}

// старт один раз при загрузке/возвращении из bfcache
const start = () => {
  if (!stopped && !timer) poll();
};
start();
window.addEventListener('pageshow', start, {once: true});
window.addEventListener('pagehide', () => {
  stopped = true;
  clearTimeout(timer);
});
})();
