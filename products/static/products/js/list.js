// Синхронизация множества чекбоксов -> hidden CSV
function syncMultiToHidden(groupName, hiddenName, formId) {
  const form = document.getElementById(formId);
  const boxes = form.querySelectorAll('input[name="' + groupName + '"]');
  const values = Array.from(boxes).filter(b => b.checked).map(b => b.value);
  const hidden = form.querySelector('input[name="' + hiddenName + '"]');
  if (hidden) hidden.value = values.join(',');
}

// Чипсы — точечный сброс
function setupChips() {
  const chips = document.querySelectorAll('.chip[data-clear]');
  if (!chips.length) return;
  const form = document.getElementById('filters-form');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      const payload = chip.getAttribute(
          'data-clear');  // варианты: "in_stock" | "price_min" | "brands:slug"
                          // | "a_color:Black"
      if (!payload) return;
      const [name, value] = payload.split(':');

      // простой кейс: одно поле
      if (!value) {
        const el = form.querySelector('[name="' + name + '"]');
        if (!el) return;
        if (el.type === 'checkbox')
          el.checked = false;
        else if (el.type === 'radio') {
          // для радио — выставим пустое (Любое)
          const any = form.querySelector(
              'input[type="radio"][name="' + name + '"][value=""]');
          if (any) any.checked = true;
        } else {
          el.value = '';
        }
      } else {
        // часть CSV: бренды и text-атрибуты
        const hidden = form.querySelector('input[name="' + name + '"]');
        if (hidden) {
          const arr = (hidden.value || '')
                          .split(',')
                          .filter(Boolean)
                          .filter(v => v !== value);
          hidden.value = arr.join(',');
        }
        // синхронизируем чекбокс в визуальной группе _multi
        const groupName = name + '_multi';
        const box = form.querySelector(
            'input[name="' + groupName + '"][value="' + CSS.escape(value) +
            '"]');
        if (box) box.checked = false;
        // поддержка brands_multi
        if (name === 'brands') {
          const bx = form.querySelector(
              'input[name="brands_multi"][value="' + CSS.escape(value) + '"]');
          if (bx) bx.checked = false;
        }
      }
      form.submit();
    });
  });
}

// Off-canvas фильтры на мобильных
function setupOffCanvas() {
  const toggleButtons = document.querySelectorAll('[data-toggle="filters"]');
  const filters = document.getElementById('filters');
  if (!filters) return;
  toggleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      filters.classList.toggle('open');
      document.body.style.overflow =
          filters.classList.contains('open') ? 'hidden' : '';
    });
  });
  // Закрытие по клику вне (только мобила)
  document.addEventListener('click', (e) => {
    if (window.matchMedia('(max-width: 1024px)').matches) {
      const open = filters.classList.contains('open');
      if (!open) return;
      const inside = filters.contains(e.target) ||
          (e.target.closest('[data-toggle="filters"]'));
      if (!inside) {
        filters.classList.remove('open');
        document.body.style.overflow = '';
      }
    }
  });
}

// Автосабмит сортировки (на случай, если кто-то убрал onchange в шаблоне)
function setupSort() {
  const sort = document.getElementById('sort');
  const form = document.getElementById('filters-form');
  if (sort && form) {
    sort.addEventListener('change', () => form.submit());
  }
}

function toggleSortControls() {
  const m = document.getElementById('sort-m');  // mobile select
  const d = document.getElementById('sort-d');  // desktop select
  if (!m || !d) return;

  const isMobile = window.matchMedia('(max-width: 1024px)').matches;

  if (isMobile) {
    // Мобилка рулит: мобильному селекту даём name="sort", десктопный выключаем
    m.name = 'sort';
    m.setAttribute('form', 'filters-form');
    d.removeAttribute('name');
    d.removeAttribute('form');
  } else {
    // Десктоп рулит
    d.name = 'sort';
    d.setAttribute('form', 'filters-form');
    m.removeAttribute('name');
    m.removeAttribute('form');
  }
}

// Синхронизация значений между двумя селектами
function setupSortSync() {
  const form = document.getElementById('filters-form');
  const m = document.getElementById('sort-m');
  const d = document.getElementById('sort-d');
  if (!m || !d || !form) return;

  const sync = (from, to) => {
    to.value = from.value;
  };

  m.addEventListener('change', () => {
    sync(m, d);
    form.submit();
  });
  d.addEventListener('change', () => {
    sync(d, m);
    form.submit();
  });
}

// При сабмите удаляем пустые price_* и possible duplicate page
function cleanQueryOnSubmit() {
  const form = document.getElementById('filters-form');
  if (!form) return;
  form.addEventListener('submit', (e) => {
    const pruneEmpty = ['price_min', 'price_max'];
    pruneEmpty.forEach(name => {
      const el = form.elements[name];
      if (el && !el.value) el.disabled = true;
    });
    // На всякий: убираем скрытые дубликаты page, если где-то завелись
    const pages = form.querySelectorAll('input[name="page"]');
    if (pages.length > 1) {
      pages.forEach((el, i) => {
        if (i < pages.length - 1) el.parentNode.removeChild(el);
      });
    }
  });
}

// init
document.addEventListener('DOMContentLoaded', () => {
  setupChips();
  setupOffCanvas();
  setupSort();
  toggleSortControls();
  setupSortSync();
  cleanQueryOnSubmit();
  window.addEventListener('resize', toggleSortControls);
});
