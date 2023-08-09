$('.appearance div:eq(0)').fadeIn(300, function(){
  $(this).next().fadeIn(300, arguments.callee);
});

$(document).ready(function() {
// Обработка кнопки "Добавить в корзину"
  $(document).on('click', '#remove-from-cart-btn, #add-to-cart-btn', function(event) {
    
    var btn = $(event.target);
    var productId = btn.attr('data-product-id');

    if (btn.is('#add-to-cart-btn')) {
        var action = 'add';
    } else if (btn.is('#remove-from-cart-btn')) {
        var action = 'remove';
    }

    var url = '/product_edit/?product_id=' + productId + '&action=' + action;

    $.ajax({
      url: url,
      type: 'GET',
      success: function(response) {
        var quantityInCart = response.count;
        var quantityInStock = response.stock_count;

        $('.cart-count-text').text(response.cart_total_count);

        if (quantityInCart === quantityInStock) {
            $("#add-to-cart-btn").prop('disabled', true);
        } else {
            $("#add-to-cart-btn").prop('disabled', false);
        }

        if (action === 'add') {
            console.log($("#remove-from-cart-btn").length)
            if ($("#remove-from-cart-btn").length === 0) {
                var decreaseButton = $('<button>').attr('id', 'remove-from-cart-btn').attr('data-product-id', productId).text('-').addClass('btn btn-outline-danger shadow-none');
                $(".add-to-cart-btn-box").append(decreaseButton)
            }

            if (quantityInCart > 0) {
                btn.text('В корзине ' + quantityInCart + ' шт.')
                btn.removeClass('btn-outline-dark')
                btn.addClass('btn-outline-success')
        }}

        else if (action === 'remove')
            if (quantityInCart > 0) {
                $("#add-to-cart-btn").text('В корзине ' + quantityInCart + ' шт.')
                $("#add-to-cart-btn").removeClass('btn-outline-dark')
                $("#add-to-cart-btn").addClass('btn-outline-success')
            }
            else if (quantityInCart === 0) {
                $("#add-to-cart-btn").text('Добавить в корзину')
                $("#add-to-cart-btn").removeClass('btn-outline-success')
                $("#add-to-cart-btn").addClass('btn-outline-dark')
                btn.remove();
            }
      }
    });
  });

});


$(document).ready(function() {
    var product_id = $("#product").data("product-id");
    
    $.ajax({
        url: '/product_check_count/',
        type: 'GET',
        data: {
            'product_id': product_id
        },
        success: function(response) {
                var count = response.count;
                var stock_count = response.stock_count;

                if (count >= stock_count) {
                    $("#add-to-cart-btn").prop('disabled', true);
                }
                if (count > 0) {
                    $("#add-to-cart-btn").text('В корзине ' + count + ' шт.')
                    $("#add-to-cart-btn").removeClass('btn-outline-dark')
                    $("#add-to-cart-btn").addClass('btn-outline-success')
                    if ($("#remove-from-cart-btn").length === 0) {
                        var decreaseButton = $('<button>').attr('id', 'remove-from-cart-btn').attr('data-product-id', product_id).text('-').addClass('btn btn-outline-danger shadow-none');
                        $(".add-to-cart-btn-box").append(decreaseButton)
                    }
                }
        },
        error: function(xhr, errmsg, err) {
            console.log(xhr.status + ": " + xhr.responseText);
        }
    });
});