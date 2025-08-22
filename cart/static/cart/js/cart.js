(function($) {

// ---- helper ----
function formatPrice(n) {
  const x = Number(n) || 0;
  return x.toLocaleString('ru-RU');
}
function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, m => ({
                                               '&': '&amp;',
                                               '<': '&lt;',
                                               '>': '&gt;',
                                               '"': '&quot;',
                                               '\'': '&#39;'
                                             }[m]));
}

// ---- Нормализуем данные варианта ----
function pickVariant(item) {
  const v = item.variant || item.product || {};
  return {
    id: v.id,
    name: v.display_name || v.name || v.title || v.base_name || 'Товар',
    img: v.main_image_url || v.imageURL || v.image_url || '',
    url: v.variant_url || v.product_url || v.url || '#',  // ← ССЫЛКА
    sku: v.sku || '',
    stock: (typeof item.stock_count === 'number') ?
        item.stock_count :
        (typeof v.inventory === 'number' ? v.inventory : null),
    qty: item.quantity || 0,
    total: Math.round(item.product_total_price || 0),
    unit_price: Number(item.unit_price || v.price || 0)
  };
}

function availabilityChip(stock) {
  return stock ? `<span class="meta-chip">В наличии</span>` :
                 `<span class="meta-chip">Нет в наличии</span>`;
}

// ---- Рендер строки корзины ----
function renderItem(raw) {
  const v = pickVariant(raw);
  const disPlus =
      (typeof v.stock === 'number' && v.qty >= v.stock) ? 'disabled' : '';
  const stockAttr = (v.stock ?? '');

  return `
  <article class="cart-item" data-variant-id="${v.id}" data-stock="${
      stockAttr}">
    <!-- Картинка — отдельная ссылка -->
    <a class="cart-item__image" href="${v.url}">
      ${v.img ? `<img src="${v.img}" alt="${escapeHtml(v.name)}">` : ''}
    </a>

    <!-- Название и мета -->
    <div>
      <a class="cart-item__title-link" href="${v.url}">
        <h3 class="cart-item__title">${escapeHtml(v.name)}</h3>
      </a>
      <div class="cart-item__meta">
        ${
      v.sku ? `<span class="meta-chip">арт. ${escapeHtml(v.sku)}</span>` : ''}
        ${availabilityChip(v.stock)}
        ${
      typeof v.stock === 'number' ?
          `<span class="meta-chip">Остаток: ${v.stock}</span>` :
          ''}
        ${
      v.unit_price ?
          `<span class="meta-chip">${formatPrice(v.unit_price)}₽/шт.</span>` :
          ''}
      </div>
    </div>

    <div class="cart-item__controls">
      <!-- Цена итога по позиции -->
      <div class="cart-item__price" id="product-total-price-${v.id}">
        ${formatPrice(v.total)}₽
      </div>

      <!-- Счётчик -->
      <div class="cart-item__qty">
        <div class="counter">
          <button class="counter__btn js-decrease" type="button" data-variant-id="${
      v.id}">−</button>
          <span class="counter__value" id="product-count-${v.id}">${
      v.qty} шт.</span>
          <button class="counter__btn js-increase" type="button" data-variant-id="${
      v.id}" ${disPlus}>+</button>
        </div>
      </div>

      <!-- Удалить -->
      <div class="cart-item__remove">
        <button class="remove-btn js-remove" type="button" title="Удалить" data-variant-id="${
      v.id}" aria-label="Удалить товар">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M9 3h6m-9 4h12m-1 0-1 13a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <path d="M10 11v6M14 11v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </div>
  </article>`;
}

// ---- блок кнопки оформления ----
function updateCheckoutButton(isBlocked, cartIsEmpty) {
  const $btn = $('#checkout-btn');

  // один раз запомним исходный href
  if (!$btn.data('href')) $btn.data('href', $btn.attr('href') || '');

  if (isBlocked || cartIsEmpty) {
    // дизейблим: убираем href, ставим aria, класс
    $btn.removeAttr('href')
        .attr('aria-disabled', 'true')
        .addClass('disabled')
        .text('Недопустимый заказ');
  } else {
    // возвращаем рабочее состояние
    $btn.attr('href', $btn.data('href'))
        .attr('aria-disabled', 'false')
        .removeClass('disabled')
        .text('Перейти к оформлению');
  }
}
// один раз повесим перехватчик клика на недоступную «кнопку»
$(document).on('click', '#checkout-btn.disabled', function(e) {
  e.preventDefault();
  e.stopPropagation();
  return false;
});

// ---- Итоги ----
function refreshSummary(summary) {
  $('#cart-total-price').text(formatPrice(summary.cart_total_price) + '₽');
  $('#cart-total-count').text(summary.cart_total_count + ' товаров');
  $('.cart-count-text')
      .text(summary.cart_total_count);  // если используешь в шапке
}

// ---- Проверка на ошибки (qty > stock) ----
function recomputeBlocking() {
  let blocked = false;
  const $items = $('#cart-items .cart-item');
  $items.each(function() {
    const stockAttr = this.dataset.stock;
    const stock = (stockAttr === '' || stockAttr == null) ?
        null :
        parseInt(stockAttr, 10);
    const qty =
        parseInt($(this).find('.counter__value').text(), 10);  // "3 шт." → 3
    if (stock != null && qty > stock) {
      blocked = true;
      $(this).addClass('cart-item--error');
    } else {
      $(this).removeClass('cart-item--error');
    }
  });
  updateCheckoutButton(blocked, $items.length === 0);
}

// ---- Загрузка корзины ----
function updateCartItems() {
  $.getJSON('/cart_data/', function(response) {
    const items = response.items || [];
    const $list = $('#cart-items').empty();

    refreshSummary(response.cart || {cart_total_price: 0, cart_total_count: 0});

    if (!items.length) {
      $list.html(
          '<div class="cart-empty"><div><div class="cart-empty__title">Корзина пуста</div><div class="cart-empty__text">Добавьте товары из каталога</div></div></div>');
      updateCheckoutButton(false, true);
      return;
    }

    const html = items.map(renderItem).join('');
    $list.html(html);
    recomputeBlocking();
  });
}

// ---- API: изменение количества / удаление ----
function changeItem(variantId, action) {
  // поддержка remove_all для полного удаления
  return $.getJSON('/variant_edit/', {variant_id: variantId, action: action});
}

// ---- события ----
function bindEvents() {
  const $root = $('#cart-items');

  // плюс/минус
  $root.on('click', '.js-increase, .js-decrease', function() {
    const $btn = $(this);
    const variantId = $btn.data('variant-id');
    const action = $btn.hasClass('js-increase') ? 'add' : 'remove';
    const $item = $btn.closest('.cart-item');

    changeItem(variantId, action).done(function(resp) {
      $('#product-total-price-' + variantId)
          .text(formatPrice(resp.product_total_price || 0) + '₽');
      $('#product-count-' + variantId).text((resp.count || 0) + ' шт.');
      refreshSummary({
        cart_total_price: resp.cart_total_price || 0,
        cart_total_count: resp.cart_total_count || 0
      });

      // дизейбл "+"
      const stockAttr = $item.get(0).dataset.stock;
      const stock = (stockAttr === '' || stockAttr == null) ?
          null :
          parseInt(stockAttr, 10);
      $item.find('.js-increase')
          .prop('disabled', (stock != null) && (resp.count >= stock));

      // убрать строку при нуле
      if (action === 'remove' && (resp.count || 0) === 0) {
        $item.remove();
      }

      if ($('#cart-items .cart-item').length === 0) {
        $('#cart-items')
            .html(
                '<div class="cart-empty"><div><div class="cart-empty__title">Корзина пуста</div><div class="cart-empty__text">Добавьте товары из каталога</div></div></div>');
      }
      recomputeBlocking();
    });
  });

  // удалить строку
  $root.on('click', '.js-remove', function() {
    const variantId = $(this).data('variant-id');
    const $item = $(this).closest('.cart-item');
    changeItem(variantId, 'remove_all').done(function(resp) {
      $item.remove();
      refreshSummary({
        cart_total_price: resp.cart_total_price || 0,
        cart_total_count: resp.cart_total_count || 0
      });
      if ($('#cart-items .cart-item').length === 0) {
        $('#cart-items')
            .html(
                '<div class="cart-empty"><div><div class="cart-empty__title">Корзина пуста</div><div class="cart-empty__text">Добавьте товары из каталога</div></div></div>');
      }
      recomputeBlocking();
    });
  });
}

// ---- init ----
$(function() {
  updateCartItems();
  bindEvents();
});
})(jQuery);
