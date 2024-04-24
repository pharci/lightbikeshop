document.addEventListener('DOMContentLoaded', function () {
      const productCards = document.querySelectorAll('.product-card');
      productCards.forEach(card => {
          card.addEventListener('click', function () {
              const url = card.getAttribute('data-url');
              if (url) {
                  window.location.href = url;
              }
          });
      });
  });


var productImageSwiper = new Swiper(".product-image-swiper", {
  slidesPerView: 1,
  centeredSlides: false,
  speed: 500,
  spaceBetween: 0,
  loop: false,
  effect: "slide",
  pagination: {
    el: '.product-image-pagination',
    clickable: true,
    renderBullet: function (index, className) {
        return '<div class="' + className + '"><span class="product-slider-pagination-bullet"></span></div>';
      },
  },
});

var swipers = document.querySelectorAll('.swiper');

swipers.forEach(function (swiper, swiperindex) {
  var paginationBullets = swiper.querySelectorAll('.swiper-pagination-bullet');

  if (window.innerWidth > 768) {
    paginationBullets.forEach(function (bullet, index) {
      bullet.addEventListener('mouseenter', function () {
        productImageSwiper[swiperindex].slideTo(index);
      });
    });
  }
});