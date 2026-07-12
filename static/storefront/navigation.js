(() => {
  const sidebar = document.querySelector('#siteSidebar');
  const backdrop = document.querySelector('#sidebarBackdrop');
  const menuButton = document.querySelector('#menuButton');
  if (!sidebar || !backdrop || !menuButton) return;

  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'
  })[char]);

  const open = () => {
    sidebar.classList.add('open');
    sidebar.setAttribute('aria-hidden', 'false');
    backdrop.hidden = false;
    requestAnimationFrame(() => backdrop.classList.add('open'));
    document.body.classList.add('sidebar-open');
  };
  const close = () => {
    sidebar.classList.remove('open');
    sidebar.setAttribute('aria-hidden', 'true');
    backdrop.classList.remove('open');
    document.body.classList.remove('sidebar-open');
    setTimeout(() => { backdrop.hidden = true; }, 220);
  };

  menuButton.addEventListener('click', open);
  document.querySelector('#sidebarClose').addEventListener('click', close);
  backdrop.addEventListener('click', close);
  document.addEventListener('keydown', event => { if (event.key === 'Escape') close(); });

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
