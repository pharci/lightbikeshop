function updateCartItems() {
  $.ajax({
    url: '/cart_data/',
    type: 'GET',
    dataType: 'json',
    success: function(response) {
      var items = response.items;

      $('#cart-total-price').html(response.cart.cart_total_price + '₽');
      $('#cart-total-count').html(response.cart.cart_total_count + ' товаров');

      var cartItemsElement = $('#cart-items');
      var isCheckoutBlocked = false; // Флаг блокировки кнопки оформления заказа
      var cartIsEmpty = items.length === 0;

      cartItemsElement.empty();

      items.forEach(function(item) {
        var productBlock = $('<div>').addClass('row p-2 mb-2 align-items-center mx-1 hover-shadow')
          .attr('data-product-id', item.product.id)

        var imageContainer = $('<div>').addClass('col-lg-2 col-4');
        var image = $('<img>').addClass('row-image').attr('src', item.product.imageURL);
        imageContainer.append(image);
        productBlock.append(imageContainer);

        var rowContainer = $('<div>').addClass('row col-lg-10 col-8');
        var nameContainer = $('<div>').addClass('col-lg-6 col-12 mt-0');
        var name = $('<p>').addClass('fw-bold mb-0 text-center').text(item.product.name);
        nameContainer.append(name);
        rowContainer.append(nameContainer);

        var priceContainer = $('<div>').addClass('col-lg-2 col-4');
        var price = $('<p>').addClass('fw-bold mb-0 text-center').attr('id', 'product-total-price-' + item.product.id).text(item.product_total_price.toFixed(0) + '₽');
        priceContainer.append(price);
        rowContainer.append(priceContainer);

        var counterContainer = $('<div>').addClass('col-lg-4 col-8 d-flex mt-0');
        var counter = $('<div>').addClass('counter');
        var decreaseButton = $('<button>').attr('id', 'remove_from_cart-btn').attr('data-product-id', item.product.id).attr('data-stock-count', item.stock_count).text('-');
        var count = $('<span>').addClass('fw-bold').attr('id', 'product-count-' + item.product.id).text(item.quantity + ' шт.');
        var increaseButton = $('<button>').attr('id', 'add-to-cart-btn').attr('data-product-id', item.product.id).attr('data-stock-count', item.stock_count).text('+');

        counter.append(decreaseButton, count, increaseButton);
        counterContainer.append(counter);
        rowContainer.append(counterContainer);

        productBlock.append(rowContainer);
        cartItemsElement.append(productBlock);
      });

      updateCheckoutButton(isCheckoutBlocked || cartIsEmpty); // Обновляем состояние кнопки оформления заказа
      EditCount();
    },
    error: function(xhr, status, error) {
      console.log(error);
    }
  });
}

function updateCheckoutButton(isBlocked, cartIsEmpty) {
  var checkoutBtn = $('#checkout-btn');
  
  if (isBlocked || cartIsEmpty) {
      checkoutBtn.prop('disabled', true);
      checkoutBtn.addClass('disabled').html('Недопустимый заказ');
    } else {
      checkoutBtn.prop('disabled', false);
      checkoutBtn.removeClass('disabled').html('Перейти к оформлению');
    }
}

$(document).ready(function() {
  updateCartItems();
});

function EditCount() {
  var cartItemsElement = $('#cart-items');

  cartItemsElement.on('click', '#add-to-cart-btn, #remove_from_cart-btn', function() {
    var btn = $(this);
    var productId = btn.attr('data-product-id');
    var action = '';

    if (btn.is('#add-to-cart-btn')) {
      action = 'add';
    } else if (btn.is('#remove_from_cart-btn')) {
      action = 'remove';
    }

    var url = '/product_edit/?product_id=' + productId + '&action=' + action;
    var quantityInStock = parseInt(btn.attr('data-stock-count'));

    $.ajax({
      url: url,
      type: 'GET',
      success: function(response) {
        $('.cart-count-text').text(response.cart_total_count);
        $('#product-total-price-' + productId).html(response.product_total_price + '₽');
        $('#product-count-' + productId).html(response.count + ' шт.');
        $('#cart-total-price').html(response.cart_total_price + '₽');
        $('#cart-total-count').html(response.cart_total_count + ' товаров');

        var quantityInCart = response.count;
        var addToCartBtn = $('#add-to-cart-btn[data-product-id="' + productId + '"]');
        addToCartBtn.prop('disabled', quantityInCart >= quantityInStock);

        var productBlock = btn.closest('.hover-shadow');
        var errorText = productBlock.find('#error-text');
        var isCheckoutBlocked = false; // Флаг блокировки кнопки оформления заказа

        if (quantityInCart > quantityInStock) {
          productBlock.addClass('red-shadow')
          productBlock.append(errorText);
        } else {
          productBlock.removeClass('red-shadow')
          errorText.remove();
        }

        if (action === 'remove' && quantityInCart === 0) {
          productBlock.remove();
        }

        var cartItems = $('#cart-items').find('.hover-shadow');
        var cartIsEmpty = cartItems.length === 0; // Проверка на пустую корзину

        cartItems.each(function() {
          var itemQuantity = parseInt($(this).find('.counter span').text().split(' ')[0]);
          var itemStockCount = parseInt($(this).find('.counter button').attr('data-stock-count'));

          if (itemQuantity > itemStockCount) {
            isCheckoutBlocked = true;
            return false; // Прерываем цикл, если найден товар с недопустимым количеством
          }
        });

        updateCheckoutButton(isCheckoutBlocked, cartIsEmpty); // Обновляем состояние кнопки оформления заказа
      },
      error: function() {
        // Обработка ошибок при выполнении запроса
      }
    });
  });
}