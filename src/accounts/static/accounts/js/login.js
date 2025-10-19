(function() {
// --- DOM ---
const emailStep = document.getElementById('email-step');
const codeStep = document.getElementById('code-step');

const emailInput = document.getElementById('id_email');
const emailErr = document.getElementById('email-error');
const consentEl = document.getElementById('id_consent');
const consentErr = document.getElementById('consent-error');
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

// --- cfg ---
const reSiteKey = window.recaptchaSiteKey;
let countdown = null;
let left = 30;
let sending = false;
let verifying = false;

// --- helpers ---
function getCookie(name) {
  const m = document.cookie.match(
      '(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)');
  return m ? decodeURIComponent(m[1]) : '';
}
const csrftoken = getCookie('csrftoken');

function validEmail(v) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
}

function show(el, ok) {
  // ok=true -> скрыть ошибку
  el.hidden = !!ok;
  if (ok)
    el.removeAttribute('aria-live');
  else
    el.setAttribute('aria-live', 'polite');
}

function startTimer() {
  clearInterval(countdown);
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
    if (!reSiteKey || !window.grecaptcha) return resolve('');
    grecaptcha.ready(function() {
      grecaptcha.execute(reSiteKey, {action: 'login'})
          .then(resolve)
          .catch(() => resolve(''));
    });
  });
}

// --- actions ---
async function sendCode() {
  if (sending) return;
  const email = (emailInput.value || '').trim().toLowerCase();
  const consent = !!consentEl.checked;

  // валидация и показ ошибок
  const emailOk = validEmail(email);
  const consentOk = consent;
  show(emailErr, emailOk);
  show(consentErr, consentOk);
  if (!(emailOk && consentOk)) return;

  sending = true;
  sendBtn.disabled = true;

  const token = await grecaptchaToken();
  const body = new URLSearchParams();
  body.append('email', email);
  body.append('agree', consent ? '1' : '0');
  body.append('g-recaptcha-response', token);

  try {
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

    if (!data.ok) {
      if (data.error === 'need_consent')
        show(consentErr, false);
      else if (data.error === 'invalid_email')
        show(emailErr, false);
      else
        alert('Не удалось отправить код. Попробуйте позже.');
      return;
    }

    // успех
    requestIdEl.value = data.request_id;
    emailHidden.value = email;
    emailStep.hidden = true;
    codeStep.hidden = false;
    codeInput.value = '';
    show(codeErr, true);
    show(codeInfo, true);
    codeInput.focus();
    startTimer();
  } finally {
    sending = false;
    sendBtn.disabled = false;
  }
}

async function verifyCode(e) {
  e.preventDefault();
  if (verifying) return;

  const code = (codeInput.value || '').trim();
  const codeOk = /^\d{6}$/.test(code);
  show(codeErr, codeOk);
  if (!codeOk) return;

  verifying = true;
  verifyBtn.disabled = true;

  const body = new URLSearchParams();
  body.append('email', emailHidden.value || '');
  body.append('request_id', requestIdEl.value || '');
  body.append('code', code);

  try {
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

    if (!data.ok) {
      if (data.error === 'bad_code') {
        show(codeErr, false);
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
    window.location.assign(data.redirect || '/');
  } finally {
    verifying = false;
    verifyBtn.disabled = false;
  }
}

function resend() {
  if (!resendBtn.disabled) sendCode();
}

function changeEmail() {
  codeStep.hidden = true;
  emailStep.hidden = false;
  emailInput.focus();
}

// --- listeners ---
emailStep.addEventListener('submit', function(e) {
  e.preventDefault();
  sendCode();
});

// показать ошибки при уходе с поля/чекбокса
emailInput.addEventListener(
    'blur', () => show(emailErr, validEmail((emailInput.value || '').trim())));
consentEl.addEventListener(
    'change', () => show(consentErr, !!consentEl.checked));

// Enter по email
emailInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    emailStep.requestSubmit();
  }
});

codeStep.addEventListener('submit', verifyCode);
resendBtn.addEventListener('click', resend);
changeEmailBtn.addEventListener('click', changeEmail);
})();
