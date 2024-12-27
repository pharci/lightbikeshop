document.addEventListener('DOMContentLoaded', function() {
    var bullets = [];

    imagesData.forEach(function(imageUrl) {
        bullets.push(`<div class="swiper-pagination-bullet" tabindex="0" aria-current="true"><img class="product-mini-image" src=${imageUrl}></span></div>`);
    });

    var productDetailImageSwiper = new Swiper(".product-detail-image-swiper", {
        slidesPerView: 1,
        centeredSlides: false,
        spaceBetween: 20,
        loop: false,
        effect: "slide",
        navigation: {
            nextEl: '.swiper-button-next',
            prevEl: '.swiper-button-prev',
        },
        pagination: {
            el: '.swiper-pagination',
            clickable: true,
            renderBullet: function (index, className) { 
                return bullets[index];
            },
        },
    });
});