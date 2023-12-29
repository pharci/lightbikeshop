var infoswiper = new Swiper(".infoswiper", {
  breakpoints: {
  991: {
    slidesPerView: 2,
  },
  576: {
    slidesPerView: 1,
  },
},
  centeredSlides: true,
  spaceBetween: 30,
  pagination: {
    el: ".infoswiper-pagination",
    clickable: true,
  },
  loop: true,
  autoplay: {
    delay: 3000,
  },
  speed: 1000,
  effect: "slide",
});

var brandswiper = new Swiper(".brendswiper", {
  slidesPerView: 4,
  breakpoints: {
  991: {
    spaceBetween: 30,
    slidesPerView: 7,
  },
  576: {
    spaceBetween: 25,
    slidesPerView: 4,
  },
},
  centeredSlides: false,
  spaceBetween: 15,
  loop: false,
  autoplay: {
    delay: 3500,
  },
  speed: 1000,
  effect: "slide",
});

var recswiper = new Swiper(".recswiper", {
  slidesPerView: 2,
  breakpoints: {
  991: {
    spaceBetween: 30,
    slidesPerView: 5,
  },
  576: {
    spaceBetween: 25,
    slidesPerView: 2,
  },
},
  centeredSlides: false,
  spaceBetween: 25,
  loop: false,
  speed: 1000,
  effect: "slide",
});



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