(function($) {
const $wrap = $('#buyControls');
if (!$wrap.length) return;

const vid = String($wrap.data('variant-id') || '').trim();
const cartUrl = String($wrap.data('cart-url') || '/cart/');

function htmlAddButton(disabled = false, label = 'В корзину') {  // NEW
  const dis = disabled ? 'disabled aria-disabled="true"' : '';
  const cls = disabled ? 'btn btn--disabled' : 'btn';
  return `<button class="${cls} js-add" type="button" ${dis}>${label}</button>`;
}

function htmlInCart(count, stock) {
  const disMinus = count <= 0 ? 'disabled' : '';
  const disPlus =
      (typeof stock === 'number' && count >= stock) ? 'disabled' : '';
  return `
      <a class="btn" href="${cartUrl}">В корзине</a>
      <div class="qty" aria-live="polite">
        <button class="qty__btn js-dec" type="button" ${
      disMinus} aria-label="Уменьшить">−</button>
        <span class="qty__val" id="pd-count">${count}</span>
        <button class="qty__btn js-inc" type="button" ${
      disPlus} aria-label="Увеличить">+</button>
      </div>
    `;
}

function renderAdd(disabled = false, label = 'В корзину') {  // NEW
  $wrap.html(htmlAddButton(disabled, label));
}
function renderInCart(c, stock) {
  $wrap.html(htmlInCart(c, stock));
}
function syncHeaderCounter(n) {
  if (n !== undefined) $('.cart-count-text').text(n);
}

// начальная инициализация
function init() {
  $.getJSON('/api/variants/', {variant_id: vid})
      .done(res => {
        const count = +res.count || 0;
        const stock =
            (res.stock_count !== undefined) ? +res.stock_count : undefined;

        // NEW: если товара нет — показываем выключенную кнопку
        if (typeof stock === 'number' && stock <= 0) {
          renderAdd(true, 'Нет в наличии');
          return;
        }

        count > 0 ? renderInCart(count, stock) : renderAdd();
      })
      .fail(() => renderAdd());
}

// изменение количества в корзине
function change(action) {
  return $.getJSON('/api/variants/', {variant_id: vid, action}).done(res => {
    const count = +res.count || 0;
    const stock =
        (res.stock_count !== undefined) ? +res.stock_count : undefined;

    syncHeaderCounter(res.cart_total_count);

    // сервер вернул «нельзя добавить»
    if (res.error === 'out_of_stock') {  // NEW
      if (count <= 0)
        renderAdd(true, 'Нет в наличии');
      else
        renderInCart(count, stock);
      return;
    }

    if (count <= 0)
      renderAdd();
    else
      renderInCart(count, stock);
  });
}

// события
$wrap
    .on('click', '.js-add',
        function() {
          // NEW: фронтовая защита на всякий (если кнопка disabled — игнор)
          if (this.disabled) return;
          change('add');
        })
    .on('click', '.js-inc', () => change('add'))
    .on('click', '.js-dec', () => change('remove'));

init();
})(jQuery);



(() => {
  const mainEl = document.querySelector('.variant-gallery__main');
  if (!mainEl) return;

  // Основной слайдер (только для фото)
  const mainSwiper = mainEl.swiper || new Swiper(mainEl, {
                       slidesPerView: 1,
                       speed: 350,
                       autoHeight: false,  // высоту контролирует квадрат слева
                       observer: true,
                       observeParents: true,
                       preloadImages: false,
                       lazy: true,
                       watchSlidesProgress: true,
                       on: {
                         init(sw) {
                           requestAnimationFrame(() => sw.update());
                         },
                         resize(sw) {
                           sw.update();
                         }
                       }
                     });

  // Рельса превью — клики + подсветка
  const rail = document.querySelector('.variant-gallery__rail-cell .rail');
  if (!rail) return;
  const items = Array.from(rail.querySelectorAll('.rail__item'));

  function setActive(idx) {
    items.forEach((btn, i) => btn.classList.toggle('is-active', i === idx));
    items[idx]?.scrollIntoView(
        {block: 'nearest', inline: 'nearest', behavior: 'smooth'});
  }

  rail.addEventListener('click', (e) => {
    const btn = e.target.closest('.rail__item');
    if (!btn) return;
    const idx = Number(btn.dataset.index) || 0;
    mainSwiper.slideTo(idx);
  });

  mainSwiper.on('slideChange', () => setActive(mainSwiper.realIndex));
  setActive(mainSwiper.realIndex || 0);
})();


// Тоггл "Показать полностью" для описания
document.addEventListener('click', (e) => {
  const btn = e.target.closest('[data-collapsible]');
  if (!btn) return;

  const sel = btn.getAttribute('data-collapsible');
  const el = document.querySelector(sel);
  if (!el) return;

  const expanded = btn.getAttribute('aria-expanded') === 'true';
  btn.setAttribute('aria-expanded', String(!expanded));

  if (expanded) {
    // свернуть
    el.classList.remove('prose--expanded');
    el.classList.add('prose--clamp');
    btn.textContent = 'Показать полностью';
  } else {
    // развернуть
    el.classList.remove('prose--clamp');
    el.classList.add('prose--expanded');
    btn.textContent = 'Свернуть';
  }
});

// Если описание короткое — прячем кнопку
document.addEventListener('DOMContentLoaded', () => {
  const el = document.querySelector('#descBody');
  const btn = document.querySelector('[data-collapsible="#descBody"]');
  if (!el || !btn) return;

  const isScrollable =
      el.scrollHeight > 340;  // немного больше max-height, с запасом
  if (!isScrollable) {
    btn.style.display = 'none';
    el.classList.remove('prose--clamp');
  }
});