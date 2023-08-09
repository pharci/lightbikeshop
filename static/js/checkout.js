function toggleFields(deliveryMethod) {
        var pickupButton = document.getElementById('pickupButton');
        var deliveryButton = document.getElementById('deliveryButton');
        var deliveryFields = document.getElementById('deliveryFields');
        var deliveryMethodInput = document.getElementById('deliveryMethodInput');
        
        if (deliveryMethod === 'pickup') {
            pickupButton.classList.add('active');
            deliveryButton.classList.remove('active');
            deliveryFields.style.display = 'none';
            deliveryMethodInput.value = 'pickup';
        } else if (deliveryMethod === 'delivery') {
            pickupButton.classList.remove('active');
            deliveryButton.classList.add('active');
            deliveryFields.style.display = 'block';
            deliveryMethodInput.value = 'delivery';
        }
    }


window.addEventListener('DOMContentLoaded', function() {
  const nameInput = document.getElementById("name");
  const middleNameInput = document.getElementById("middle_name");
  const numberInput = document.getElementById("number");
  const addressInput = document.getElementById("address");
  const cityInput = document.getElementById("city");
  const zip_codeInput = document.getElementById("zip_code");
  const delivery_valueInput = document.getElementById("delivery_value");
  const deliveryMethodInput = document.getElementById('deliveryMethodInput');
  const checkoutButton = document.getElementById("checkout-button");
  const pickupButton = document.getElementById('pickupButton');
  const deliveryButton = document.getElementById('deliveryButton');

  function enableCheckoutButton() {
    let isFormValid = nameInput.value.trim() !== "" &&
                      middleNameInput.value.trim() !== "" &&
                      numberInput.value.trim() !== "";

    if (deliveryMethodInput.value === 'pickup') {
      // No additional checks needed for pickup
    } else if (deliveryMethodInput.value === 'delivery') {
      isFormValid = isFormValid &&
                    addressInput.value.trim() !== "" &&
                    cityInput.value.trim() !== "" &&
                    zip_codeInput.value.trim() !== "" &&
                    delivery_valueInput.value.trim() !== "";
    }

    checkoutButton.disabled = !isFormValid;
  }

  enableCheckoutButton();

  pickupButton.addEventListener("click", enableCheckoutButton);
  deliveryButton.addEventListener("click", enableCheckoutButton);
  nameInput.addEventListener("input", enableCheckoutButton);
  middleNameInput.addEventListener("input", enableCheckoutButton);
  numberInput.addEventListener("input", enableCheckoutButton);
  addressInput.addEventListener("input", enableCheckoutButton);
  cityInput.addEventListener("input", enableCheckoutButton);
  zip_codeInput.addEventListener("input", enableCheckoutButton);
  delivery_valueInput.addEventListener("input", enableCheckoutButton);
});