(() => {
  document.querySelectorAll('.infoswiper').forEach(el => {
    const count = el.querySelectorAll('.swiper-slide').length;

    new Swiper(el, {
      slidesPerView: 1,
      loop: count > 2,
      spaceBetween: 8,
      speed: 500,
      breakpoints: {768: {spaceBetween: 12}, 1200: {spaceBetween: 16}},
      autoplay: {delay: 4000, disableOnInteraction: false},
      pagination: {el: '.infoswiper__pagination', clickable: true}
    });
  });
})();

// Бренды
(() => {
  const el = document.querySelector('.brandswiper');
  if (!el) return;
  new Swiper(el, {
    slidesPerView: 'auto',
    spaceBetween: 6,
    speed: 500,
    breakpoints: {768: {spaceBetween: 6}, 1200: {spaceBetween: 12}}
  });
})();


(() => {
  const el = document.querySelector('.variantsSwiperNew');
  if (!el) return;
  new Swiper(el, {
    slidesPerView: 'auto',
    spaceBetween: 6,
    speed: 500,
    breakpoints: {768: {spaceBetween: 6}, 1200: {spaceBetween: 12}}
  });
})();