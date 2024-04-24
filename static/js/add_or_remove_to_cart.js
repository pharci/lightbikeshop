function updateCartData(response, productId) {
    $('#cart-total-price').text(response.cart_total_price + '₽');
    $('#cart-total-count').text(response.cart_total_count + ' товаров');
    $('.cart-count-text').text(response.cart_total_count);

    var productElement = $('#product-' + productId);

    productElement.find('.product-quantity').text(response.item_quantity + ' шт.');
    productElement.find('.product-total-price').text(response.item_total_price + ' ₽');

}

    // Функция для отправки AJAX-запроса на сервер
function sendAjaxRequest(url, product_sku, successCallback) {
  $.ajax({
    url: url,
    type: 'POST',
    dataType: 'json',
    data: {
            'product_sku': product_sku,
        },
    headers: {
      "X-CSRFToken": getToken('csrftoken')
    },
    success: successCallback,
    error: function(xhr, status, error) {
      console.error(error);
    }
  });
}

// Функция для добавления товара в корзину
function addToCart(product_sku) {
  sendAjaxRequest('/add_to_cart/', product_sku, function(response) {
    updateCartData(response, product_sku);
  });
}

// Функция для удаления товара из корзины
function removeFromCart(product_sku) {
  sendAjaxRequest('/remove_from_cart/', product_sku, function(response) {
    updateCartData(response, product_sku);
  });
}

function updateButtonStyles(product_sku, item_quantity, product_count) {
  var addButton = $('#product-' + product_sku).find('.add-to-cart-btn')
  var deleteButton = $('#product-' + product_sku).find('.remove-from-cart-btn')

  if (item_quantity === 1) {
    deleteButton.prop('disabled', true);
    deleteButton.css('background-color', '#dddfe0');
  } else {
    deleteButton.prop('disabled', false);
    deleteButton.css('background-color', '');
  }

  if (item_quantity === product_count) {
    addButton.prop('disabled', true);
    addButton.css('background-color', '#dddfe0');
  } else {
    addButton.prop('disabled', false);
    addButton.css('background-color', '');
  }
}


$(document).ready(function() {
        var productElements = $('.product');

        productElements.each(function() {
          var product_sku = $(this).data('product-sku');

          sendAjaxRequest('/check_item_count/', product_sku, function(response) {

            updateButtonStyles(product_sku, response.item_quantity, response.product_count)

          });
        });


        // Обработчик события для кнопки "Добавить в корзину"
        $('.add-to-cart-btn').click(function() {

          var product_sku = $(this).data('product-sku');

          sendAjaxRequest('/check_item_count/', product_sku, function(response) {

            if (response.item_quantity < response.product_count) {
              updateButtonStyles(product_sku, response.item_quantity + 1, response.product_count)
              addToCart(product_sku);
            };

          });
        });
 
        // Обработчик события для кнопки "Удалить из корзины"
        $('.remove-from-cart-btn').click(function() {
          var product_sku = $(this).data('product-sku');

          sendAjaxRequest('/check_item_count/', product_sku, function(response) {

            if (response.item_quantity >= 1) {
              updateButtonStyles(product_sku, response.item_quantity - 1, response.product_count)
              removeFromCart(product_sku);
            };

          });
        });
  });