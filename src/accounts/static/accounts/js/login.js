function initLoginCheck() {
  const email = document.getElementById('id_email');
  const pwd = document.getElementById('id_password');
  const btn = document.getElementById('login-button');
  const err = document.getElementById('email-invalid-error');
  if (!email || !pwd || !btn) return;

  function check() {
    const ok = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value);
    err.style.display = ok || !email.value ? 'none' : 'block';
    btn.disabled = !ok || !pwd.value;
  }

  ['input', 'change'].forEach(e => {
    email.addEventListener(e, check);
    pwd.addEventListener(e, check);
  });

  // проверка сразу и после автозаполнения
  check();
  setTimeout(check, 300);
}

window.addEventListener('DOMContentLoaded', initLoginCheck);
window.addEventListener('pageshow', initLoginCheck);