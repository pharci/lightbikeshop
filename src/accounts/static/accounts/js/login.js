(function() {
const emailStep = document.getElementById('email-step');
const codeStep = document.getElementById('code-step');
const emailInput = document.getElementById('id_email');
const emailErr = document.getElementById('email-error');
const sendBtn = document.getElementById('send-btn');

const codeInput = document.getElementById('id_code');
const verifyBtn = document.getElementById('verify-btn');
const codeErr = document.getElementById('code-error');
const codeInfo = document.getElementById('code-info');
const requestIdEl = document.getElementById('request_id');
const emailHidden = document.getElementById('email_hidden');
const resendBtn = document.getElementById('resend-btn');
const resendTimer = document.getElementById('resend-timer');
const changeEmailBtn = document.getElementById('change-email-btn');

const reSiteKey = window.recaptchaSiteKey;
let countdown = null, left = 30;

// CSRF из cookie -> заголовок X-CSRFToken
function getCookie(name) {
  const m = document.cookie.match(
      '(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)');
  return m ? decodeURIComponent(m[1]) : '';
}
const csrftoken = getCookie('csrftoken');

function validEmail(v) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
}

function startTimer() {
  left = 30;
  resendBtn.disabled = true;
  resendTimer.textContent = `(${left}s)`;
  countdown = setInterval(() => {
    left -= 1;
    if (left <= 0) {
      clearInterval(countdown);
      resendTimer.textContent = '';
      resendBtn.disabled = false;
    } else {
      resendTimer.textContent = `(${left}s)`;
    }
  }, 1000);
}

function grecaptchaToken() {
  return new Promise((resolve) => {
    if (!reSiteKey || !window.grecaptcha) {
      resolve('');
      return;
    }
    grecaptcha.ready(function() {
      grecaptcha.execute(reSiteKey, {action: 'login'})
          .then(resolve)
          .catch(() => resolve(''));
    });
  });
}

async function sendCode() {
  const email = (emailInput.value || '').trim().toLowerCase();
  emailErr.hidden = true;
  if (!validEmail(email)) {
    emailErr.hidden = false;
    return;
  }
  sendBtn.disabled = true;

  const token = await grecaptchaToken();
  const body = new URLSearchParams();
  body.append('email', email);
  body.append('g-recaptcha-response', token);

  const r = await fetch('/api/auth/send_code/', {
    method: 'POST',
    headers: {
      'X-Requested-With': 'XMLHttpRequest',
      'X-CSRFToken': csrftoken,
    },
    body,
    credentials: 'same-origin',
  });
  const data = await r.json().catch(() => ({ok: false, error: 'bad_json'}));

  sendBtn.disabled = false;
  if (!data.ok) {
    if (data.error === 'invalid_email') emailErr.hidden = false;
    alert('Не удалось отправить код. Попробуйте позже.');
    return;
  }

  requestIdEl.value = data.request_id;
  emailHidden.value = email;
  emailStep.hidden = true;
  codeStep.hidden = false;
  codeInput.focus();
  codeErr.hidden = true;
  codeInfo.hidden = true;
  startTimer();
}

async function verifyCode(e) {
  e.preventDefault();
  codeErr.hidden = true;
  const code = (codeInput.value || '').trim();
  if (!/^\d{6}$/.test(code)) {
    codeErr.hidden = false;
    return;
  }

  const body = new URLSearchParams();
  body.append('email', emailHidden.value);
  body.append('request_id', requestIdEl.value);
  body.append('code', code);

  verifyBtn.disabled = true;
  const r = await fetch('/api/auth/verify_code/', {
    method: 'POST',
    headers: {
      'X-Requested-With': 'XMLHttpRequest',
      'X-CSRFToken': csrftoken,
    },
    body,
    credentials: 'same-origin',
  });
  const data = await r.json().catch(() => ({ok: false, error: 'bad_json'}));
  verifyBtn.disabled = false;

  if (!data.ok) {
    if (data.error === 'bad_code') {
      codeErr.hidden = false;
      codeInfo.hidden = false;
      codeInfo.textContent = data.attempts_left != null ?
          `Осталось попыток: ${data.attempts_left}` :
          '';
    } else if (data.error === 'expired_or_locked') {
      alert('Код истёк или превышен лимит попыток. Отправьте код заново.');
    } else {
      alert('Ошибка подтверждения. Попробуйте снова.');
    }
    return;
  }
  window.location.href = data.redirect || '/';
}

async function resend() {
  if (!resendBtn.disabled) sendCode();
}
function changeEmail() {
  codeStep.hidden = true;
  emailStep.hidden = false;
  emailInput.focus();
}

emailStep.addEventListener('submit', function(e) {
  e.preventDefault();
  sendCode();
});
codeStep.addEventListener('submit', verifyCode);
resendBtn.addEventListener('click', resend);
changeEmailBtn.addEventListener('click', changeEmail);
})();
