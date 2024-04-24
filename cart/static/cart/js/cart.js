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