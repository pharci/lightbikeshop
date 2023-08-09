window.addEventListener('DOMContentLoaded', function() {
  const registerForm = document.getElementById("register-form");
  const emailInput = document.getElementById("id_email");
  const passwordInput = document.getElementById("id_password1");
  const confirmPasswordInput = document.getElementById("id_password2");
  const registerButton = document.getElementById("register-button");
  const emailError = document.getElementById("email-error");
  const emailInvalidError = document.getElementById("email-invalid-error");
  const passwordWeakError = document.getElementById("password-weak-error");
  const passwordMismatchError = document.getElementById("password-mismatch-error");

  function enableRegisterButton() {
    registerButton.disabled = emailError.style.display === "block" ||
      emailInvalidError.style.display === "block" ||
      passwordWeakError.style.display === "block" ||
      passwordMismatchError.style.display === "block" ||
      !emailInput.value ||
      !passwordInput.value ||
      !confirmPasswordInput.value;
  }

  function checkEmailAvailability() {
    const email = emailInput.value;

    fetch("/check_email_availability/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": getToken('csrftoken')
      },
      body: JSON.stringify({ email })
    })
    .then(response => response.json())
    .then(data => {
      emailError.style.display = data.is_taken ? "block" : "none";
      enableRegisterButton();
    })
    .catch(error => {
      console.error("Error:", error);
    });
  }

  function checkEmailValidity() {
    const email = emailInput.value;
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const isValid = regex.test(email);

    emailInvalidError.style.display = isValid ? "none" : "block";
    enableRegisterButton();
  }

  function checkPasswordStrength() {
    const password = passwordInput.value;
    const regex = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]{8,64}$/;
    const hasSpaces = /\s/;

    if (password.trim() === '' || /^\s+$/.test(password)) {
      passwordWeakError.style.display = "none";
      enableRegisterButton();
      return;
    }

    if (!regex.test(password) || hasSpaces.test(password)) {
      passwordWeakError.style.display = "block";
      enableRegisterButton();
    } else {
      passwordWeakError.style.display = "none";
      enableRegisterButton();
    }
  }

  function checkPasswordMatch() {
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;

    if (password.trim() === '' || /^\s+$/.test(password)) {
      passwordMismatchError.style.display = "none";
      enableRegisterButton();
      return;
    }

    if (password !== confirmPassword) {
      passwordMismatchError.style.display = "block";
      enableRegisterButton();
    } else {
      passwordMismatchError.style.display = "none";
      enableRegisterButton();
    }
  }

  emailInput.addEventListener("input", function() {
    checkEmailAvailability();
    checkEmailValidity();
  });

  passwordInput.addEventListener("input", checkPasswordStrength);

  confirmPasswordInput.addEventListener("input", checkPasswordMatch);

  registerForm.addEventListener("submit", function(event) {
    if (passwordInput.value !== confirmPasswordInput.value) {
      passwordMismatchError.style.display = "block";
      event.preventDefault();
    }
  });
});