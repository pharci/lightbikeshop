document.addEventListener('DOMContentLoaded', function () {
    var swipers = document.querySelectorAll('.product-image-swiper');
    var wishlist_btns = document.querySelectorAll('.add-to-wishlist');
    
    updateWishlistBtns(wishlist_btns)
    updateSwipers(swipers);
    updateCards();
});

//Цифра количества товаров
function formatProductCount(value) {
    value = parseInt(value);
    if (isNaN(value)) {
        return "Неверное значение";
    }
    let lastTwoDigits = value % 100;
    if (10 <= lastTwoDigits && lastTwoDigits <= 20) {
        return `${value} товаров`;
    }
    let lastDigit = value % 10;
    if (lastDigit === 1) {
        return `${value} товар`;
    }
    if (2 <= lastDigit && lastDigit <= 4) {
        return `${value} товара`;
    }
    return `${value} товаров`;
}


//Управление добавлением в корзину
$(document).ready(function() {
    function sendAjaxRequest(url, variant_id, callback) {
        $.ajax({
            url: url,
            type: 'POST',
            dataType: 'json',
            data: {
                'variant_id': variant_id,
                'quantity': 1,
            },
            headers: {
                "X-CSRFToken": getToken('csrftoken') 
            },
            success: function(response) {
                if (callback) {
                    callback(response.quantity);
                }
            },
            error: function(xhr, status, error) {
                console.error(error);
            }
        });
    }
    
    $('.add-to-cart-btn').on('click', function() {
        sendAjaxRequest('/cart/add_to_cart/', $(this).data('product-id'))
    });

    $('.add-to-cart-btn-increase').on('click', function() {
        var productId = $(this).data('product-id');
        sendAjaxRequest('/cart/add_to_cart/', productId, function(quantity) {
            $('#product-quantity-' + productId).text(quantity);
        });
    });
    
    $('.add-to-cart-btn-decrease').on('click', function() {
        var productId = $(this).data('product-id');
        sendAjaxRequest('/cart/remove_from_cart/', productId, function(quantity) {
            $('#product-quantity-' + productId).text(quantity);
        });
    });
});


//Проверка количества товаров в списке
function checkRemainingItems(data) {
    const container = document.querySelector('.products-container');
    let message = document.querySelector('.notfound-products-message');

    if (data.remaining_items <= 0) {
        if (!message) {
            message = document.createElement('div');
            message.className = 'notfound-products-message';
            message.textContent = 'Товаров с такими фильтрами не найдено';
            container.appendChild(message);
        }
        message.style.display = 'block';
    } else {
        if (message) {
            message.style.display = 'none';
        }
    }
}

//Обновление ссылок на страницы товаров
function updateCards() {
    const productCards = document.querySelectorAll('.product-card-title, .product-image-swiper');
    productCards.forEach(card => {
        card.addEventListener('click', function () {
            const url = card.getAttribute('data-url');
            if (url) {
                window.location.href = url;
            }
        });
    });
  }

//Обновление свайперов
function updateSwipers(swipers) {
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

  swipers.forEach(function (swiper, swiperindex) {
    var paginationBullets = swiper.querySelectorAll('.swiper-pagination-bullet');
    if (window.innerWidth > 768) {
      paginationBullets.forEach(function (bullet, index) {
        bullet.addEventListener('mouseenter', function () {
            if (!Array.isArray(productImageSwiper)) { productImageSwiper = [productImageSwiper]; }
            productImageSwiper[swiperindex].slideTo(index);
        });
      });
    }
  });
}


//обновление кнопок избранного
function updateWishlistBtns(btns) {
    btns.forEach(item => {
        item.addEventListener('click', function() {
            const variantId = this.dataset.variantId;
            const url = `/add_to_wishlist/${variantId}/`;
            fetch(url, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest', 
                },
            })
            .then(response => response.json())
            .then(data => {
                if (data.added) {
                    this.innerHTML = `<img src="/static/images/trueheart.png" role="link" width="20" height="20" class="d-flex">`;
                } else {
                    this.innerHTML = `<img src="/static/images/heart.png" role="link" width="20" height="20" class="d-flex">`;
                }
            })
            .catch(error => console.error('Error:', error));
        });
    });
}



//Управление списком товаров
$(document).ready(function() {
    //обновление интерфейса
    function updateUI(data, formData, page, append) {

        $('.variants-count').text(formatProductCount(data.total_items))

        let button = $('#load-more');
        button.data('page', page);

        const newUrl = window.location.pathname + '?' + formData;
        window.history.pushState({ path: newUrl }, '', newUrl);

        if (append) {
            $('.products-list').append(data.products_html);
        } else {
            $('.products-list').html(data.products_html);
            console.log($('.products-list').html(data.products_html))
        }

        if (data.is_last_page) {
            button.hide();
        } else {
            button.text('Показать еще ' + data.remaining_items);
            button.show()
        }

        pagination = $('.pagination-products-block').html(data.pagination_html);

        if (data.per_page > data.total_items) {
            pagination.hide()
        } else {
            pagination.show()
        }

        checkRemainingItems(data)

        var swipers = document.querySelectorAll('.swiper');
        var wishlist_btns = document.querySelectorAll('.add-to-wishlist');
        updateWishlistBtns(wishlist_btns)
        updateSwipers(swipers);
        updateCards();
    }


    function makeAjaxCall(formData, page, append) {
        $.ajax({
            url: window.location.pathname,
            type: 'GET',
            data: formData,
            dataType: 'json',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            success: function(data) {
                updateUI(data, formData, page, append);
            },
            error: function(error) {
                console.log('Error:', error);
            }
        });
    }

    // Обработчик для кнопки "Показать еще"
    $('.pagination-products-block').on('click', '#load-more', function() {
        let formData = $('#product-filter-form').serialize();
        let page = parseInt($(this).data('page')) + 1;

        let sortValue = $('.sort-option.selected').attr('data-value');

        formData += '&sort=' + sortValue + '&page=' + page.toString()

        makeAjaxCall(formData, parseInt(page) , true)
    });

    // Обработчик для пагинации
    $('.pagination-products-block').on('click', 'button', function() {
        let page = $(this).data('page');
        let formData = $('#product-filter-form').serialize();
        let sortValue = $('.sort-option.selected').attr('data-value');

        formData += '&sort=' + sortValue + '&page=' + page;

        makeAjaxCall(formData, parseInt(page), false);
    });
    
    //сортировка
    $('#sortOptions').on('click', '.sort-option', function() {
        const sortValue = $(this).attr('data-value');
        $('#sortOptions .sort-option.selected').removeClass('selected');
        $(this).addClass('selected');

        $('#sortSelectTrigger span').text($(this).text());

        let formData = $('#product-filter-form').serialize() + '&sort=' + sortValue + '&page=1';
        
        makeAjaxCall(formData, 1, false);
    });

    // Обработчик изменений фильтров
    $('.checkbox-input-filter').on('change', function() {
        var attrName = $(this).attr('name'); 
        var value = $(this).val();
        var currentUrl = new URL(window.location.href);
        var searchParams = currentUrl.searchParams;
    
        if (this.checked) {
            searchParams.set(attrName, value);
        } else {
            searchParams.delete(attrName);
        }
    
        currentUrl.search = searchParams.toString();
        window.history.pushState({path: currentUrl.href}, '', currentUrl.href);
        let formData = $('#product-filter-form').serialize();
        let sortValue = $('.sort-option.selected').attr('data-value');
        formData += '&sort=' + sortValue + '&page=1'
    
        makeAjaxCall(formData, 1, false)
    });

    //сброс фильтров
    $('#reset-filters').on('click', function() {
        $('#product-filter-form').find('input[type=checkbox], input[type=text]').prop('checked', false);

        var currentUrl = new URL(window.location.href);
        var baseUrl = currentUrl.pathname; 
        window.history.pushState({path: baseUrl}, '', baseUrl);
        let formData = $('#product-filter-form').serialize();

        let sortValue = $('.sort-option.selected').attr('data-value');
        formData += '&sort=' + sortValue + '&page=1'

        makeAjaxCall(formData, 1, false)
    });
});