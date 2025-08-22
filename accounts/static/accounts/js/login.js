window.addEventListener('DOMContentLoaded', function() {
  const loginForm = document.getElementById('login-form');
  const emailInput = document.getElementById('id_email');
  const passwordInput = document.getElementById('id_password');
  const loginButton = document.getElementById('login-button');
  const emailError = document.getElementById('email-error');
  const emailInvalidError = document.getElementById('email-invalid-error');

  function enableLoginButton() {
    loginButton.disabled = emailError.style.display === 'block' ||
        emailInvalidError.style.display === 'block' || !emailInput.value ||
        !passwordInput.value;
  }

  function checkEmailAvailability() {
    const email = emailInput.value;

    fetch('/check_email_availability/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getToken('csrftoken')
      },
      body: JSON.stringify({email})
    })
        .then(response => response.json())
        .then(data => {
          emailError.style.display = data.is_taken ? 'none' : 'block';
          enableLoginButton();
        })
        .catch(error => {
          console.error('Error:', error);
        });
  }

  function checkEmailValidity() {
    const email = emailInput.value;
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const isValid = regex.test(email);

    emailInvalidError.style.display = isValid ? 'none' : 'block';
    enableLoginButton();
  }

  emailInput.addEventListener('input', checkEmailAvailability);
  emailInput.addEventListener('input', checkEmailValidity);
});