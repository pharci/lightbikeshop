(function($) {
// ===== helpers =====
const $list = $('#cart-items');
const $summaryPrice = $('#cart-total-price');
const $summarySubtotalPrice = $('#cart-subtotal-price');
const $summaryCount = $('#cart-total-count');
const fmt = v =>
    new Intl
        .NumberFormat(
            'ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2})
        .format(v || 0);
const esc = s => String(s || '').replace(
    /[&<>"']/g,
    m =>
        ({'&': '&amp;',
          '<': '&lt;',
          '>': '&gt;',
          '"': '&quot;',
          '\'': '&#39;'}[m]));
const emptyHtml =
    `<div class="cart-empty"><div><div class="cart-empty__title">Корзина пуста</div><div class="cart-empty__text">Добавьте товары из каталога</div></div></div>`;

// ===== totals =====
function updateCartSummary() {
  return $.getJSON('/api/cart/').done(r => {
    const c = r.cart || {};
    $summaryPrice.text(fmt(c.cart_total_price) + ' ₽');
    $summarySubtotalPrice.text(fmt(c.cart_subtotal_price || 0) + ' ₽');
    $summaryCount.text((c.cart_total_count || 0) + ' товаров');
  });
}

// ===== load full cart =====
function loadCart() {
  $.getJSON('/api/cart/').done(r => {
    const items = r.items || [];
    $list.empty();
    if (!items.length) {
      $list.html(emptyHtml);
      toggleCheckout(false, true);
    } else {
      $list.html(items.map(renderItem).join(''));
      recomputeBlocking();
    }
    const c = r.cart || {};
    $summaryPrice.text(fmt(c.cart_total_price || 0) + ' ₽');
    $summarySubtotalPrice.text(fmt(c.cart_subtotal_price || 0) + ' ₽');
    $summaryCount.text((c.cart_total_count || 0) + ' товаров');
  });
}

// ===== UI =====
function chipAvail(stock) {
  return `<span class="meta-chip">${
      (stock ?? null) ? 'В наличии' : 'Нет в наличии'}</span>`;
}
function renderItem(it) {
  const v = it.variant || it.product || {};
  const id = v.id, name = v.display_name || v.name || 'Товар';
  const img = v.main_image_url || v.imageURL || v.image_url || '';
  const url = v.variant_url || v.product_url || v.url || '#';
  const slug = v.slug || '';
  const stock = (typeof it.stock_count === 'number') ? it.stock_count :
      (typeof v.inventory === 'number')              ? v.inventory :
                                                       null;
  const qty = it.quantity || 0;
  const unit = Number(it.unit_price || v.price || 0);
  const total = Math.round(it.product_total_price || 0);
  const disPlus = (typeof stock === 'number' && qty >= stock) ? 'disabled' : '';
  const stockAttr = (stock ?? '');
  return `
    <article class="cart-item" data-variant-id="${id}" data-stock="${
      stockAttr}">
      <a class="cart-item__image" href="${url}">${
      img ? `<img src="${img}" alt="${esc(name)}">` : ''}</a>
      <div>
        <a class="cart-item__title-link" href="${
      url}"><h3 class="cart-item__title">${esc(name)}</h3></a>
        <div class="cart-item__meta">
          ${slug ? `<span class="meta-chip">арт. ${esc(slug)}</span>` : ''}
          ${chipAvail(stock)}
          ${
      typeof stock === 'number' ?
          `<span class="meta-chip">Остаток: ${stock}</span>` :
          ''}
          ${unit ? `<span class="meta-chip">${fmt(unit)}₽/шт.</span>` : ''}
        </div>
      </div>
      <div class="cart-item__controls">
        <div class="cart-item__price" id="product-total-price-${id}">${
      fmt(total)}₽</div>
        <div class="cart-item__qty">
          <div class="counter">
            <button class="counter__btn js-decrease" type="button" data-variant-id="${
      id}">−</button>
            <span class="counter__value" id="product-count-${id}">${
      qty} шт.</span>
            <button class="counter__btn js-increase" type="button" data-variant-id="${
      id}" ${disPlus}>+</button>
          </div>
        </div>
        <div class="cart-item__remove">
          <button class="remove-btn js-remove" type="button" title="Удалить" data-variant-id="${
      id}" aria-label="Удалить товар">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M9 3h6m-9 4h12m-1 0-1 13a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              <path d="M10 11v6M14 11v6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </button>
        </div>
      </div>
    </article>`;
}

function toggleCheckout(blocked, empty) {
  const $btn = $('#checkout-btn');

  if (!$btn.data('href')) {
    $btn.data('href', $btn.attr('href') || '');
  }

  if (blocked || empty) {
    $btn.removeAttr('href')
        .attr('aria-disabled', 'true')
        .addClass('btn--disabled')
        .text('Недопустимый заказ');
  } else {
    $btn.attr('href', $btn.data('href'))
        .attr('aria-disabled', 'false')
        .removeClass('btn--disabled')
        .text('Перейти к оформлению');
  }
}

function recomputeBlocking() {
  let blocked = false;
  const $items = $list.find('.cart-item');
  $items.each(function() {
    const stockAttr = this.dataset.stock;
    const stock = (stockAttr === '' || stockAttr == null) ?
        null :
        parseInt(stockAttr, 10);
    const qty = parseInt($(this).find('.counter__value').text(), 10);
    if (stock != null && qty > stock) {
      blocked = true;
      $(this).addClass('cart-item--error');
    } else
      $(this).removeClass('cart-item--error');
  });
  toggleCheckout(blocked, $items.length === 0);
}

// ===== per-item change =====
function changeItem(variantId, action) {
  return $.getJSON('/api/variants/', {variant_id: variantId, action})
      .done(resp => {
        // обновляем строку
        $('#product-total-price-' + variantId)
            .text(fmt(resp.product_total_price || 0) + '₽');
        $('#product-count-' + variantId).text((resp.count || 0) + ' шт.');
        // плюс дизейбл по остатку
        const $item = $list.find(`.cart-item[data-variant-id="${variantId}"]`);
        const stockAttr = $item.get(0)?.dataset.stock;
        const stock = (stockAttr === '' || stockAttr == null) ?
            null :
            parseInt(stockAttr, 10);
        $item.find('.js-increase')
            .prop('disabled', (stock != null) && (resp.count >= stock));
        // удалить строку при нуле
        if (action === 'remove' && (resp.count || 0) === 0) $item.remove();
        if ($list.find('.cart-item').length === 0) $list.html(emptyHtml);
        recomputeBlocking();
      })
      .then(updateCartSummary);  // всегда подтягиваем итог из /api/cart/
}

// ===== events =====
function bind() {
  const $root = $list;
  $root.on('click', '.js-increase, .js-decrease', function() {
    const id = $(this).data('variant-id');
    changeItem(id, $(this).hasClass('js-increase') ? 'add' : 'remove');
  });
  $root.on('click', '.js-remove', function() {
    const id = $(this).data('variant-id');
    const $item = $(this).closest('.cart-item');
    $.when(
         $.getJSON('/api/variants/', {variant_id: id, action: 'remove_all'}),
         updateCartSummary())
        .done(() => {
          $item.remove();
          if (!$list.find('.cart-item').length) $list.html(emptyHtml);
          recomputeBlocking();
        });
  });
}

// ===== init =====
$(function() {
  loadCart();
  bind();
});
})(jQuery);
