window.addEventListener('DOMContentLoaded', function() {
  const recoveryPasswordsForm = document.getElementById("recovery-passwords-form");
  const passwordInput = document.getElementById("id_password1");
  const confirmPasswordInput = document.getElementById("id_password2");
  const recoveryInputButton = document.getElementById("recovery-input-button");
  const passwordWeakError = document.getElementById("password-weak-error");
  const passwordMismatchError = document.getElementById("password-mismatch-error");

  function enableRecoveryPasswordsButton() {
    recoveryInputButton.disabled = passwordWeakError.style.display === "block" ||
      passwordMismatchError.style.display === "block" ||
      !passwordInput.value ||
      !confirmPasswordInput.value;
  }

  function checkPasswordStrength() {
    const password = passwordInput.value;
    const regex = /^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]{8,64}$/;
    const hasSpaces = /\s/;

    const isValidPassword = regex.test(password) && !hasSpaces.test(password);

    passwordWeakError.style.display = isValidPassword ? "none" : "block";
    enableRecoveryPasswordsButton();
  }

  function checkPasswordMatch() {
    const password = passwordInput.value;
    const confirmPassword = confirmPasswordInput.value;

    const passwordsMatch = password === confirmPassword;

    passwordMismatchError.style.display = passwordsMatch ? "none" : "block";
    enableRecoveryPasswordsButton();
  }

  passwordInput.addEventListener("input", checkPasswordStrength);

  confirmPasswordInput.addEventListener("input", checkPasswordMatch);

  recoveryPasswordsForm.addEventListener("submit", function(event) {
    if (passwordInput.value !== confirmPasswordInput.value) {
      passwordMismatchError.style.display = "block";
      event.preventDefault();
    }
  });
});