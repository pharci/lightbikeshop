// Утилита csrftoken, если нет глобальной
function getCookie(name) {
  const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return m ? m.pop() : '';
}

document.addEventListener('DOMContentLoaded', function() {
  // Инициализировать иконки Lucide, если загружены
  if (window.lucide && lucide.createIcons) lucide.createIcons();

  // ---------- ТАБЫ ----------
  const KEY = 'profile.section';
  const buttons = Array.from(document.querySelectorAll('.js-tab'));
  const sections = Array.from(document.querySelectorAll('.js-section'));

  function show(name) {
    sections.forEach(s => s.hidden = (s.id !== 'section-' + name));
    buttons.forEach(
        b => b.classList.toggle('is-active', b.dataset.section === name));
    localStorage.setItem(KEY, name);
    history.replaceState(null, '', '#' + name);
  }

  buttons.forEach(b => b.addEventListener('click', (e) => {
    e.preventDefault();
    show(b.dataset.section);
  }));

  const fromHash = location.hash.replace('#', '');
  const initial = ['profile', 'apps', 'orders', 'history'].includes(fromHash) ?
      fromHash :
      (localStorage.getItem(KEY) || 'profile');
  show(initial);

  // ---------- МОДАЛКА ОТМЕНЫ ----------
  const overlay = document.getElementById('confirmationOverlay');
  const confirmBtn = document.getElementById('confirmBtn');
  const cancelBtn = document.getElementById('cancelBtn');

  // делегирование клика по кнопке отмены
  document.addEventListener('click', function(e) {
    const btn = e.target.closest('.cancel_order');
    if (!btn) return;
    e.preventDefault();
    confirmBtn.dataset.orderId = btn.dataset.orderId;
    if (overlay) overlay.style.display = 'block';
  });

  // закрыть модалку
  if (cancelBtn)
    cancelBtn.addEventListener('click', () => overlay.style.display = 'none');
  if (overlay)
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.style.display = 'none';
    });

  // подтвердить отмену
  if (confirmBtn)
    confirmBtn.addEventListener('click', function() {
      const orderId = this.dataset.orderId;
      fetch('/api/orders/delete/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': getCookie('csrftoken')
        },
        body: new URLSearchParams({order_id: orderId})
      })
          .then(r => {
            if (!r.ok) throw r;
            return r.json();
          })
          .then(() => {
            const card = document.getElementById(orderId);
            if (!card) return;
            const badge = card.querySelector('.badge');
            if (badge) {
              badge.classList.remove('badge--ok');
              badge.classList.add('badge--danger');
              badge.textContent = 'Отменён';
            }
            const cancel = card.querySelector('.cancel_order');
            if (cancel) cancel.remove();

            // перенос в историю
            const historySection = document.getElementById('section-history');
            if (historySection) historySection.prepend(card);

            overlay.style.display = 'none';
          })
          .catch(() => {
            alert('Не удалось отменить заказ. Попробуйте позже.');
            overlay.style.display = 'none';
          });
    });
});
