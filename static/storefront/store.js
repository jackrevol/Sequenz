const state = { brand: '', ordering: 'recommended', query: '', next: null, products: [], wishlist:new Set() };
const guestKey = localStorage.getItem('sequenzGuestKey') || crypto.randomUUID();
localStorage.setItem('sequenzGuestKey', guestKey);
const headers = { 'Content-Type': 'application/json', 'X-Guest-Key': guestKey };
headers['X-CSRFToken'] = document.querySelector('meta[name="csrf-token"]').content;
const won = value => `${Number(value).toLocaleString('ko-KR')}원`;
const h = value => String(value ?? '').replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' })[char]);
const safeUrl = value => { try { const url = new URL(value, location.origin); return ['http:','https:'].includes(url.protocol) ? url.href : '#'; } catch (_) { return '#'; } };
const escapeData = value => Array.isArray(value) ? value.map(escapeData) : (value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).map(([key, item]) => [key, escapeData(item)])) : (typeof value === 'string' ? h(value) : value));
const htmlToText = value => new DOMParser().parseFromString(String(value || ''), 'text/html').body.textContent || '';

async function api(url, options = {}) {
  const response = await fetch(url, { ...options, headers: { ...headers, ...(options.headers || {}) } });
  if (!response.ok) { const error = await response.json().catch(() => ({})); throw new Error(error.detail || '요청을 처리하지 못했습니다.'); }
  return response.status === 204 ? null : response.json();
}

async function loadBrands() {
  const brands = await api('/api/catalog/brands/');
  const container = document.querySelector('#brands');
  container.innerHTML = `<button class="chip active" data-brand="">ALL</button>` + brands.map(b => `<button class="chip" data-brand="${h(b.slug)}">${h(b.name)}</button>`).join('');
  container.addEventListener('click', event => { if (!event.target.matches('.chip')) return; document.querySelectorAll('.chip').forEach(x => x.classList.remove('active')); event.target.classList.add('active'); state.brand = event.target.dataset.brand; loadProducts(); });
}

async function loadContent() {
  const [banners, collections] = await Promise.all([api('/api/content/banners/'), api('/api/content/collections/')]);
  if (banners.length) {
    const banner = banners[0], hero = document.querySelector('#heroBanner');
    document.querySelector('#heroTitle').textContent = banner.title;
    document.querySelector('#heroSubtitle').textContent = banner.subtitle;
    document.querySelector('#heroLink').textContent = `${banner.button_label || '자세히 보기'} →`;
    document.querySelector('#heroLink').href = banner.link_url ? safeUrl(banner.link_url) : '#products';
    const media = banner.mobile_media_url || banner.media_url;
    if (banner.media_type === 'image') hero.style.backgroundImage = `linear-gradient(rgba(0,0,0,.08),rgba(0,0,0,.22)),url("${safeUrl(media)}")`;
    if (banner.media_type === 'video') hero.innerHTML = `<video class="hero-video" autoplay muted loop playsinline poster="${h(safeUrl(banner.poster_url || ''))}"><source src="${h(safeUrl(media))}"></video><div class="hero-copy"><p class="eyebrow">CURATED EVERYDAY</p><h1>${h(banner.title)}</h1><p>${h(banner.subtitle)}</p><a class="hero-link" href="${h(banner.link_url ? safeUrl(banner.link_url) : '#products')}">${h(banner.button_label || '자세히 보기')} →</a></div>`;
  }
  document.querySelector('#collectionSections').innerHTML = collections.map(collection => `<section class="collection-block"><div class="collection-head" style="${collection.hero_image_url ? `background-image:linear-gradient(rgba(0,0,0,.08),rgba(0,0,0,.2)),url('${h(safeUrl(collection.hero_image_url))}')` : ''}"><p class="eyebrow">COLLECTION</p><h2>${h(collection.title)}</h2><p>${h(collection.summary)}</p></div><div class="collection-products">${collection.listings.slice(0,6).map(productCard).join('')}</div></section>`).join('');
}

async function loadProducts(append = false) {
  const params = new URLSearchParams({ ordering: state.ordering });
  if (state.brand) params.set('brand', state.brand);
  if (state.query) params.set('q', state.query);
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
  return `<article class="product-card" data-product-id="${Number(item.id)}"><button class="wish-button" data-wish="${Number(item.id)}" aria-label="찜하기">${state.wishlist.has(Number(item.id)) ? '♥' : '♡'}</button><div class="product-image">${primaryImage ? `<img src="${h(safeUrl(primaryImage.image_url))}" alt="${h(primaryImage.alt_text || item.display_name)}" loading="lazy">` : h(brand)}</div><p class="brand-name">${h(brand)}</p><h3>${h(item.display_name)}</h3><p class="price">${item.consumer_price_snapshot > item.selling_price_snapshot ? `<del>${won(item.consumer_price_snapshot)}</del>` : ''}${won(item.selling_price_snapshot)}</p><p class="labels">${h(labels)}</p></article>`;
}

async function openProduct(id) {
  const [item, reviews] = await Promise.all([api(`/api/catalog/listings/${id}/`), api(`/api/community/reviews/listing/${id}/`)]);
  api('/api/accounts/recently-viewed/', { method:'POST', body:JSON.stringify({ listing_id:Number(id) }) }).catch(() => {});
  const available = item.variants.filter(v => v.status === 'active' && v.stock_quantity > 0);
  const detailImage = item.product.images?.find(image => image.is_primary) || item.product.images?.[0];
  const detailVisual = detailImage ? `<img src="${h(safeUrl(detailImage.image_url))}" alt="${h(detailImage.alt_text || item.display_name)}">` : h(item.product.brand?.name || 'SEQUENZ');
  document.querySelector('#productDetail').innerHTML = `<div class="detail-visual">${detailVisual}</div><p class="brand-name">${h(item.product.brand?.name || '')}</p><h2>${h(item.display_name)}</h2><p>${h(item.listing_summary || '')}</p><p class="detail-price">${won(item.selling_price_snapshot)}</p><select id="variantSelect" class="variant-select"><option value="">옵션을 선택하세요</option>${available.map(v => `<option value="${Number(v.id)}">${h(v.option_display_name)} · 재고 ${Number(v.stock_quantity)}</option>`).join('')}</select><button id="addCartButton" class="primary-button">장바구니 담기</button><div class="review-summary">후기 ${Number(reviews.summary.count)} · 평점 ${Number(reviews.summary.average_rating)}</div>${reviews.results.map(review => `<article class="review-card"><strong>${'★'.repeat(review.rating)}${'☆'.repeat(5-review.rating)}</strong><p>${h(review.title || '')}</p><p>${h(review.body)}</p><small>${h(review.reviewer_name)}</small></article>`).join('') || '<p>아직 작성된 후기가 없습니다.</p>'}`;
  const description = document.createElement('div'); description.className = 'product-description'; description.textContent = htmlToText(item.listing_detail_html || item.product.detail_html); document.querySelector('#productDetail .detail-price').before(description);
  document.querySelector('#productDialog').showModal();
  document.querySelector('#addCartButton').onclick = async () => { const id = document.querySelector('#variantSelect').value; if (!id) return toast('옵션을 선택해 주세요.'); await api('/api/commerce/cart/items/', { method:'POST', body:JSON.stringify({ listing_variant_id:Number(id), quantity:1 }) }); await refreshCartCount(); toast('장바구니에 담았습니다.'); };
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
  member = escapeData(member);
  const address = escapeData(addresses.results?.[0] || {});
  document.querySelector('#checkoutContent').innerHTML = `<h2>CHECKOUT</h2><form id="checkoutForm" class="checkout-form"><input name="buyer_name" required placeholder="주문자명" value="${member?.name || ''}"><input name="buyer_phone" required placeholder="주문자 연락처" value="${member?.phone || ''}"><input name="buyer_email" type="email" placeholder="이메일" value="${member?.email || ''}"><input name="recipient_name" required placeholder="수취인명" value="${address.recipient_name || ''}"><input name="recipient_phone" required placeholder="수취인 연락처" value="${address.recipient_phone || ''}"><input name="postal_code" required placeholder="우편번호" value="${address.postal_code || ''}"><input name="address1" required placeholder="기본주소" value="${address.address1 || ''}"><input name="address2" placeholder="상세주소" value="${address.address2 || ''}"><input name="delivery_memo" placeholder="배송 메모" value="${address.delivery_memo || ''}">${member ? '<label class="checkbox-row"><input type="checkbox" name="save_address"> 이 배송지를 기본 배송지로 저장</label>' : ''}<fieldset class="payment-methods"><legend>결제수단</legend><div class="payment-grid"><label class="payment-option"><input type="radio" name="payment_method" value="CARD" checked><span>신용·체크카드</span></label><label class="payment-option"><input type="radio" name="payment_method" value="NAVERPAY"><span>네이버페이</span></label><label class="payment-option"><input type="radio" name="payment_method" value="KAKAOPAY"><span>카카오페이</span></label><label class="payment-option"><input type="radio" name="payment_method" value="TOSSPAY"><span>토스페이</span></label></div></fieldset><div class="checkout-total"><span>결제 예정 금액</span><span>${won(summary.payment_amount)}</span></div><button class="primary-button">${won(summary.payment_amount)} 결제하기</button></form>`;
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
    const [orders, wishlist, recent, inquiries] = await Promise.all([
      api('/api/commerce/orders/mine/'), api('/api/accounts/wishlist/'), api('/api/accounts/recently-viewed/'), api('/api/community/inquiries/')
    ]);
    member = escapeData(member);
    orders.results = escapeData(orders.results); wishlist.results = escapeData(wishlist.results);
    recent.results = escapeData(recent.results); inquiries.results = escapeData(inquiries.results);
    content.innerHTML = `<div class="member-card"><p class="brand-name">MEMBER</p><h2>${member.name || member.username}님</h2><p>${member.email}</p><div class="social-status"><button class="social-button" disabled>카카오 · ${member.social_connections.kakao ? '연결됨' : '연동 준비 중'}</button><button class="social-button" disabled>네이버 · ${member.social_connections.naver ? '연결됨' : '연동 준비 중'}</button></div></div><section class="mypage-section"><h3>주문내역</h3><div class="mini-list">${orders.results.slice(0,10).map(o => `<button class="mini-item text-button" data-order="${o.order_number}"><span>${o.order_number}<br><small>${o.status} · ${o.fulfillment_status}</small></span><strong>${won(o.payment_amount)}</strong></button>`).join('') || '<p>주문내역이 없습니다.</p>'}</div></section><section class="mypage-section"><h3>1:1 문의</h3><form id="inquiryForm" class="inquiry-form"><select name="order_id"><option value="">주문 선택 없음</option>${orders.results.map(o => `<option value="${o.id}">${o.order_number}</option>`).join('')}</select><select name="category"><option value="order">주문</option><option value="delivery">배송</option><option value="product">상품</option><option value="return">교환·반품</option><option value="other">기타</option></select><input name="subject" required placeholder="문의 제목"><textarea name="body" required placeholder="문의 내용"></textarea><button class="primary-button">문의 등록</button></form><div class="mini-list">${inquiries.results.map(i => `<div class="mini-item"><span>${i.subject}<br><small>${i.status}</small>${i.answer ? `<div class="inquiry-answer">${i.answer}</div>` : ''}</span></div>`).join('')}</div></section><section class="mypage-section"><h3>찜한 상품</h3><div class="mini-list">${wishlist.results.slice(0,5).map(i => `<div class="mini-item" data-product-id="${i.id}"><span>${i.display_name}</span><strong>${won(i.selling_price_snapshot)}</strong></div>`).join('') || '<p>찜한 상품이 없습니다.</p>'}</div></section><section class="mypage-section"><h3>최근 본 상품</h3><div class="mini-list">${recent.results.slice(0,5).map(i => `<div class="mini-item" data-product-id="${i.id}"><span>${i.display_name}</span><strong>${won(i.selling_price_snapshot)}</strong></div>`).join('') || '<p>최근 본 상품이 없습니다.</p>'}</div></section><button id="logoutButton" class="primary-button">로그아웃</button>`;
    document.querySelector('#logoutButton').onclick = async () => { await api('/api/accounts/logout/', { method:'POST' }); document.querySelector('#accountDialog').close(); toast('로그아웃했습니다.'); };
    document.querySelector('#inquiryForm').onsubmit = async event => { event.preventDefault(); const payload = Object.fromEntries(new FormData(event.target)); if (!payload.order_id) delete payload.order_id; else payload.order_id = Number(payload.order_id); try { await api('/api/community/inquiries/', { method:'POST', body:JSON.stringify(payload) }); toast('문의를 등록했습니다.'); await openAccount(); } catch (error) { toast(error.message); } };
  } else {
    renderLogin();
  }
  if (!document.querySelector('#accountDialog').open) document.querySelector('#accountDialog').showModal();
}

async function openOrder(orderNumber) {
  const order = escapeData(await api(`/api/commerce/orders/${orderNumber}/`));
  const canCancel = order.status === 'paid' && !['shipped','in_transit','delivered','returned'].includes(order.fulfillment_status);
  document.querySelector('#orderContent').innerHTML = `<p class="brand-name">ORDER DETAIL</p><h2>${order.order_number}</h2><span class="status-badge">${order.status} · ${order.fulfillment_status}</span><div class="order-items">${order.items.map(item => `<article class="order-item"><strong>${item.product_name_snapshot}</strong><p>${item.option_name_snapshot} · ${item.ordered_quantity}개</p><p>${won(item.line_total)}</p>${order.fulfillment_status === 'delivered' && item.review_status !== 'written' ? `<button class="text-button" data-review-item="${item.id}">후기 작성</button><div id="reviewForm-${item.id}"></div>` : ''}</article>`).join('')}</div><div class="checkout-total"><span>결제금액</span><span>${won(order.payment_amount)}</span></div>${order.status === 'payment_pending' ? '<select id="retryPaymentMethod" class="variant-select"><option value="CARD">신용·체크카드</option><option value="NAVERPAY">네이버페이</option><option value="KAKAOPAY">카카오페이</option><option value="TOSSPAY">토스페이</option></select><button id="retryPaymentButton" class="primary-button">결제 다시 시도</button>' : ''}${canCancel ? '<button id="cancelOrderButton" class="primary-button">전체 주문취소</button>' : ''}`;
  if (order.shipments?.length) {
    const shipmentBox = document.createElement('div'); shipmentBox.className = 'shipment-box';
    order.shipments.forEach(shipment => { const line = document.createElement('p'); line.textContent = `${shipment.carrier_name || shipment.carrier_code || '택배사'} · ${shipment.tracking_number} · ${shipment.status}`; shipmentBox.append(line); });
    document.querySelector('#orderContent .order-items').before(shipmentBox);
  }
  if (canCancel) document.querySelector('#cancelOrderButton').onclick = async () => { const reason = prompt('취소 사유를 입력해 주세요.'); if (!reason) return; try { await api(`/api/commerce/orders/${order.order_number}/cancel/`, { method:'POST', body:JSON.stringify({ reason }) }); toast('주문을 취소했습니다.'); await openOrder(order.order_number); } catch (error) { toast(error.message); } };
  if (order.status === 'payment_pending') document.querySelector('#retryPaymentButton').onclick = async () => { try { const prepare = await api(`/api/commerce/payments/toss/prepare/${order.order_number}/`); await requestTossPayment(prepare, document.querySelector('#retryPaymentMethod').value); } catch (error) { toast(error.message); } };
  if (!document.querySelector('#orderDialog').open) document.querySelector('#orderDialog').showModal();
}

function showReviewForm(orderItemId) {
  document.querySelector(`#reviewForm-${orderItemId}`).innerHTML = `<form class="review-form" data-review-form="${orderItemId}"><select name="rating"><option value="5">★★★★★</option><option value="4">★★★★☆</option><option value="3">★★★☆☆</option><option value="2">★★☆☆☆</option><option value="1">★☆☆☆☆</option></select><input name="title" placeholder="후기 제목"><textarea name="body" required placeholder="상품 후기를 작성해 주세요."></textarea><button class="primary-button">후기 등록</button></form>`;
}

function authTabs(active) {
  return `<div class="auth-tabs"><button data-auth-tab="login" class="${active === 'login' ? 'active' : ''}">로그인</button><button data-auth-tab="register" class="${active === 'register' ? 'active' : ''}">회원가입</button></div>`;
}

function renderLogin() {
  document.querySelector('#accountContent').innerHTML = `${authTabs('login')}<form id="loginForm" class="auth-form"><input name="username" required placeholder="아이디" autocomplete="username"><input name="password" type="password" required placeholder="비밀번호" autocomplete="current-password"><button class="primary-button">로그인</button></form>`;
  document.querySelector('#loginForm').onsubmit = async event => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); try { await api('/api/accounts/login/', { method:'POST', body:JSON.stringify(data) }); await Promise.all([refreshCartCount(), loadWishlist()]); await loadProducts(); await openAccount(); toast('로그인했습니다.'); } catch (error) { toast(error.message); } };
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
  const card = event.target.closest('[data-product-id]'); if (card) return openProduct(card.dataset.productId);
  if (event.target.dataset.close) document.querySelector(`#${event.target.dataset.close}`).close();
  if (event.target.dataset.remove) { await api(`/api/commerce/cart/items/${event.target.dataset.remove}/`, { method:'DELETE' }); await openCart(); await refreshCartCount(); }
  if (event.target.dataset.qty) { const value = Number(event.target.dataset.value); if (value < 1) return; await api(`/api/commerce/cart/items/${event.target.dataset.qty}/`, { method:'PATCH', body:JSON.stringify({ quantity:value }) }); await openCart(); await refreshCartCount(); }
  if (event.target.dataset.authTab === 'login') renderLogin();
  if (event.target.dataset.authTab === 'register') renderRegister();
  if (event.target.dataset.order) openOrder(event.target.dataset.order);
  if (event.target.dataset.reviewItem) showReviewForm(event.target.dataset.reviewItem);
  const reviewForm = event.target.closest('[data-review-form]');
});

document.addEventListener('submit', async event => {
  if (!event.target.dataset.reviewForm) return;
  event.preventDefault();
  const data = Object.fromEntries(new FormData(event.target)); data.order_item_id = Number(event.target.dataset.reviewForm); data.rating = Number(data.rating);
  try { await api('/api/community/reviews/', { method:'POST', body:JSON.stringify(data) }); event.target.innerHTML = '<p>후기가 등록되었습니다.</p>'; toast('후기를 등록했습니다.'); } catch (error) { toast(error.message); }
});

async function refreshCartCount() { const data = await api('/api/commerce/cart/items/'); document.querySelector('#cartCount').textContent = data.summary.item_count; }
function toast(message) { const el = document.querySelector('#toast'); el.textContent = message; el.classList.add('show'); setTimeout(() => el.classList.remove('show'), 1800); }
document.querySelector('#cartButton').onclick = openCart; document.querySelector('#bottomCartButton').onclick = openCart;
document.querySelector('#accountButton').onclick = openAccount; document.querySelector('#bottomAccountButton').onclick = openAccount;
document.querySelector('#loadMoreButton').onclick = () => loadProducts(true);
document.querySelector('#sortSelect').onchange = event => { state.ordering = event.target.value; loadProducts(); };
let timer; document.querySelector('#searchInput').oninput = event => { clearTimeout(timer); timer = setTimeout(() => { state.query = event.target.value.trim(); loadProducts(); }, 250); };
loadWishlist().finally(() => Promise.all([loadBrands(), loadProducts(), loadContent(), refreshCartCount(), handlePaymentRedirect()]).catch(error => toast(error.message)));
