window.addEventListener('DOMContentLoaded', function() {
  const Form = document.getElementById("code-form");
  const codeInput = document.getElementById("id_code");
  const codeValidityError = document.getElementById("code-validity-error");
  const Button = document.getElementById("button");

  function enableButton() {
    Button.disabled = !isValidCode(codeInput.value);
  }

  function isValidCode(code) {
    const regex = /^\d{6}$/;
    return regex.test(code);
  }

  function checkCodeValidity() {
    const code = codeInput.value;

    codeValidityError.style.display = isValidCode(code) ? "none" : "block";
    enableButton();
  }

  codeInput.addEventListener("input", checkCodeValidity);

  Form.addEventListener("submit", function(event) {
    if (!isValidCode(codeInput.value)) {
      codeValidityError.style.display = "block";
      event.preventDefault();
    }
  });
});