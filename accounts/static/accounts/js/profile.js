$(function() {
  const $btn = $('#dropdown-button');
  const $container = $('#dropdown-container');

  // 1) Плавная анимация высоты
  function openCollapsible($el) {
    const el = $el.get(0);
    $el.addClass('is-open');
    // вычисляем натуральную высоту
    const prevHeight = el.style.height;
    el.style.height = 'auto';
    const target = el.getBoundingClientRect().height;
    el.style.height = prevHeight || '0px';
    // следующий тик — анимируем до нужной высоты
    requestAnimationFrame(() => {
      el.style.height = target + 'px';
    });
    // по окончании — ставим auto, чтобы контейнер подстраивался по контенту
    el.addEventListener('transitionend', function onEnd(e) {
      if (e.propertyName === 'height') {
        el.style.height = 'auto';
        el.removeEventListener('transitionend', onEnd);
      }
    });
  }

  function closeCollapsible($el) {
    const el = $el.get(0);
    $el.removeClass('is-open');
    // от «auto» к фиксированной высоте, затем к 0
    const start = el.getBoundingClientRect().height;
    el.style.height = start + 'px';
    requestAnimationFrame(() => {
      el.style.height = '0px';
    });
  }

  // 2) Обновление текста и поворот стрелочки
  function setButtonState(isOpen) {
    const $text = $('#history-button-text');
    const $chev = $btn.find('.history-toggle__chev');
    if ($text.length)
      $text.text(isOpen ? 'Скрыть историю' : 'Показать историю');
    if ($chev.length) $btn.toggleClass('is-open', isOpen);
  }

  // 3) Счётчик заказов в истории
  function updateHistoryCount() {
    const count =
        $container.find('.order').length;  // или уточни селектор, если нужно
    $('#history-count-badge').text(count);
  }
  updateHistoryCount();

  // 4) Запоминание состояния
  const STORAGE_KEY = 'profile.history.open';
  const initialOpen = localStorage.getItem(STORAGE_KEY) === '1';

  // вешаем базовые классы для анимации (если хочется без классов — можно и по
  // id)
  $container.addClass('collapsible');

  if (initialOpen) {
    // раскрываем без анимации при первом рендере
    $container.addClass('is-open').css('height', 'auto');
    setButtonState(true);
  } else {
    $container.removeClass('is-open').css('height', 0);
    setButtonState(false);
  }

  // 5) Тоггл по клику
  $btn.on('click', function() {
    const isOpen = $container.hasClass('is-open');
    if (isOpen) {
      closeCollapsible($container);
      setButtonState(false);
      localStorage.setItem(STORAGE_KEY, '0');
    } else {
      openCollapsible($container);
      setButtonState(true);
      localStorage.setItem(STORAGE_KEY, '1');

      // Дружелюбный автоскролл к началу истории
      const y = $container.offset().top - 16;
      window.scrollTo({top: y, behavior: 'smooth'});
    }
  });
});



$(function() {
  const $doc = $(document);
  const $overlay = $('#confirmationOverlay');
  const $confirm = $('#confirmBtn');
  const $cancel = $('#cancelBtn');

  // 1) Делегированный клик по кнопке отмены
  $doc.on('click', '.cancel_order', function(e) {
    e.preventDefault();  // на случай, если внутри формы
    const orderId = $(this).data('order-id');
    $confirm.data('order-id', orderId);
    $overlay.fadeIn(150);
  });

  // 2) Закрыть модалку
  $cancel.on('click', () => $overlay.fadeOut(150));
  $overlay.on('click', function(e) {
    if (e.target === this) $(this).fadeOut(150);  // клик по фону
  });

  // 3) Подтвердить отмену → AJAX POST
  $confirm.on('click', function() {
    const orderId = $(this).data('order-id');
    $.ajax({
      url: '/delete_order/',
      type: 'POST',
      dataType: 'json',
      data: {order_id: orderId},
      headers: {'X-CSRFToken': getCookie('csrftoken')},
      success: function(resp) {
        // карточка заказа
        const $card = $('#' + orderId);

        // Обновим визуально статус
        $card.find('.badge')
            .removeClass('badge--ok')
            .addClass('badge--danger')
            .text('Отменён');

        // Уберём кнопку «Отменить»
        $card.find('.cancel_order').remove();

        // Перенесём в историю (если карточка была в активных)
        $('#dropdown-container').prepend($card);

        // Обновим счётчик в кнопке истории
        $('#history-count-badge').text($('#dropdown-container .order').length);

        // Закрыть модалку
        $overlay.fadeOut(150);
      },
      error: function(xhr) {
        console.error('Cancel error', xhr.status, xhr.responseText);
        alert('Не удалось отменить заказ. Попробуйте позже.');
        $overlay.fadeOut(150);
      }
    });
  });
});