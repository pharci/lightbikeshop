$(document).ready(function() {
    const button = $("#dropdown-button");
    const dropdownContainer = $("#dropdown-container");

    button.click(function() {
      dropdownContainer.slideToggle(1000, function() {
        if (button.text() === "Показать историю заказов") {
          button.text("Скрыть");
        } else {
          button.text("Показать историю заказов");
        }
      });
    });
  });

$(document).ready(function() {
    const overlay = $('#confirmationOverlay');
    const overlayContent = $('.overlay-content');
    const confirmBtn = $('#confirmBtn');
    const cancelBtn = $('#cancelBtn');
    // Show the overlay
    function showOverlay() {
      overlay.fadeIn(200);
    }

    // Hide the overlay
    function hideOverlay() {
      overlay.fadeOut(200);
    }

    // When the user clicks on a button to trigger the confirmation
    $('.cancel_order').click(function() {
      const orderId = $(this).attr('data-order-id');
      $('#confirmBtn').attr('data-order-id', orderId)
      showOverlay();
    });

    // When the user clicks the confirm button
    confirmBtn.click(function() {
      // Get the order ID from the hidden input field

      const orderId = $(this).attr('data-order-id');

      $.ajaxSetup({
      headers: {
        "X-CSRFToken": getToken('csrftoken')
      }
      });

      // Send an AJAX request to delete the order
      $.ajax({
        type: 'POST',
        url: '/delete_order/', // Replace this with your view URL for deleting the order
        data: { order_id: orderId },
        success: function(response) {
          // If the order is successfully deleted, move it to the completed orders section
          $('#dropdown-container').append($('#' + orderId));
          $('#buttom-' + orderId).remove()
        },
        error: function() {
          alert('An error occurred while deleting the order.');
        }
      });

      // After the action is done, hide the overlay
      hideOverlay();
    });

    // When the user clicks the cancel button
    cancelBtn.click(function() {
      hideOverlay();
    });

    // When the user clicks anywhere outside the overlay
    $(document).mouseup(function(e) {
      if (!overlayContent.is(e.target) && overlayContent.has(e.target).length === 0) {
        hideOverlay();
      }
    });
  });