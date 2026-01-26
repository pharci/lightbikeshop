
// admin/js/dashboard.js (v2 tolerant)
(function() {
'use strict';

function z(n) {
  return String(n).padStart(2, '0');
}
function fmt(d) {
  return d.getFullYear() + '-' + z(d.getMonth() + 1) + '-' + z(d.getDate());
}
function toDate(s) {
  const [y, m, d] = String(s || '').split('-').map(Number);
  return new Date(y || 1970, (m || 1) - 1, d || 1);
}
function addDays(d, n) {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}
const DAY = 86400000;

function text(node, msg) {
  if (!node) return;
  const p = document.createElement('div');
  p.style.cssText =
      'padding:10px;color:#6b7280;font:13px/1.4 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;';
  p.textContent = msg;
  node.replaceWith(p);
}

function ensureChart(cb) {
  if (window.Chart && typeof window.Chart === 'function') {
    cb();
    return;
  }
  const s = document.createElement('script');
  s.src = 'https://cdn.jsdelivr.net/npm/chart.js';
  s.async = true;
  s.onload = function() {
    cb();
  };
  s.onerror = function() {
    cb(new Error('Chart.js load error'));
  };
  document.head.appendChild(s);
}

function readJSON(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  let s = el.textContent;
  if (typeof s !== 'string') return null;
  s = s.trim();
  if (!s) return [];
  try {
    return JSON.parse(s);
  } catch (e1) {
    try {
      // исправление частых случаев: одинарные кавычки и висячие запятые
      const fixed = s.replace(/'/g, '"').replace(/,\s*([}\]])/g, '$1');
      return JSON.parse(fixed);
    } catch (e2) {
      console.error('Bad JSON in #' + id + ':', s);
      return null;
    }
  }
}

function draw() {
  const canvas = document.getElementById('ordersChart');
  if (!canvas) return;

  const labels = readJSON('ord-labels');
  const counts = readJSON('ord-counts');
  if (labels === null || counts === null) {
    text(canvas, 'Ошибка данных');
    return;
  }

  const L = Array.isArray(labels) ? labels : [];
  const C = (Array.isArray(counts) ? counts : []).map(v => +v || 0);

  if (L.length === 0 || L.length !== C.length) {
    text(canvas, 'Нет данных');
    return;
  }

  const wrap = canvas.closest('.chart-wrap');
  if (wrap && (!wrap.offsetHeight || wrap.offsetHeight < 40))
    wrap.style.height = '220px';

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  if (canvas._chart) canvas._chart.destroy();

  canvas._chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: L,
      datasets: [{
        label: 'Заказы',
        data: C,
        borderColor: '#111111',
        backgroundColor: 'rgba(0,0,0,0.08)',
        pointRadius: 3,
        pointHoverRadius: 4,
        borderWidth: 2,
        tension: 0.3,
        fill: false,
        spanGaps: true
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {display: false},
        tooltip: {mode: 'index', intersect: false}
      },
      scales: {
        x: {grid: {color: 'rgba(0,0,0,0.06)'}, ticks: {maxTicksLimit: 8}},
        y: {
          beginAtZero: true,
          ticks: {precision: 0},
          grid: {color: 'rgba(0,0,0,0.06)'}
        }
      }
    }
  });

  // навигация
  const wrapBox = document.getElementById('orders-summary');
  const btnPrev = document.getElementById('prevDay');
  const btnNext = document.getElementById('nextDay');
  const btnToday = document.getElementById('todayBtn');

  let startStr = (wrapBox?.dataset?.start) || fmt(new Date());
  let endStr = (wrapBox?.dataset?.end) || fmt(new Date());
  const PERIOD = (wrapBox?.dataset?.period || 'custom').toLowerCase();

  function gotoRange(s, e) {
    const params = new URLSearchParams(location.search);
    params.delete('period');
    params.delete('shift');
    params.set('start', s);
    params.set('end', e);
    location.search = params.toString();
  }
  function days(a, b) {
    return Math.round((b - a) / DAY) + 1;
  }
  function shiftWindow(sign) {
    if (PERIOD === 'all') {
      gotoRange(endStr, endStr);
      return;
    }
    let s = toDate(startStr), e = toDate(endStr);
    const len = Math.max(1, days(s, e));
    let ns = addDays(s, sign * len), ne = addDays(e, sign * len);
    const t = toDate(fmt(new Date()));
    if (ne > t) {
      ne = t;
      ns = addDays(t, -(len - 1));
    }
    startStr = fmt(ns);
    endStr = fmt(ne);
    gotoRange(startStr, endStr);
  }
  function syncAll() {
    const dis = PERIOD === 'all';
    if (btnPrev) btnPrev.disabled = dis;
    if (btnToday) btnToday.disabled = dis;
    if (btnNext)
      btnNext.disabled = dis || toDate(endStr) >= toDate(fmt(new Date()));
  }
  syncAll();

  btnPrev && btnPrev.addEventListener('click', () => shiftWindow(-1));
  btnNext && btnNext.addEventListener('click', () => shiftWindow(1));
  btnToday && btnToday.addEventListener('click', () => {
    const t = new Date();
    const len = Math.max(1, days(toDate(startStr), toDate(endStr)));
    gotoRange(fmt(addDays(t, -(len - 1))), fmt(t));
  });
}

function boot() {
  ensureChart(function(err) {
    if (err) {
      const canvas = document.getElementById('ordersChart');
      text(canvas, 'Chart.js недоступен');
      return;
    }
    draw();
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', boot);
} else {
  boot();
}
})();
