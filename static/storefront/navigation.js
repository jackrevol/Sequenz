(() => {
  const sidebar = document.querySelector('#siteSidebar');
  const backdrop = document.querySelector('#sidebarBackdrop');
  const menuButton = document.querySelector('#menuButton');
  const closeButton = document.querySelector('#sidebarClose');
  const backgroundTargets = [...document.querySelectorAll('body > header, body > main, body > footer, body > nav.bottom-nav')];
  let previousFocus = null;
  if (!sidebar || !backdrop || !menuButton) return;

  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
  })[char]);

  const open = () => {
    previousFocus = document.activeElement;
    sidebar.classList.add('open');
    sidebar.setAttribute('aria-hidden', 'false');
    menuButton.setAttribute('aria-expanded', 'true');
    backdrop.hidden = false;
    requestAnimationFrame(() => backdrop.classList.add('open'));
    document.body.classList.add('sidebar-open');
    backgroundTargets.forEach(element => element.setAttribute('inert', ''));
    closeButton.focus();
  };
  const close = () => {
    sidebar.classList.remove('open');
    sidebar.setAttribute('aria-hidden', 'true');
    menuButton.setAttribute('aria-expanded', 'false');
    backdrop.classList.remove('open');
    document.body.classList.remove('sidebar-open');
    backgroundTargets.forEach(element => element.removeAttribute('inert'));
    setTimeout(() => { backdrop.hidden = true; }, 220);
    if (previousFocus?.focus) previousFocus.focus();
  };

  menuButton.addEventListener('click', open);
  closeButton.addEventListener('click', close);
  backdrop.addEventListener('click', close);
  sidebar.addEventListener('click', event => { if (event.target.closest('a')) close(); });
  document.addEventListener('keydown', event => {
    if (!sidebar.classList.contains('open')) return;
    if (event.key === 'Escape') return close();
    if (event.key !== 'Tab') return;
    const focusable = [...sidebar.querySelectorAll('a,button,summary,[tabindex]:not([tabindex="-1"])')].filter(element => !element.hidden);
    const first = focusable[0], last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });

  Promise.all([
    fetch('/api/catalog/categories/').then(response => response.json()),
    fetch('/api/catalog/brands/').then(response => response.json()),
  ]).then(([categories, brands]) => {
    const children = new Map();
    categories.forEach(category => {
      const key = category.parent_id || 0;
      children.set(key, [...(children.get(key) || []), category]);
    });
    const renderBranch = category => {
      const nested = children.get(category.id) || [];
      const link = `/?category=${encodeURIComponent(category.slug)}#products`;
      if (!nested.length) return `<a href="${link}">${escapeHtml(category.name)}</a>`;
      return `<details><summary>${escapeHtml(category.name)}</summary><div>${nested.map(child => `<a href="/?category=${encodeURIComponent(child.slug)}#products">${escapeHtml(child.name)}</a>`).join('')}</div></details>`;
    };
    document.querySelector('#sidebarCategories').innerHTML = `
      <a class="sidebar-primary-link" href="/#products">ALL PRODUCTS</a>
      ${(children.get(0) || []).map(renderBranch).join('')}
      <details><summary>BRANDS</summary><div>${brands.map(brand => `<a href="/?brand=${encodeURIComponent(brand.slug)}#products">${escapeHtml(brand.name)}</a>`).join('')}</div></details>
    `;
  }).catch(() => {
    document.querySelector('#sidebarCategories').innerHTML = '<a class="sidebar-primary-link" href="/#products">ALL PRODUCTS</a>';
  });
})();
