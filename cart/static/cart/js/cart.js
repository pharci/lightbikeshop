function updateCartData(response, productId) {
    $('#cart-total-price').text(response.cart_total_price + '₽');
    $('#cart-total-count').text(response.cart_total_count + ' товаров');
    $('.cart-count-text').text(response.cart_total_count);

    var productElement = $('#product-' + productId);

    productElement.find('.product-quantity').text(response.item_quantity + ' шт.');
    productElement.find('.product-total-price').text(response.item_total_price + ' ₽');

}

    // Функция для отправки AJAX-запроса на сервер
function sendAjaxRequest(url, product_id, successCallback) {
  $.ajax({
    url: url + product_id + '/',
    type: 'POST',
    dataType: 'json',
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
function addToCart(product_id) {
  sendAjaxRequest('/add_to_cart/', product_id, function(response) {
    updateCartData(response, product_id);
  });
}

// Функция для удаления товара из корзины
function removeFromCart(product_id) {
  sendAjaxRequest('/remove_from_cart/', product_id, function(response) {
    updateCartData(response, product_id);
  });
}

function updateButtonStyles(product_id, item_quantity, product_count) {
  var addButton = $('#product-' + product_id).find('.add-to-cart-btn')
  var deleteButton = $('#product-' + product_id).find('.remove-from-cart-btn')

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
          var product_id = $(this).data('product-id');

          sendAjaxRequest('/check_item_count/', product_id, function(response) {

            updateButtonStyles(product_id, response.item_quantity, response.product_count)

          });
        });


        // Обработчик события для кнопки "Добавить в корзину"
        $('.add-to-cart-btn').click(function() {

          var product_id = $(this).data('product-id');

          sendAjaxRequest('/check_item_count/', product_id, function(response) {

            if (response.item_quantity < response.product_count) {
              updateButtonStyles(product_id, response.item_quantity + 1, response.product_count)
              addToCart(product_id);
            };

          });
        });
 
        // Обработчик события для кнопки "Удалить из корзины"
        $('.remove-from-cart-btn').click(function() {
          var product_id = $(this).data('product-id');

          sendAjaxRequest('/check_item_count/', product_id, function(response) {

            if (response.item_quantity >= 1) {
              updateButtonStyles(product_id, response.item_quantity - 1, response.product_count)
              removeFromCart(product_id);
            };

          });
        });
  });


$(document).ready(function() {
  $('.delete-btn').click(function() {

    currentProductId = $(this).data('product-id');
    var productElement = $('#product-' + currentProductId);
    var deleteBtnImg = productElement.find('.delete-btn img');

    if (deleteBtnImg.hasClass('rotate-reverse')) {
      deleteBtnImg.toggleClass('rotate-reverse');
    }

    deleteBtnImg.toggleClass('rotate');

    $('#confirmDeleteModal').modal('show');
  });

  $('#deleteConfirmBtn').click(function() {

    sendAjaxRequest('/delete_from_cart/', currentProductId, function(response) {
      updateCartData(response, currentProductId);
      $('#product-' + currentProductId).remove();
    });

    $('#confirmDeleteModal').modal('hide');
  });

  $('#confirmDeleteModal').on('hidden.bs.modal', function () {

    var productElement = $('#product-' + currentProductId);
    var deleteBtnImg = productElement.find('.delete-btn img');

    deleteBtnImg.toggleClass('rotate rotate-reverse');

    $('#confirmDeleteModal').modal('hide');
  });
});