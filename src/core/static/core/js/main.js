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