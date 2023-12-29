window.addEventListener('DOMContentLoaded', function() {
  const userNameInput = document.getElementById("user_name");
  const contactPhoneInput = document.getElementById("contact_phone");
  const deliveryAddressInput = document.getElementById("delivery_address");
  const pickupLocationInput = document.getElementById('pickup_location');
  const deliveryMethodInput = document.getElementById('delivery_method');

  const pickupButton = document.getElementById('pickupButton');
  const deliveryButton = document.getElementById('deliveryButton');
  const checkoutButton = document.getElementById("checkout-button");

  function toggleCheckoutButton() {
    console.log(1)
    if (
      (pickupButton.classList.contains('active') && userNameInput.value !== '' && contactPhoneInput.value !== '' && pickupLocationInput.value !== '') ||
      (deliveryButton.classList.contains('active') && userNameInput.value !== '' && contactPhoneInput.value !== '' && deliveryAddressInput.value !== '' && deliveryMethodInput.value !== '')
    ) {
      checkoutButton.disabled = false;
    } else {
      checkoutButton.disabled = true;
    }
  }

  function toggleFields(receivingMethod) {
    if (receivingMethod === 'pickup') {
      pickupButton.classList.add('active');
      deliveryButton.classList.remove('active');
      document.getElementById('pickupFields').style.display = 'block';
      document.getElementById('deliveryFields').style.display = 'none';
      pickupLocationInput.hidden = false;
      deliveryAddressInput.hidden = true;
      deliveryMethodInput.hidden = true;
      pickupLocationInput.disabled = false;
      deliveryAddressInput.disabled = true;
      deliveryMethodInput.disabled = true;

    } else if (receivingMethod === 'delivery') {
      deliveryButton.classList.add('active');
      pickupButton.classList.remove('active');
      document.getElementById('pickupFields').style.display = 'none';
      document.getElementById('deliveryFields').style.display = 'block';
      pickupLocationInput.hidden = true;
      deliveryAddressInput.hidden = false;
      deliveryMethodInput.hidden = false;
      pickupLocationInput.disabled = true;
      deliveryAddressInput.disabled = false;
      deliveryMethodInput.disabled = false;



    }
    toggleCheckoutButton();
  }

  userNameInput.addEventListener('input', toggleCheckoutButton);
  contactPhoneInput.addEventListener('input', toggleCheckoutButton);
  deliveryAddressInput.addEventListener('input', toggleCheckoutButton);
  pickupLocationInput.addEventListener('change', toggleCheckoutButton);
  deliveryMethodInput.addEventListener('change', toggleCheckoutButton);

  pickupButton.addEventListener('click', function () {
    toggleFields('pickup');
    receivingMethodInput.value = 'pickup';
  });

  deliveryButton.addEventListener('click', function () {
    toggleFields('delivery');
    receivingMethodInput.value = 'delivery';
  });

  // Инициализация состояния кнопки при загрузке страницы
  toggleCheckoutButton();
});