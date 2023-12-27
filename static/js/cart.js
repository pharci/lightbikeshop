$(document).ready(function() {
    // Функция для обновления данных корзины
    function updateCartData(response, productId) {
        $('#cart-total-price').text(response.cart_total_price + '₽');
        $('#cart-total-count').text(response.cart_total_count + ' товаров');
        $('.cart-count-text').text(response.cart_total_count);

        var productElement = $('#product-' + productId);

        productElement.find('.product-quantity').text(response.item_quantity + ' шт.');
        productElement.find('.product-total-price').text(response.item_total_price + ' ₽');

    }

    // Обработчик события для кнопки "Добавить в корзину"
    $('.add-to-cart-btn').click(function() {
      var product_id = $(this).data('product-id');

      // Отправляем AJAX-запрос на сервер
      $.ajax({
        url: '/add_to_cart/' + product_id + '/',
        type: 'POST',
        dataType: 'json',
        headers: {
          "X-CSRFToken": getToken('csrftoken')
        },
        success: function(response) {
          // Обновляем данные корзины
          updateCartData(response, product_id);
        },
        error: function(xhr, status, error) {
          console.error(error);
        }
      });
    });

    // Обработчик события для кнопки "Удалить из корзины"
    $('.remove-from-cart-btn').click(function() {
      var product_id = $(this).data('product-id');

      // Отправляем AJAX-запрос на сервер
      $.ajax({
        url: '/remove_from_cart/' + product_id + '/',
        type: 'POST',
        dataType: 'json',
        headers: {
          "X-CSRFToken": getToken('csrftoken')
        },
        success: function(response) {
          // Обновляем данные корзины
          updateCartData(response, product_id);
        },
        error: function(xhr, status, error) {
          console.error(error);
        }
      });
    });
  });