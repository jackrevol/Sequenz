const initialParams = new URLSearchParams(location.search);
const state = { brand: initialParams.get('brand') || '', category: initialParams.get('category') || '', ordering: 'recommended', query: initialParams.get('q') || '', attributes: {}, minPrice:'', maxPrice:'', inStock:false, next: null, products: [], wishlist:new Set() };
const createGuestKey = () => {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  if (globalThis.crypto?.getRandomValues) {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = [...bytes].map(byte => byte.toString(16).padStart(2, '0')).join('');
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }
  return `guest-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};
const guestKey = localStorage.getItem('sequenzGuestKey') || createGuestKey();
localStorage.setItem('sequenzGuestKey', guestKey);
const headers = { 'Content-Type': 'application/json', 'X-Guest-Key': guestKey };
headers['X-CSRFToken'] = document.querySelector('meta[name="csrf-token"]').content;
const won = value => `${Number(value).toLocaleString('ko-KR')}원`;
const h = value => String(value ?? '').replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' })[char]);
const safeUrl = value => { try { const url = new URL(value, location.origin); return ['http:','https:'].includes(url.protocol) ? url.href : '#'; } catch (_) { return '#'; } };
const escapeData = value => Array.isArray(value) ? value.map(escapeData) : (value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).map(([key, item]) => [key, escapeData(item)])) : (typeof value === 'string' ? h(value) : value));
const htmlToText = value => new DOMParser().parseFromString(String(value || ''), 'text/html').body.textContent || '';

async function api(url, options = {}) {
  const requestHeaders = { ...headers, ...(options.headers || {}) };
  if (options.body instanceof FormData) delete requestHeaders['Content-Type'];
  const response = await fetch(url, { ...options, headers: requestHeaders });
  if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.detail || '요청을 처리하지 못했습니다.'); }
  return response.status === 204 ? null : response.json();
}

async function loadBrands() {
  const brands = await api('/api/catalog/brands/');
  const container = document.querySelector('#brands');
  container.innerHTML = `<button class="chip ${state.brand ? '' : 'active'}" data-brand="">ALL</button>` + brands.map(b => `<button class="chip ${state.brand === b.slug ? 'active' : ''}" data-brand="${h(b.slug)}">${h(b.name)}</button>`).join('');
  container.addEventListener('click', event => { if (!event.target.matches('.chip')) return; document.querySelectorAll('.chip').forEach(x => x.classList.remove('active')); event.target.classList.add('active'); state.brand = event.target.dataset.brand; loadProducts(); });
}

async function loadContent() {
  const [banners, collections, promotions, lookbooks] = await Promise.all([api('/api/content/banners/'), api('/api/content/collections/'), api('/api/content/promotions/'), api('/api/content/lookbooks/')]);
  if (banners.length) {
    const banner = banners[0], hero = document.querySelector('#heroBanner');
    document.querySelector('#heroTitle').textContent = banner.title;
    document.querySelector('#heroSubtitle').textContent = banner.subtitle;
    document.querySelector('#heroLink').textContent = `${banner.button_label || '자세히 보기'} →`;
    document.querySelector('#heroLink').href = banner.link_url ? safeUrl(banner.link_url) : '#products';
    const media = banner.mobile_media_url || banner.media_url;
    if (media && banner.media_type === 'image') {
      hero.classList.add('has-media');
      hero.style.backgroundImage = `linear-gradient(rgba(0,0,0,.08),rgba(0,0,0,.32)),url("${safeUrl(media)}")`;
    }
    if (media && banner.media_type === 'video') {
      hero.classList.add('has-media');
      hero.innerHTML = `<video class="hero-video" autoplay muted loop playsinline ${banner.poster_url ? `poster="${h(safeUrl(banner.poster_url))}"` : ''}><source src="${h(safeUrl(media))}"></video><div class="hero-copy"><p class="eyebrow">CURATED EVERYDAY</p><h1>${h(banner.title)}</h1><p>${h(banner.subtitle)}</p><a class="hero-link" href="${h(banner.link_url ? safeUrl(banner.link_url) : '#products')}">${h(banner.button_label || '자세히 보기')} →</a></div>`;
    }
  }
  const sections = [
    ...promotions.map(item => ({ ...item, label:'PROMOTION', type:'promotions', image:item.hero_image_url })),
    ...lookbooks.map(item => ({ ...item, label:'LOOKBOOK', type:'lookbooks', image:item.cover_image_url })),
    ...collections.map(item => ({ ...item, label:'COLLECTION', type:'collections', image:item.hero_image_url })),
  ];
  document.querySelector('#collectionSections').innerHTML = sections.map(collection => `<section class="collection-block"><div class="collection-head" ${collection.type ? `data-curated-type="${collection.type}" data-curated-slug="${h(collection.slug)}"` : ''} style="${collection.image ? `background-image:linear-gradient(rgba(0,0,0,.08),rgba(0,0,0,.2)),url('${h(safeUrl(collection.image))}')` : ''}"><p class="eyebrow">${collection.label}</p><h2>${h(collection.title)}</h2><p>${h(collection.summary)}</p></div><div class="collection-products">${collection.listings.slice(0,6).map(productCard).join('')}</div></section>`).join('');
}

async function openCuratedContent(type, slug) {
  location.href = `/content/${encodeURIComponent(type)}/${encodeURIComponent(slug)}/`;
}

async function openSupport() {
  const [notices, faqs, shipping, returns] = await Promise.all([
    api('/api/content/notices/'), api('/api/content/faqs/'),
    api('/api/content/policies/shipping/').catch(() => null), api('/api/content/policies/returns/').catch(() => null),
  ]);
  document.querySelector('#supportContent').innerHTML = `<p class="brand-name">CUSTOMER CARE</p><h2>고객센터</h2><section class="mypage-section"><h3>공지사항</h3>${notices.map(item => `<details><summary>${h(item.title)}</summary><p>${h(item.content)}</p></details>`).join('') || '<p>공지사항이 없습니다.</p>'}</section><section class="mypage-section"><h3>자주 묻는 질문</h3>${faqs.map(item => `<details><summary>[${h(item.category)}] ${h(item.question)}</summary><p>${h(item.answer)}</p></details>`).join('') || '<p>FAQ가 없습니다.</p>'}</section>${[shipping, returns].filter(Boolean).map(policy => `<section class="mypage-section"><h3>${h(policy.title)}</h3><p class="product-description">${h(policy.content)}</p><small>버전 ${h(policy.version)}</small></section>`).join('')}`;
  if (!document.querySelector('#supportDialog').open) document.querySelector('#supportDialog').showModal();
}

async function loadDiscovery() {
  const [filters, keywords] = await Promise.all([api('/api/catalog/filters/'), api('/api/catalog/search-keywords/')]);
  document.querySelector('#attributeFilters').innerHTML = filters.map(filter => `<label>${h(filter.name)}<select data-attribute="${h(filter.name)}"><option value="">전체</option>${filter.values.map(value => `<option value="${h(value)}">${h(value)}</option>`).join('')}</select></label>`).join('');
  const items = [...keywords.recommended, ...keywords.popular].filter((item, index, array) => array.findIndex(other => other.keyword === item.keyword) === index);
  document.querySelector('#searchKeywords').innerHTML = items.map(item => `<button class="chip" data-keyword="${h(item.keyword)}">${h(item.keyword)}</button>`).join('');
  renderRecentKeywords();
  document.querySelectorAll('[data-attribute]').forEach(select => { select.onchange = () => { if (select.value) state.attributes[select.dataset.attribute] = select.value; else delete state.attributes[select.dataset.attribute]; loadProducts(); }; });
}

function recentSearches() { return JSON.parse(localStorage.getItem('sequenzRecentSearches') || '[]'); }
function rememberSearch(keyword) {
  if (!keyword) return;
  localStorage.setItem('sequenzRecentSearches', JSON.stringify([keyword, ...recentSearches().filter(item => item !== keyword)].slice(0, 8)));
  renderRecentKeywords();
}
function renderRecentKeywords() {
  const recent = recentSearches();
  document.querySelector('#recentKeywords').innerHTML = recent.length ? `<span>최근</span>${recent.map(keyword => `<button class="chip" data-keyword="${h(keyword)}">${h(keyword)}</button>`).join('')}<button class="text-button" data-clear-recent="1">전체 삭제</button>` : '';
}

async function loadProducts(append = false) {
  const params = new URLSearchParams({ ordering: state.ordering });
  if (state.brand) params.set('brand', state.brand);
  if (state.category) params.set('category', state.category);
  if (state.query) params.set('q', state.query);
  if (state.minPrice) params.set('min_price', state.minPrice);
  if (state.maxPrice) params.set('max_price', state.maxPrice);
  if (state.inStock) params.set('in_stock', 'true');
  Object.entries(state.attributes).forEach(([name, value]) => params.append('attribute', `${name}:${value}`));
  const data = await api(append && state.next ? state.next : `/api/catalog/listings/?${params}`);
  state.products = append ? state.products.concat(data.results) : data.results;
  state.next = data.next;
  document.querySelector('#resultCount').textContent = `${data.count} ITEMS`;
  document.querySelector('#loadMoreButton').hidden = !data.next;
  document.querySelector('#productGrid').innerHTML = state.products.map(productCard).join('') || '<p>조건에 맞는 상품이 없습니다.</p>';
}

async function loadWishlist() {
  try { const data = await api('/api/accounts/wishlist/'); state.wishlist = new Set(data.results.map(item => Number(item.id))); }
  catch (_) { state.wishlist = new Set(); }
}

function productCard(item) {
  const brand = item.product.brand?.name || 'SEQUENZ';
  const labels = [item.is_new_label && 'NEW', item.is_sale_label && 'SALE'].filter(Boolean).join(' · ');
  const primaryImage = item.product.images?.find(image => image.is_primary) || item.product.images?.[0];
  const available = item.variants.filter(variant => variant.status === 'active' && Number(variant.stock_quantity) > 0);
  return `<article class="product-card" data-product-id="${Number(item.id)}"><button class="wish-button" data-wish="${Number(item.id)}" aria-label="찜하기">${state.wishlist.has(Number(item.id)) ? '♥' : '♡'}</button><a class="product-card-link" href="/products/${Number(item.id)}/"><div class="product-image">${primaryImage ? `<img src="${h(safeUrl(primaryImage.image_url))}" alt="${h(primaryImage.alt_text || item.display_name)}" loading="lazy">` : h(brand)}</div><p class="brand-name">${h(brand)}</p><h3>${h(item.display_name)}</h3><p class="price">${item.consumer_price_snapshot > item.selling_price_snapshot ? `<del>${won(item.consumer_price_snapshot)}</del>` : ''}${won(item.selling_price_snapshot)}</p><p class="labels">${h(labels || (available.length ? '' : 'SOLD OUT'))}</p></a>${available.length ? `<button class="quick-cart" data-quick-cart="${Number(item.id)}" data-variant="${available.length === 1 ? Number(available[0].id) : ''}">빠른 담기</button>` : ''}</article>`;
}

async function openProduct(id) {
  location.href = `/products/${Number(id)}/`;
}

async function openCart() {
  const data = await api('/api/commerce/cart/items/');
  document.querySelector('#cartItems').innerHTML = data.results.map(i => `<div class="cart-line"><div><h3>${h(i.display_name)}</h3><small>${h(i.option_display_name)}</small><p>${won(i.line_total)}</p><button class="remove" data-remove="${Number(i.id)}">삭제</button></div><div class="quantity"><button data-qty="${Number(i.id)}" data-value="${Number(i.quantity) - 1}">−</button><span>${Number(i.quantity)}</span><button data-qty="${Number(i.id)}" data-value="${Number(i.quantity) + 1}">＋</button></div></div>`).join('') || '<p>장바구니가 비어 있습니다.</p>';
  document.querySelector('#cartSummary').innerHTML = `<div><span>결제 예정 금액</span><strong>${won(data.summary.payment_amount)}</strong></div>${data.results.length ? '<button id="checkoutButton" class="primary-button">주문하기</button>' : ''}`;
  if (data.results.length) document.querySelector('#checkoutButton').onclick = () => openCheckout(data.summary);
  if (!document.querySelector('#cartDialog').open) document.querySelector('#cartDialog').showModal();
}

async function openCheckout(summary) {
  let member = null; try { member = await api('/api/accounts/me/'); } catch (_) {}
  const addresses = member ? await api('/api/accounts/addresses/') : { results:[] };
  const memberBenefits = member ? await api('/api/benefits/mine/') : null;
  member = escapeData(member);
  const address = escapeData(addresses.results?.[0] || {});
  document.querySelector('#checkoutContent').innerHTML = `<h2>CHECKOUT</h2><form id="checkoutForm" class="checkout-form"><input name="buyer_name" required placeholder="주문자명" value="${member?.name || ''}"><input name="buyer_phone" required placeholder="주문자 연락처" value="${member?.phone || ''}"><input name="buyer_email" type="email" placeholder="이메일" value="${member?.email || ''}"><input name="recipient_name" required placeholder="수취인명" value="${address.recipient_name || ''}"><input name="recipient_phone" required placeholder="수취인 연락처" value="${address.recipient_phone || ''}"><input name="postal_code" required placeholder="우편번호" value="${address.postal_code || ''}"><input name="address1" required placeholder="기본주소" value="${address.address1 || ''}"><input name="address2" placeholder="상세주소" value="${address.address2 || ''}"><input name="delivery_memo" placeholder="배송 메모" value="${address.delivery_memo || ''}">${member ? '<label class="checkbox-row"><input type="checkbox" name="save_address"> 이 배송지를 기본 배송지로 저장</label>' : ''}<fieldset class="payment-methods"><legend>결제수단</legend><div class="payment-grid"><label class="payment-option"><input type="radio" name="payment_method" value="CARD" checked><span>신용·체크카드</span></label><label class="payment-option"><input type="radio" name="payment_method" value="NAVERPAY"><span>네이버페이</span></label><label class="payment-option"><input type="radio" name="payment_method" value="KAKAOPAY"><span>카카오페이</span></label><label class="payment-option"><input type="radio" name="payment_method" value="TOSSPAY"><span>토스페이</span></label></div></fieldset><div class="checkout-total"><span>결제 예정 금액</span><span id="checkoutPaymentAmount">${won(summary.payment_amount)}</span></div><button class="primary-button"><span id="checkoutButtonAmount">${won(summary.payment_amount)}</span> 결제하기</button></form>`;
  if (memberBenefits) {
    const benefitFields = document.createElement('div'); benefitFields.className = 'benefit-fields';
    benefitFields.innerHTML = `<label>쿠폰<select name="coupon_code"><option value="">사용 안 함</option>${memberBenefits.coupons.filter(item => item.status === 'available').map(item => `<option value="${h(item.coupon.code)}">${h(item.coupon.name)}</option>`).join('')}</select></label><label>적립금 사용 <small>보유 ${Number(memberBenefits.account.point_balance).toLocaleString('ko-KR')}P</small><input type="number" name="point_to_use" min="0" max="${Number(memberBenefits.account.point_balance)}" value="0"></label>`;
    document.querySelector('#checkoutForm .payment-methods').before(benefitFields);
    const refreshQuote = async () => { const form = document.querySelector('#checkoutForm'); try { const quote = await api('/api/commerce/cart/benefit-quote/', { method:'POST', body:JSON.stringify({ coupon_code:form.coupon_code.value, point_to_use:Number(form.point_to_use.value || 0) }) }); document.querySelector('#checkoutPaymentAmount').textContent = won(quote.payment_amount); document.querySelector('#checkoutButtonAmount').textContent = won(quote.payment_amount); } catch (error) { toast(error.message); } };
    benefitFields.querySelector('select').onchange = refreshQuote;
    benefitFields.querySelector('input').onchange = refreshQuote;
  }
  document.querySelector('#checkoutForm').onsubmit = async event => { event.preventDefault(); const form = new FormData(event.target); const selectedMethod = form.get('payment_method'); const saveAddress = form.has('save_address'); form.delete('payment_method'); form.delete('save_address'); const data = Object.fromEntries(form); const button = event.submitter; button.disabled = true; try { if (member && saveAddress) await api('/api/accounts/addresses/', { method:'POST', body:JSON.stringify({ label:'기본 배송지', recipient_name:data.recipient_name, recipient_phone:data.recipient_phone, postal_code:data.postal_code, address1:data.address1, address2:data.address2, delivery_memo:data.delivery_memo, is_default:true }) }); const order = await api('/api/commerce/orders/', { method:'POST', body:JSON.stringify(data) }); const prepare = await api(`/api/commerce/payments/toss/prepare/${order.order_number}/`); await requestTossPayment(prepare, selectedMethod); } catch (error) { button.disabled = false; toast(error.message); } };
  if (!document.querySelector('#checkoutDialog').open) document.querySelector('#checkoutDialog').showModal();
}

async function requestTossPayment(prepare, selectedMethod) {
  if (!window.TossPayments) throw new Error('결제 SDK를 불러오지 못했습니다.');
  const payment = window.TossPayments(prepare.client_key).payment({ customerKey:prepare.customer_key });
  const card = selectedMethod === 'CARD' ? { flowMode:'DEFAULT' } : { flowMode:'DIRECT', easyPay:selectedMethod };
  await payment.requestPayment({ method:'CARD', card, amount:{ currency:'KRW', value:prepare.amount }, orderId:prepare.order_id, orderName:prepare.order_name, customerName:prepare.customer_name, customerEmail:prepare.customer_email, customerMobilePhone:prepare.customer_mobile_phone, successUrl:prepare.success_url, failUrl:prepare.fail_url });
}

async function handlePaymentRedirect() {
  const params = new URLSearchParams(location.search);
  if (params.get('payment') === 'success') {
    const orderId = params.get('orderId'), paymentKey = params.get('paymentKey'), amount = Number(params.get('amount'));
    if (!orderId || !paymentKey || !Number.isSafeInteger(amount)) return toast('결제 승인 정보가 올바르지 않습니다.');
    try { await api('/api/commerce/payments/toss/confirm/', { method:'POST', body:JSON.stringify({ order_number:orderId, payment_key:paymentKey, amount }) }); history.replaceState({}, '', '/'); toast('결제가 완료되었습니다.'); } catch (error) { toast(error.message); }
  } else if (params.get('payment') === 'fail') {
    toast(params.get('message') || '결제가 취소되었거나 실패했습니다.'); history.replaceState({}, '', '/');
  }
}

async function openAccount() {
  let member = null;
  try { member = await api('/api/accounts/me/'); } catch (_) {}
  const content = document.querySelector('#accountContent');
  if (member) {
    const [orders, wishlist, recent, inquiries, benefits, addresses, reviewable, points] = await Promise.all([
      api('/api/commerce/orders/mine/'), api('/api/accounts/wishlist/'), api('/api/accounts/recently-viewed/'), api('/api/community/inquiries/'), api('/api/benefits/mine/'), api('/api/accounts/addresses/'), api('/api/community/reviews/reviewable/'), api('/api/benefits/points/')
    ]);
    member = escapeData(member);
    orders.results = escapeData(orders.results); wishlist.results = escapeData(wishlist.results);
    recent.results = escapeData(recent.results); inquiries.results = escapeData(inquiries.results);
    content.innerHTML = `<div class="member-card"><p class="brand-name">MEMBER</p><h2>${member.name || member.username}님</h2><p>${member.email}</p><div class="social-status"><button class="social-button" disabled>카카오 · ${member.social_connections.kakao ? '연결됨' : '연동 준비 중'}</button><button class="social-button" disabled>네이버 · ${member.social_connections.naver ? '연결됨' : '연동 준비 중'}</button></div></div><section class="mypage-section"><h3>회원정보 수정</h3><form id="profileForm" class="auth-form"><input name="name" required value="${member.name}"><input name="email" type="email" required value="${member.email}"><input name="phone" required value="${member.phone}"><label class="checkbox-row"><input type="checkbox" name="marketing_agreed" ${member.marketing_agreed ? 'checked' : ''}> 마케팅 수신 동의</label><button class="primary-button">정보 저장</button></form></section><section class="mypage-section"><h3>배송지 관리</h3><div id="addressList">${addresses.results.map(address => addressEditor(address)).join('') || '<p>등록된 배송지가 없습니다.</p>'}</div></section><section class="mypage-section"><h3>주문내역</h3><div class="mini-list">${orders.results.slice(0,10).map(o => `<button class="mini-item text-button" data-order="${o.order_number}"><span>${o.order_number}<br><small>${o.status} · ${o.fulfillment_status}</small></span><strong>${won(o.payment_amount)}</strong></button>`).join('') || '<p>주문내역이 없습니다.</p>'}</div></section><section class="mypage-section"><h3>작성 가능한 후기</h3><div class="mini-list">${reviewable.results.map(item => `<button class="mini-item text-button" data-review-order="${item.order_number}" data-review-item="${item.order_item_id}">${h(item.product_name)} · ${h(item.option_name)}</button>`).join('') || '<p>작성 가능한 후기가 없습니다.</p>'}</div></section><section class="mypage-section"><h3>1:1 문의</h3><form id="inquiryForm" class="inquiry-form"><select name="order_id"><option value="">주문 선택 없음</option>${orders.results.map(o => `<option value="${o.id}">${o.order_number}</option>`).join('')}</select><select name="category"><option value="order">주문</option><option value="delivery">배송</option><option value="product">상품</option><option value="return">교환·반품</option><option value="other">기타</option></select><input name="subject" required placeholder="문의 제목"><textarea name="body" required placeholder="문의 내용"></textarea><button class="primary-button">문의 등록</button></form><div class="mini-list">${inquiries.results.map(i => `<div class="mini-item"><span>${i.subject}<br><small>${i.status}</small>${i.answer ? `<div class="inquiry-answer">${i.answer}</div>` : ''}</span></div>`).join('')}</div></section><section class="mypage-section"><h3>찜한 상품 전체</h3><div class="mini-list">${wishlist.results.map(i => `<div class="mini-item" data-product-id="${i.id}"><span>${i.display_name}</span><strong>${won(i.selling_price_snapshot)}</strong></div>`).join('') || '<p>찜한 상품이 없습니다.</p>'}</div></section><section class="mypage-section"><h3>최근 본 상품</h3><div class="mini-list">${recent.results.slice(0,5).map(i => `<div class="mini-item" data-product-id="${i.id}"><span>${i.display_name}</span><strong>${won(i.selling_price_snapshot)}</strong></div>`).join('') || '<p>최근 본 상품이 없습니다.</p>'}</div></section><button id="logoutButton" class="primary-button">로그아웃</button>`;
    const benefitCard = document.createElement('section'); benefitCard.className = 'mypage-section';
    benefitCard.innerHTML = `<h3>쿠폰·적립금·등급</h3><div class="member-card"><strong>${h(benefits.account.tier_name)}</strong><p>적립금 ${Number(benefits.account.point_balance).toLocaleString('ko-KR')}P · 쿠폰 ${benefits.coupons.filter(item => item.status === 'available').length}장</p></div><div class="mini-list">${benefits.coupons.map(item => `<p>${h(item.coupon.name)} · ${h(item.status)}</p>`).join('')}${(points.results || points).slice(0,10).map(point => `<p>${h(point.reason)} · ${Number(point.amount).toLocaleString('ko-KR')}P</p>`).join('')}</div>`;
    content.querySelector('.member-card').after(benefitCard);
    document.querySelector('#logoutButton').onclick = async () => { await api('/api/accounts/logout/', { method:'POST' }); document.querySelector('#accountDialog').close(); toast('로그아웃했습니다.'); };
    document.querySelector('#inquiryForm').onsubmit = async event => { event.preventDefault(); const payload = Object.fromEntries(new FormData(event.target)); if (!payload.order_id) delete payload.order_id; else payload.order_id = Number(payload.order_id); try { await api('/api/community/inquiries/', { method:'POST', body:JSON.stringify(payload) }); toast('문의를 등록했습니다.'); await openAccount(); } catch (error) { toast(error.message); } };
    document.querySelector('#profileForm').onsubmit = async event => { event.preventDefault(); const form = new FormData(event.target), payload = Object.fromEntries(form); payload.marketing_agreed = form.has('marketing_agreed'); try { await api('/api/accounts/me/', { method:'PATCH', body:JSON.stringify(payload) }); toast('회원정보를 수정했습니다.'); await openAccount(); } catch (error) { toast(error.message); } };
    document.querySelectorAll('[data-address-form]').forEach(form => { form.onsubmit = async event => { event.preventDefault(); const payload = Object.fromEntries(new FormData(form)); payload.is_default = form.querySelector('[name=is_default]').checked; try { await api(`/api/accounts/addresses/${form.dataset.addressForm}/`, { method:'PATCH', body:JSON.stringify(payload) }); toast('배송지를 수정했습니다.'); await openAccount(); } catch (error) { toast(error.message); } }; });
    document.querySelectorAll('[data-address-delete]').forEach(button => { button.onclick = async () => { if (!confirm('이 배송지를 삭제할까요?')) return; await api(`/api/accounts/addresses/${button.dataset.addressDelete}/`, { method:'DELETE' }); await openAccount(); }; });
  } else {
    renderLogin();
  }
  if (!document.querySelector('#accountDialog').open) document.querySelector('#accountDialog').showModal();
}

async function openOrder(orderNumber) {
  const [orderData, claimData] = await Promise.all([api(`/api/commerce/orders/${orderNumber}/`), api(`/api/commerce/orders/${orderNumber}/claims/`)]);
  const order = escapeData(orderData), claims = escapeData(claimData.results);
  const canCancel = order.status === 'paid' && !['shipped','in_transit','delivered','returned'].includes(order.fulfillment_status);
  const canReturn = order.status === 'paid' && ['shipped','in_transit','delivered'].includes(order.fulfillment_status);
  document.querySelector('#orderContent').innerHTML = `<p class="brand-name">ORDER DETAIL</p><h2>${order.order_number}</h2><span class="status-badge">${order.status} · ${order.fulfillment_status}</span><div class="order-items">${order.items.map(item => `<article class="order-item"><strong>${item.product_name_snapshot}</strong><p>${item.option_name_snapshot} · 주문 ${item.ordered_quantity}개${item.cancelled_quantity ? ` · 취소 ${item.cancelled_quantity}개` : ''}</p><p>${won(item.line_total)}</p>${canReturn ? `<button class="text-button" data-claim-type="exchange" data-claim-item="${item.id}" data-claim-max="${item.ordered_quantity}">교환 신청</button><button class="text-button" data-claim-type="return" data-claim-item="${item.id}" data-claim-max="${item.ordered_quantity}">반품 신청</button>` : ''}${order.fulfillment_status === 'delivered' && item.review_status !== 'written' ? `<button class="text-button" data-review-item="${item.id}">후기 작성</button><div id="reviewForm-${item.id}"></div>` : ''}</article>`).join('')}</div><div class="checkout-total"><span>결제금액</span><span>${won(order.payment_amount)}</span></div>${order.status === 'payment_pending' ? '<select id="retryPaymentMethod" class="variant-select"><option value="CARD">신용·체크카드</option><option value="NAVERPAY">네이버페이</option><option value="KAKAOPAY">카카오페이</option><option value="TOSSPAY">토스페이</option></select><button id="retryPaymentButton" class="primary-button">결제 다시 시도</button>' : ''}${canCancel ? '<button id="cancelOrderButton" class="primary-button">전체 주문취소</button>' : ''}<section class="claim-history"><h3>교환·반품·취소 현황</h3>${claims.map(claim => `<p>${claim.claim_type} · ${claim.status}<br><small>${claim.reason}${claim.refund_amount ? ` · 환불 ${won(claim.refund_amount)}` : ''}</small></p>`).join('') || '<p>신청 내역이 없습니다.</p>'}</section>`;
  if (order.shipments?.length) {
    const shipmentBox = document.createElement('div'); shipmentBox.className = 'shipment-box';
    order.shipments.forEach(shipment => { const line = document.createElement('p'); line.textContent = `${shipment.carrier_name || shipment.carrier_code || '택배사'} · ${shipment.tracking_number} · ${shipment.status}`; shipmentBox.append(line); });
    document.querySelector('#orderContent .order-items').before(shipmentBox);
  }
  if (canCancel) document.querySelector('#cancelOrderButton').onclick = async () => { const reason = prompt('취소 사유를 입력해 주세요.'); if (!reason) return; try { await api(`/api/commerce/orders/${order.order_number}/cancel/`, { method:'POST', body:JSON.stringify({ reason }) }); toast('주문을 취소했습니다.'); await openOrder(order.order_number); } catch (error) { toast(error.message); } };
  document.querySelectorAll('[data-claim-type]').forEach(button => { button.onclick = async () => { const labels = { exchange:'교환', return:'반품' }; const quantity = Number(prompt(`${labels[button.dataset.claimType]} 수량 (최대 ${button.dataset.claimMax})`, '1')); if (!Number.isInteger(quantity) || quantity < 1 || quantity > Number(button.dataset.claimMax)) return toast('신청 수량을 확인해 주세요.'); const reason = prompt(`${labels[button.dataset.claimType]} 사유를 입력해 주세요.`); if (!reason) return; try { await api(`/api/commerce/orders/${order.order_number}/claims/`, { method:'POST', body:JSON.stringify({ claim_type:button.dataset.claimType, reason, items:[{ order_item_id:Number(button.dataset.claimItem), quantity }] }) }); toast(`${labels[button.dataset.claimType]} 신청을 처리했습니다.`); await openOrder(order.order_number); } catch (error) { toast(error.message); } }; });
  if (order.status === 'payment_pending') document.querySelector('#retryPaymentButton').onclick = async () => { try { const prepare = await api(`/api/commerce/payments/toss/prepare/${order.order_number}/`); await requestTossPayment(prepare, document.querySelector('#retryPaymentMethod').value); } catch (error) { toast(error.message); } };
  if (!document.querySelector('#orderDialog').open) document.querySelector('#orderDialog').showModal();
}

function showReviewForm(orderItemId) {
  document.querySelector(`#reviewForm-${orderItemId}`).innerHTML = `<form class="review-form" data-review-form="${orderItemId}"><select name="rating"><option value="5">★★★★★</option><option value="4">★★★★☆</option><option value="3">★★★☆☆</option><option value="2">★★☆☆☆</option><option value="1">★☆☆☆☆</option></select><input name="title" placeholder="후기 제목"><textarea name="body" required placeholder="상품 후기를 작성해 주세요."></textarea><input name="images" type="file" accept="image/*" multiple><button class="primary-button">후기 등록</button></form>`;
}

function addressEditor(address) {
  return `<form class="address-editor" data-address-form="${Number(address.id)}"><input name="label" value="${h(address.label)}"><input name="recipient_name" value="${h(address.recipient_name)}"><input name="recipient_phone" value="${h(address.recipient_phone)}"><input name="postal_code" value="${h(address.postal_code)}"><input name="address1" value="${h(address.address1)}"><input name="address2" value="${h(address.address2)}"><input name="delivery_memo" value="${h(address.delivery_memo)}"><label class="checkbox-row"><input name="is_default" type="checkbox" ${address.is_default ? 'checked' : ''}> 기본 배송지</label><button class="text-button">수정</button><button type="button" class="text-button" data-address-delete="${Number(address.id)}">삭제</button></form>`;
}

function authTabs(active) {
  return `<div class="auth-tabs"><button data-auth-tab="login" class="${active === 'login' ? 'active' : ''}">로그인</button><button data-auth-tab="register" class="${active === 'register' ? 'active' : ''}">회원가입</button></div>`;
}

function renderLogin() {
  document.querySelector('#accountContent').innerHTML = `${authTabs('login')}<form id="loginForm" class="auth-form"><input name="username" required placeholder="아이디" autocomplete="username"><input name="password" type="password" required placeholder="비밀번호" autocomplete="current-password"><button class="primary-button">로그인</button></form><section class="mypage-section"><h3>비회원 주문조회</h3><form id="guestOrderLookupForm" class="auth-form"><input name="order_number" required placeholder="주문번호"><input name="buyer_name" required placeholder="주문자명"><input name="buyer_phone" required placeholder="주문자 연락처"><button class="primary-button">주문조회</button></form></section>`;
  document.querySelector('#loginForm').onsubmit = async event => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); try { await api('/api/accounts/login/', { method:'POST', body:JSON.stringify(data) }); await Promise.all([refreshCartCount(), loadWishlist()]); await loadProducts(); await openAccount(); toast('로그인했습니다.'); } catch (error) { toast(error.message); } };
  document.querySelector('#guestOrderLookupForm').onsubmit = async event => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); try { const order = await api('/api/commerce/orders/guest-lookup/', { method:'POST', body:JSON.stringify(data) }); document.querySelector('#accountDialog').close(); await renderGuestOrder(order); } catch (error) { toast(error.message); } };
}

async function renderGuestOrder(orderData) {
  const order = escapeData(orderData);
  document.querySelector('#orderContent').innerHTML = `<p class="brand-name">GUEST ORDER</p><h2>${order.order_number}</h2><span class="status-badge">${order.status} · ${order.fulfillment_status}</span><div class="order-items">${order.items.map(item => `<article class="order-item"><strong>${item.product_name_snapshot}</strong><p>${item.option_name_snapshot} · ${item.ordered_quantity}개</p><p>${won(item.line_total)}</p></article>`).join('')}</div><div class="checkout-total"><span>결제금액</span><span>${won(order.payment_amount)}</span></div>`;
  if (!document.querySelector('#orderDialog').open) document.querySelector('#orderDialog').showModal();
}

function renderRegister() {
  document.querySelector('#accountContent').innerHTML = `${authTabs('register')}<form id="registerForm" class="auth-form"><input name="username" required placeholder="아이디" autocomplete="username"><input name="email" type="email" required placeholder="이메일"><input name="password" type="password" minlength="8" required placeholder="비밀번호 (8자 이상)" autocomplete="new-password"><input name="name" required placeholder="이름"><input name="phone" required placeholder="휴대폰 번호"><label class="checkbox-row"><input name="terms_agreed" type="checkbox" required> 필수 약관에 동의합니다.</label><label class="checkbox-row"><input name="marketing_agreed" type="checkbox"> 마케팅 정보 수신에 동의합니다.</label><button class="primary-button">회원가입</button></form>`;
  document.querySelector('#registerForm').onsubmit = async event => { event.preventDefault(); const form = new FormData(event.target); const data = Object.fromEntries(form); data.terms_agreed = form.has('terms_agreed'); data.marketing_agreed = form.has('marketing_agreed'); try { await api('/api/accounts/register/', { method:'POST', body:JSON.stringify(data) }); await Promise.all([refreshCartCount(), loadWishlist()]); await loadProducts(); await openAccount(); toast('가입을 완료했습니다.'); } catch (error) { toast(error.message); } };
}

document.addEventListener('click', async event => {
  if (event.target.dataset.wish) {
    event.stopPropagation();
    const listingId = Number(event.target.dataset.wish);
    try { if (state.wishlist.has(listingId)) { await api(`/api/accounts/wishlist/${listingId}/`, { method:'DELETE' }); state.wishlist.delete(listingId); event.target.textContent = '♡'; toast('찜 목록에서 삭제했습니다.'); } else { await api('/api/accounts/wishlist/', { method:'POST', body:JSON.stringify({ listing_id:listingId }) }); state.wishlist.add(listingId); event.target.textContent = '♥'; toast('찜 목록에 추가했습니다.'); } } catch (_) { toast('로그인 후 찜할 수 있습니다.'); }
    return;
  }
  if (event.target.dataset.quickCart) {
    event.stopPropagation();
    const variantId = Number(event.target.dataset.variant);
    if (!variantId) return openProduct(event.target.dataset.quickCart);
    try { await api('/api/commerce/cart/items/', { method:'POST', body:JSON.stringify({ listing_variant_id:variantId, quantity:1 }) }); await refreshCartCount(); toast('장바구니에 담았습니다.'); } catch (error) { toast(error.message); }
    return;
  }
  const card = event.target.closest('[data-product-id]'); if (card) return openProduct(card.dataset.productId);
  if (event.target.dataset.close) document.querySelector(`#${event.target.dataset.close}`).close();
  if (event.target.dataset.remove) { await api(`/api/commerce/cart/items/${event.target.dataset.remove}/`, { method:'DELETE' }); await openCart(); await refreshCartCount(); }
  if (event.target.dataset.qty) { const value = Number(event.target.dataset.value); if (value < 1) return; await api(`/api/commerce/cart/items/${event.target.dataset.qty}/`, { method:'PATCH', body:JSON.stringify({ quantity:value }) }); await openCart(); await refreshCartCount(); }
  if (event.target.dataset.authTab === 'login') renderLogin();
  if (event.target.dataset.authTab === 'register') renderRegister();
  if (event.target.dataset.order) openOrder(event.target.dataset.order);
  if (event.target.dataset.reviewOrder) { document.querySelector('#accountDialog').close(); await openOrder(event.target.dataset.reviewOrder); showReviewForm(event.target.dataset.reviewItem); return; }
  if (event.target.dataset.reviewItem) showReviewForm(event.target.dataset.reviewItem);
  if (event.target.dataset.keyword) { state.query = event.target.dataset.keyword; document.querySelector('#searchInput').value = state.query; rememberSearch(state.query); loadProducts(); }
  if (event.target.dataset.clearRecent) { localStorage.removeItem('sequenzRecentSearches'); renderRecentKeywords(); }
  const curated = event.target.closest('[data-curated-type]'); if (curated) openCuratedContent(curated.dataset.curatedType, curated.dataset.curatedSlug);
  const reviewForm = event.target.closest('[data-review-form]');
});

document.addEventListener('submit', async event => {
  if (!event.target.dataset.reviewForm) return;
  event.preventDefault();
  const data = new FormData(event.target); data.set('order_item_id', event.target.dataset.reviewForm);
  try { await api('/api/community/reviews/', { method:'POST', body:data }); event.target.innerHTML = '<p>후기가 등록되었습니다.</p>'; toast('후기를 등록했습니다.'); } catch (error) { toast(error.message); }
});

async function refreshCartCount() { const data = await api('/api/commerce/cart/items/'); document.querySelector('#cartCount').textContent = data.summary.item_count; }
function toast(message) { const el = document.querySelector('#toast'); el.textContent = message; el.classList.add('show'); setTimeout(() => el.classList.remove('show'), 1800); }
document.querySelector('#loadMoreButton').onclick = () => loadProducts(true);
document.querySelector('#sortSelect').onchange = event => { state.ordering = event.target.value; loadProducts(); };
document.querySelector('#searchInput').value = state.query;
let timer; document.querySelector('#searchInput').oninput = event => { clearTimeout(timer); timer = setTimeout(() => { state.query = event.target.value.trim(); if (state.query) rememberSearch(state.query); loadProducts(); }, 350); };
['minPriceFilter','maxPriceFilter'].forEach(id => { document.querySelector(`#${id}`).onchange = event => { state[id === 'minPriceFilter' ? 'minPrice' : 'maxPrice'] = event.target.value; loadProducts(); }; });
document.querySelector('#inStockFilter').onchange = event => { state.inStock = event.target.checked; loadProducts(); };
loadWishlist().finally(() => Promise.all([loadBrands(), loadProducts(), loadContent(), loadDiscovery(), refreshCartCount()]).catch(error => toast(error.message)));
