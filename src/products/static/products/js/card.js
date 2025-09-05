const isTouch = ('ontouchstart' in window) || navigator.maxTouchPoints > 0 ||
    navigator.msMaxTouchPoints > 0 ||
    (window.matchMedia && window.matchMedia('(pointer: coarse)').matches);

document.addEventListener('click', (e) => {
  const card = e.target.closest('.product-card[data-url]');
  if (!card) return;
  // не уводим, если клик по кнопке/ссылке внутри
  if (e.target.closest('a, button, [role="button"]')) return;
  window.location.href = card.dataset.url;
});

// Доступность с клавиатуры
document.querySelectorAll('.product-card[data-url]').forEach(card => {
  card.setAttribute('role', 'link');
  card.setAttribute('tabindex', '0');
  card.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      window.location.href = card.dataset.url;
    }
  });
});


function addHoverZones(swiper) {
  const n = swiper.slides.length;
  if (n <= 1) return;

  const host = swiper.el;
  if (host.querySelector('.hover-zones')) return;

  const zones = document.createElement('div');
  zones.className = 'hover-zones';

  for (let i = 0; i < n; i++) {
    const z = document.createElement('div');
    z.className = 'hover-zone';
    z.setAttribute('aria-hidden', 'true');
    // Только hover для переключения
    z.addEventListener('mouseenter', () => swiper.slideTo(i, 0));
    zones.appendChild(z);
  }

  host.appendChild(zones);
}

function addHoverStrip(swiper) {
  const wrapper = swiper.el.closest('.product-card__image-wrapper');
  if (!wrapper) return;

  const strip = wrapper.nextElementSibling;
  if (!strip || !strip.matches('.hover-strip')) return;

  const count = swiper.slides.length;

  // очищаем и выставляем пустышку при 1 слайде
  strip.innerHTML = '';
  strip.classList.toggle('is-empty', count <= 1);
  if (count <= 1) return;

  const segs = [];
  for (let i = 0; i < count; i++) {
    const seg = document.createElement('button');
    seg.type = 'button';
    seg.className = 'hover-strip__seg';
    seg.setAttribute('aria-label', `Фото ${i + 1}`);
    seg.addEventListener('mouseenter', () => swiper.slideTo(i));
    seg.addEventListener('click', () => swiper.slideTo(i));
    strip.appendChild(seg);
    segs.push(seg);
  }

  const sync = () => {
    segs.forEach(
        (s, idx) => s.classList.toggle('is-active', idx === swiper.realIndex));
  };

  swiper.off('slideChange', sync);
  swiper.off('init', sync);
  swiper.on('init', sync);
  swiper.on('slideChange', sync);
  sync();
}

// Инициализация мини-галерей в карточках
document.querySelectorAll('.product-card__swiper').forEach(swEl => {
  const slides = swEl.querySelectorAll('.swiper-slide');
  if (slides.length <= 1) return;

  const sw = new Swiper(swEl, {
    slidesPerView: 1,
    speed: 300,
    allowTouchMove: isTouch,
    simulateTouch: isTouch,
    preventClicks: isTouch,
    preventClicksPropagation: isTouch
  });

  // кастомная полоска-пагинация (если используешь)
  if (typeof addHoverStrip === 'function') addHoverStrip(sw);
  // наши hover-зоны по всей картинке
  if (!isTouch && typeof addHoverZones === 'function') {
    addHoverZones(sw);  // внутри зон оставляем только mouseenter (см. ниже)
  }
});