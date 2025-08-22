// Баннеры
(() => {
  const el = document.querySelector('.infoswiper');
  if (!el) return;
  new Swiper(el, {
    slidesPerView: 1,
    loop: true,
    spaceBetween: 8,
    speed: 500,
    breakpoints: {768: {spaceBetween: 12}, 1200: {spaceBetween: 16}},
    autoplay: {delay: 4000, disableOnInteraction: false},
    pagination: {el: '.infoswiper__pagination', clickable: true}
  });
})();

// Бренды
(() => {
  const el = document.querySelector('.brandswiper');
  if (!el) return;
  new Swiper(el, {
    slidesPerView: 'auto',
    spaceBetween: 12,
    speed: 500,
    breakpoints: {768: {spaceBetween: 16}, 1200: {spaceBetween: 20}}
  });
})();

// Рекомендуем
(() => {
  const el = document.querySelector('.recswiper');
  if (!el) return;
  new Swiper(el, {
    slidesPerView: 'auto',
    spaceBetween: 8,
    speed: 500,
    breakpoints: {768: {spaceBetween: 12}, 1200: {spaceBetween: 16}}
  });
})();