const detailGuestKey = localStorage.getItem('sequenzGuestKey') || crypto.randomUUID();
localStorage.setItem('sequenzGuestKey', detailGuestKey);
const detailHeaders = {
  'Content-Type':'application/json',
  'X-Guest-Key':detailGuestKey,
  'X-CSRFToken':document.querySelector('meta[name="csrf-token"]').content,
};
const detailWon = value => `${Number(value).toLocaleString('ko-KR')}원`;
const detailEscape = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' })[char]);
const detailSafeUrl = value => { try { const url = new URL(value, location.origin); return ['http:','https:'].includes(url.protocol) ? url.href : '#'; } catch (_) { return '#'; } };
const detailAllowedTags = new Set(['A','B','BLOCKQUOTE','BR','DIV','EM','FIGCAPTION','FIGURE','H1','H2','H3','H4','H5','H6','HR','I','IMG','LI','OL','P','SPAN','STRONG','TABLE','TBODY','TD','TH','THEAD','TR','U','UL']);
const detailDroppedTags = new Set(['BUTTON','EMBED','FORM','IFRAME','INPUT','LINK','MATH','META','OBJECT','SCRIPT','STYLE','SVG','TEXTAREA']);

function detailSanitizeHtml(value) {
  const parsed = new DOMParser().parseFromString(String(value || ''), 'text/html');
  const container = document.createElement('div');

  const cleanNode = node => {
    if (node.nodeType === Node.TEXT_NODE) return document.createTextNode(node.textContent || '');
    if (node.nodeType !== Node.ELEMENT_NODE || detailDroppedTags.has(node.tagName)) return null;
    if (!detailAllowedTags.has(node.tagName)) {
      const fragment = document.createDocumentFragment();
      [...node.childNodes].forEach(child => { const clean = cleanNode(child); if (clean) fragment.appendChild(clean); });
      return fragment;
    }

    const element = document.createElement(node.tagName.toLowerCase());
    if (node.tagName === 'IMG') {
      const src = detailSafeUrl(node.getAttribute('src') || '');
      if (src === '#') return null;
      element.src = src;
      element.alt = node.getAttribute('alt') || '';
      element.loading = 'lazy';
      element.decoding = 'async';
    } else if (node.tagName === 'A') {
      const href = detailSafeUrl(node.getAttribute('href') || '');
      if (href !== '#') {
        element.href = href;
        element.target = '_blank';
        element.rel = 'noopener noreferrer nofollow';
      }
    } else if (['TD','TH'].includes(node.tagName)) {
      ['colspan','rowspan'].forEach(name => {
        const value = Number.parseInt(node.getAttribute(name), 10);
        if (Number.isInteger(value) && value > 0 && value <= 100) element.setAttribute(name, String(value));
      });
    }
    [...node.childNodes].forEach(child => { const clean = cleanNode(child); if (clean) element.appendChild(clean); });
    return element;
  };

  [...parsed.body.childNodes].forEach(node => { const clean = cleanNode(node); if (clean) container.appendChild(clean); });
  return container.innerHTML;
}

async function detailApi(url, options = {}) {
  const response = await fetch(url, { ...options, headers:{ ...detailHeaders, ...(options.headers || {}) } });
  if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.detail || '요청을 처리하지 못했습니다.'); }
  return response.status === 204 ? null : response.json();
}

function detailToast(message) {
  const toast = document.querySelector('#toast');
  toast.textContent = message; toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 1800);
}

async function loadProductPage() {
  const listingId = Number(document.body.dataset.listingId);
  const [item, reviews, cart, wishlist, related] = await Promise.all([
    detailApi(`/api/catalog/listings/${listingId}/`),
    detailApi(`/api/community/reviews/listing/${listingId}/`),
    detailApi('/api/commerce/cart/items/'),
    detailApi('/api/accounts/wishlist/').catch(() => ({ results:[] })),
    detailApi(`/api/catalog/listings/?related_to=${listingId}`),
  ]);
  document.querySelector('#detailCartCount').textContent = cart.summary.item_count;
  detailApi('/api/accounts/recently-viewed/', { method:'POST', body:JSON.stringify({ listing_id:listingId }) }).catch(() => {});
  const images = item.product.images || [];
  const available = item.variants.filter(variant => variant.status === 'active' && variant.stock_quantity > 0);
  const wished = wishlist.results.some(listing => Number(listing.id) === listingId);
  const gallery = images.length ? images.map((image, index) => `<figure class="pdp-image ${index === 0 ? 'primary' : ''}"><img src="${detailEscape(detailSafeUrl(image.image_url))}" alt="${detailEscape(image.alt_text || item.display_name)}" loading="${index === 0 ? 'eager' : 'lazy'}"></figure>`).join('') : '<div class="pdp-image placeholder">SEQUENZ</div>';
  const attributes = item.product.attributes?.map(attribute => `<div><dt>${detailEscape(attribute.name)}</dt><dd>${detailEscape(attribute.value)}</dd></div>`).join('') || '';
  const notice = item.product.information_notice?.fields || {};
  const reviewCards = reviews.results.map(review => `<article class="review-card pdp-review"><strong>${'★'.repeat(review.rating)}${'☆'.repeat(5-review.rating)}</strong><h4>${detailEscape(review.title)}</h4><p>${detailEscape(review.body)}</p>${(review.image_urls || []).length ? `<div class="review-images">${review.image_urls.map(url => `<img src="${detailEscape(detailSafeUrl(url))}" alt="후기 이미지" loading="lazy">`).join('')}</div>` : ''}<small>${detailEscape(review.reviewer_name)} · ${String(review.created_at).slice(0,10)}</small></article>`).join('') || '<p>아직 작성된 후기가 없습니다.</p>';

  document.querySelector('#productPageContent').innerHTML = `
    <nav class="pdp-breadcrumb"><a href="/">HOME</a><span>/</span><a href="/?category=${encodeURIComponent(item.product.category?.slug || '')}#products">${detailEscape(item.product.category?.name || 'SHOP')}</a></nav>
    <div class="pdp-layout">
      <section class="pdp-gallery" aria-label="상품 이미지">${gallery}</section>
      <aside class="pdp-purchase">
        <p class="brand-name">${detailEscape(item.product.brand?.name || 'SEQUENZ')}</p>
        <div class="pdp-title-row"><h1>${detailEscape(item.display_name)}</h1><button id="detailWishButton" class="pdp-wish" aria-label="찜하기">${wished ? '♥' : '♡'}</button></div>
        <p class="pdp-summary">${detailEscape(item.listing_summary || '')}</p>
        <p class="pdp-price">${item.consumer_price_snapshot > item.selling_price_snapshot ? `<del>${detailWon(item.consumer_price_snapshot)}</del>` : ''}<strong>${detailWon(item.selling_price_snapshot)}</strong></p>
        <div class="pdp-delivery"><span>배송</span><p>결제 완료 후 순차 출고<br><small>배송비는 주문서에서 최종 계산됩니다.</small></p></div>
        <label class="pdp-option-label">옵션 선택<select id="detailVariantSelect" class="variant-select"><option value="">사이즈·컬러를 선택하세요</option>${available.map(variant => `<option value="${Number(variant.id)}" data-price="${Number(item.selling_price_snapshot) + Number(variant.additional_amount_snapshot)}">${detailEscape(variant.option_display_name)} · 재고 ${Number(variant.stock_quantity)}</option>`).join('')}</select></label>
        <label class="pdp-quantity">수량 <input id="detailQuantity" type="number" min="1" value="1"></label>
        <div class="pdp-actions"><button id="detailAddCart" class="secondary-button">장바구니</button><button id="detailBuyNow" class="primary-button">바로 구매</button></div>
      </aside>
    </div>
    <section class="pdp-information">
      <div class="pdp-section"><p class="eyebrow">PRODUCT STORY</p><h2>상품 상세</h2><div class="product-description">${detailSanitizeHtml(item.listing_detail_html || item.product.detail_html || item.listing_summary || '')}</div></div>
      ${attributes ? `<div class="pdp-section"><h2>상품 속성</h2><dl class="product-attributes">${attributes}</dl></div>` : ''}
      ${Object.keys(notice).length ? `<div class="pdp-section"><h2>상품정보제공고시</h2><dl class="product-attributes">${Object.entries(notice).map(([name,value]) => `<div><dt>${detailEscape(name)}</dt><dd>${detailEscape(value)}</dd></div>`).join('')}</dl></div>` : ''}
      <div class="pdp-section"><div class="pdp-review-head"><h2>리뷰</h2><strong>${Number(reviews.summary.count)} / ${Number(reviews.summary.average_rating).toFixed(1)}</strong></div>${reviewCards}</div>
      <div class="pdp-section"><h2>관련 상품</h2><div class="related-products">${related.results.slice(0, 6).map(product => { const image = product.product.images?.find(item => item.is_primary) || product.product.images?.[0]; return `<a href="/products/${Number(product.id)}/"><div class="product-image">${image ? `<img src="${detailEscape(detailSafeUrl(image.image_url))}" alt="${detailEscape(product.display_name)}" loading="lazy">` : 'SEQUENZ'}</div><strong>${detailEscape(product.display_name)}</strong><span>${detailWon(product.selling_price_snapshot)}</span></a>`; }).join('') || '<p>관련 상품이 없습니다.</p>'}</div></div>
    </section>
    <div class="mobile-buy-bar"><button id="mobileAddCart" class="secondary-button">BAG</button><button id="mobileBuyNow" class="primary-button">구매하기</button></div>
  `;

  const addToCart = async buyNow => {
    const variantId = Number(document.querySelector('#detailVariantSelect').value);
    const quantity = Number(document.querySelector('#detailQuantity').value);
    if (!variantId) return detailToast('옵션을 선택해 주세요.');
    if (!Number.isInteger(quantity) || quantity < 1) return detailToast('수량을 확인해 주세요.');
    await detailApi('/api/commerce/cart/items/', { method:'POST', body:JSON.stringify({ listing_variant_id:variantId, quantity }) });
    const updatedCart = await detailApi('/api/commerce/cart/items/');
    document.querySelector('#detailCartCount').textContent = updatedCart.summary.item_count;
    if (buyNow) location.href = '/cart/'; else detailToast('장바구니에 담았습니다.');
  };
  document.querySelector('#detailAddCart').onclick = () => addToCart(false);
  document.querySelector('#detailBuyNow').onclick = () => addToCart(true);
  document.querySelector('#mobileAddCart').onclick = () => addToCart(false);
  document.querySelector('#mobileBuyNow').onclick = () => addToCart(true);
  document.querySelector('#detailWishButton').onclick = async event => {
    try {
      if (event.currentTarget.textContent === '♥') {
        await detailApi(`/api/accounts/wishlist/${listingId}/`, { method:'DELETE' }); event.currentTarget.textContent = '♡';
      } else {
        await detailApi('/api/accounts/wishlist/', { method:'POST', body:JSON.stringify({ listing_id:listingId }) }); event.currentTarget.textContent = '♥';
      }
    } catch (_) { detailToast('로그인 후 찜할 수 있습니다.'); }
  };
}

loadProductPage().catch(error => {
  document.querySelector('#productPageContent').innerHTML = `<div class="detail-error"><h1>상품을 불러오지 못했습니다.</h1><p>${detailEscape(error.message)}</p><a href="/">쇼핑 계속하기</a></div>`;
});
