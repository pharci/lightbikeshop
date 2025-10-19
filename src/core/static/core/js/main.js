function getToken(name) {
  var cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    var cookies = document.cookie.split(';');
    for (var i = 0; i < cookies.length; i++) {
      var cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

function getCookie(name) {
  var cookieArr = document.cookie.split(';');
  for (var i = 0; i < cookieArr.length; i++) {
    var cookiePair = cookieArr[i].split('=');
    if (name == cookiePair[0].trim()) {
      return decodeURIComponent(cookiePair[1]);
    }
  }
  return null;
}

var cookies_cart = JSON.parse(getCookie('cookies_cart'))

if (cookies_cart == undefined) {
  cookies_cart = {};
  document.cookie =
      'cookies_cart=' + JSON.stringify(cookies_cart) + ';domain=;path=/'
}


document.addEventListener('DOMContentLoaded', () => {
  const currentUrl = window.location.pathname;
  document.querySelectorAll('.footerbar__btn').forEach(btn => {
    if (btn.getAttribute('href') === currentUrl) {
      btn.classList.add('is-active');
    }
  });
});


(() => {
  const el = document.querySelector('.variantsSwiperRec');
  if (!el) return;
  new Swiper(el, {
    slidesPerView: 'auto',
    spaceBetween: 8,
    speed: 500,
    breakpoints: {768: {spaceBetween: 12}, 1200: {spaceBetween: 16}}
  });
})();



function loadMetrika() {
  if (window.ym) return;
  (function(m, e, t, r, i, k, a) {
    m[i] = m[i] || function() {
      (m[i].a = m[i].a || []).push(arguments)
    };
    m[i].l = 1 * new Date();
    for (var j = 0; j < document.scripts.length; j++) {
      if (document.scripts[j].src === r) return;
    }
    k = e.createElement(t);
    a = e.getElementsByTagName(t)[0];
    k.async = 1;
    k.src = r;
    a.parentNode.insertBefore(k, a);
  })(window, document, 'script', 'https://mc.yandex.ru/metrika/tag.js', 'ym');
  ym(94255695, 'init', {
    clickmap: true,
    trackLinks: true,
    accurateTrackBounce: true,
    webvisor: true
  });
}

(function() {
const KEY = 'cookieConsent.choice.v1';
const CK = 'cookie_consent';
const MAX_AGE = 60 * 60 * 24 * 180;

function getLS() {
  try {
    return localStorage.getItem(KEY) || '';
  } catch (e) {
    return ''
  }
}
function setLS(v) {
  try {
    localStorage.setItem(KEY, v);
  } catch (e) {
  }
}
function getC(n) {
  return document.cookie.split('; ')
             .find(x => x.startsWith(n + '='))
             ?.split('=')[1] ||
      ''
}
function setC(n, v) {
  document.cookie = `${n}=${v}; Max-Age=${MAX_AGE}; Path=/; SameSite=Lax`
}

function apply(choice) {
  document.documentElement.setAttribute('data-consent', choice);
  setLS(choice);
  setC(CK, choice);
  const bar = document.getElementById('cookie-banner');
  if (bar) bar.style.display = 'none';
  if (choice === 'all') loadMetrika();
}

function init() {
  const bar = document.getElementById('cookie-banner');
  if (!bar) return;

  // уже выбранно?
  const saved = getC(CK) || getLS();
  if (saved === 'all' || saved === 'necessary') {
    document.documentElement.setAttribute('data-consent', saved);
    if (saved === 'all') loadMetrika();
    return;
  }

  // показать и навесить обработчики
  bar.style.display = 'flex';
  const accept = document.getElementById('cc-accept');
  const necessary = document.getElementById('cc-necessary');

  if (accept)
    accept.addEventListener('click', function(ev) {
      ev.preventDefault();
      ev.stopPropagation();
      apply('all');
    }, {once: true});

  if (necessary)
    necessary.addEventListener('click', function(ev) {
      ev.preventDefault();
      ev.stopPropagation();
      apply('necessary');
    }, {once: true});
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
})();
