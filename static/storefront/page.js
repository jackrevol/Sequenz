const pageRoot = document.body;
const pageContent = document.querySelector('#pageContent');
const pageKind = pageRoot.dataset.page;
const h = value => String(value ?? '').replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' })[char]);
const won = value => `${Number(value || 0).toLocaleString('ko-KR')}원`;
const safeUrl = value => { try { const url = new URL(value, location.origin); return ['http:','https:'].includes(url.protocol) ? url.href : '#'; } catch (_) { return '#'; } };

function createGuestKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  if (globalThis.crypto?.getRandomValues) {
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
    return [...bytes].map(byte => byte.toString(16).padStart(2, '0')).join('');
  }
  return `guest-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

const guestKey = localStorage.getItem('sequenzGuestKey') || createGuestKey();
localStorage.setItem('sequenzGuestKey', guestKey);
const baseHeaders = { 'Content-Type':'application/json', 'X-Guest-Key':guestKey, 'X-CSRFToken':document.querySelector('meta[name="csrf-token"]').content };

async function api(url, options = {}) {
  const requestHeaders = { ...baseHeaders, ...(options.headers || {}) };
  if (options.body instanceof FormData) delete requestHeaders['Content-Type'];
  const response = await fetch(url, { ...options, headers:requestHeaders });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || Object.values(error).flat().join(' ') || '요청을 처리하지 못했습니다.');
  }
  return response.status === 204 ? null : response.json();
}

function toast(message) {
  const element = document.querySelector('#toast');
  element.textContent = message;
  element.classList.add('show');
  setTimeout(() => element.classList.remove('show'), 2200);
}

function showError(error) {
  pageContent.innerHTML = `<div class="page-empty"><h2>화면을 불러오지 못했습니다.</h2><p>${h(error.message)}</p><a class="secondary-button" href="/">홈으로 돌아가기</a></div>`;
}

function scrollToHashTarget() {
  if (!location.hash) return;
  requestAnimationFrame(() => document.querySelector(location.hash)?.scrollIntoView({ block:'start' }));
}

async function refreshCartCount() {
  const data = await api('/api/commerce/cart/items/');
  document.querySelector('#pageCartCount').textContent = data.summary.item_count;
  return data;
}

async function renderCart() {
  const data = await refreshCartCount();
  pageContent.innerHTML = data.results.length ? `
    <div class="cart-page-layout">
      <section class="cart-page-list">
        <div class="cart-tools"><label><input id="selectAllCart" type="checkbox" checked> 전체 선택</label><span id="cartSelectedCount">${data.results.length}개 선택</span><button class="text-button" data-cart-bulk="delete">선택 삭제</button><button class="text-button" data-cart-bulk="move_to_wishlist">찜으로 이동</button></div>
        ${data.results.map(item => `<article class="cart-page-item"><label class="cart-select"><input type="checkbox" data-cart-select="${Number(item.id)}" data-line-total="${Number(item.line_total)}" checked><span class="sr-only">${h(item.display_name)} 선택</span></label><div class="cart-item-info"><p class="brand-name">${h(item.listing_code || 'SEQUENZ')}</p><h2>${h(item.display_name)}</h2><label class="sr-only" for="cartOption${Number(item.id)}">${h(item.display_name)} 옵션</label><select id="cartOption${Number(item.id)}" class="cart-option-select" data-cart-option="${Number(item.id)}">${item.available_variants.map(variant => `<option value="${Number(variant.id)}" ${Number(variant.id) === Number(item.listing_variant_id) ? 'selected' : ''}>${h(variant.option_display_name)} · 재고 ${Number(variant.stock_quantity)}</option>`).join('')}</select><strong>${won(item.line_total)}</strong><button class="text-button" data-remove="${Number(item.id)}">삭제</button></div><div class="quantity"><button data-qty="${Number(item.id)}" data-value="${Number(item.quantity) - 1}" aria-label="수량 줄이기">−</button><span>${Number(item.quantity)}</span><button data-qty="${Number(item.id)}" data-value="${Number(item.quantity) + 1}" aria-label="수량 늘리기">＋</button></div></article>`).join('')}
      </section>
      <aside class="order-summary"><h2>ORDER SUMMARY</h2><dl><div><dt>상품 금액</dt><dd id="selectedSubtotal">${won(data.summary.items_subtotal)}</dd></div><div><dt>배송비</dt><dd id="selectedShipping">${won(data.summary.shipping_fee)}</dd></div><div class="summary-total"><dt>결제 예정 금액</dt><dd id="selectedPayment">${won(data.summary.payment_amount)}</dd></div></dl><button id="selectedCheckoutButton" class="primary-button">선택 상품 주문하기</button><a class="continue-link" href="/#products">쇼핑 계속하기</a></aside>
    </div>` : '<div class="page-empty"><h2>장바구니가 비어 있습니다.</h2><p>마음에 드는 상품을 담아보세요.</p><a class="primary-link" href="/#products">상품 보러가기</a></div>';
}

function authTabs(active) {
  return `<div class="auth-tabs"><button data-auth-tab="login" class="${active === 'login' ? 'active' : ''}">로그인</button><button data-auth-tab="register" class="${active === 'register' ? 'active' : ''}">회원가입</button></div>`;
}

function savedAddressChoices(member, addresses) {
  if (!member) return '';
  if (!addresses.length) {
    return '<div class="saved-address-empty"><strong>저장된 배송지가 없습니다.</strong><span>아래에서 주소를 검색해 입력해 주세요.</span></div>';
  }
  return `<fieldset class="saved-address-book"><legend>주소록에서 불러오기</legend><div class="saved-address-grid">${addresses.map((address, index) => `
    <label class="saved-address-card">
      <input type="radio" name="saved_address_id" value="${Number(address.id)}" ${index === 0 ? 'checked' : ''}>
      <span><strong>${h(address.label)}${address.is_default ? '<em>기본 배송지</em>' : ''}</strong><small>${h(address.recipient_name)} · ${h(address.recipient_phone)}</small><span>${h(address.address1)} ${h(address.address2)}</span></span>
    </label>`).join('')}</div></fieldset>`;
}

function bindCheckoutAddressControls(form, addresses) {
  const sameAsBuyer = form.querySelector('#sameAsBuyer');
  const buyerName = form.querySelector('[name="buyer_name"]');
  const buyerPhone = form.querySelector('[name="buyer_phone"]');
  const recipientName = form.querySelector('[name="recipient_name"]');
  const recipientPhone = form.querySelector('[name="recipient_phone"]');

  const syncRecipient = () => {
    const checked = sameAsBuyer.checked;
    recipientName.readOnly = checked;
    recipientPhone.readOnly = checked;
    recipientName.classList.toggle('copied-from-buyer', checked);
    recipientPhone.classList.toggle('copied-from-buyer', checked);
    if (checked) {
      recipientName.value = buyerName.value;
      recipientPhone.value = buyerPhone.value;
    }
  };
  sameAsBuyer.addEventListener('change', syncRecipient);
  buyerName.addEventListener('input', () => { if (sameAsBuyer.checked) recipientName.value = buyerName.value; });
  buyerPhone.addEventListener('input', () => { if (sameAsBuyer.checked) recipientPhone.value = buyerPhone.value; });

  form.querySelectorAll('[name="saved_address_id"]').forEach(input => {
    input.addEventListener('change', () => {
      if (!input.checked) return;
      const address = addresses.find(item => Number(item.id) === Number(input.value));
      if (!address) return;
      sameAsBuyer.checked = false;
      syncRecipient();
      recipientName.value = address.recipient_name || '';
      recipientPhone.value = address.recipient_phone || '';
      form.querySelector('[name="postal_code"]').value = address.postal_code || '';
      form.querySelector('[name="address1"]').value = address.address1 || '';
      form.querySelector('[name="address2"]').value = address.address2 || '';
      form.querySelector('[name="delivery_memo"]').value = address.delivery_memo || '';
    });
  });
}

function renderLogin() {
  pageContent.innerHTML = `<div class="account-guest-layout"><section>${authTabs('login')}<form id="loginForm" class="auth-form"><input name="username" required placeholder="아이디" autocomplete="username"><input name="password" type="password" required placeholder="비밀번호" autocomplete="current-password"><button class="primary-button">로그인</button></form></section><section class="guest-order-box"><h2>비회원 주문조회</h2><p>주문 시 입력한 정보로 배송 현황을 확인할 수 있습니다.</p><form id="guestOrderLookupForm" class="auth-form"><input name="order_number" required placeholder="주문번호"><input name="buyer_name" required placeholder="주문자명"><input name="buyer_phone" required placeholder="주문자 연락처"><button class="secondary-button">주문조회</button></form></section></div>`;
}

function renderRegister() {
  pageContent.innerHTML = `<div class="account-form-wrap">${authTabs('register')}<form id="registerForm" class="auth-form"><input name="username" required placeholder="아이디" autocomplete="username"><input name="email" type="email" required placeholder="이메일"><input name="password" type="password" minlength="8" required placeholder="비밀번호 (8자 이상)" autocomplete="new-password"><input name="name" required placeholder="이름"><input name="phone" required placeholder="휴대폰 번호"><label class="checkbox-row"><input name="terms_agreed" type="checkbox" required> 필수 약관에 동의합니다.</label><label class="checkbox-row"><input name="marketing_agreed" type="checkbox"> 마케팅 정보 수신에 동의합니다.</label><button class="primary-button">회원가입</button></form></div>`;
}

async function renderAccount() {
  let member;
  try { member = await api('/api/accounts/me/'); } catch (_) { renderLogin(); return; }
  const [orders, wishlist, recent, inquiries, benefits, addresses] = await Promise.all([
    api('/api/commerce/orders/mine/'), api('/api/accounts/wishlist/'), api('/api/accounts/recently-viewed/'),
    api('/api/community/inquiries/'), api('/api/benefits/mine/'), api('/api/accounts/addresses/'),
  ]);
  pageContent.innerHTML = `<div class="account-dashboard">
    <aside class="member-overview"><p class="brand-name">MEMBER</p><h2>${h(member.name || member.username)}님</h2><p>${h(member.email)}</p><dl><div><dt>등급</dt><dd>${h(benefits.account.tier_name)}</dd></div><div><dt>적립금</dt><dd>${Number(benefits.account.point_balance).toLocaleString('ko-KR')}P</dd></div><div><dt>쿠폰</dt><dd>${benefits.coupons.filter(item => item.status === 'available').length}장</dd></div></dl><button id="logoutButton" class="secondary-button">로그아웃</button></aside>
    <div class="account-sections">
      <section class="mypage-section"><h2>주문내역</h2><div class="mini-list">${orders.results.map(order => `<a class="mini-item" href="/orders/${encodeURIComponent(order.order_number)}/"><span>${h(order.order_number)}<br><small>${h(order.status)} · ${h(order.fulfillment_status)}</small></span><strong>${won(order.payment_amount)}</strong></a>`).join('') || '<p>주문내역이 없습니다.</p>'}</div></section>
      <section id="addresses" class="mypage-section"><div class="address-section-head"><h2>배송지 관리</h2><button type="button" class="address-add-button" data-address-dialog-open>배송지 추가</button></div><div class="mini-list">${addresses.results.map(address => `<div class="mini-item"><span><strong>${h(address.label)}</strong>${address.is_default ? ' · 기본' : ''}<br><small>${h(address.recipient_name)} · ${h(address.address1)} ${h(address.address2)}</small></span><button class="text-button" data-address-delete="${Number(address.id)}">삭제</button></div>`).join('') || '<p>등록된 배송지가 없습니다.</p>'}</div><dialog id="addressDialog" class="address-dialog" aria-labelledby="addressDialogTitle"><div class="address-dialog-panel"><header><div><p class="eyebrow">ADDRESS BOOK</p><h3 id="addressDialogTitle">배송지 추가</h3></div><button type="button" class="address-dialog-close" data-address-dialog-close aria-label="닫기">×</button></header><form id="newAddressForm" class="address-editor address-modal-form"><input name="label" required placeholder="배송지명 (예: 집, 회사)"><input name="recipient_name" required placeholder="수취인"><input name="recipient_phone" required placeholder="연락처">${SequenzPostcode.fields()}<input name="delivery_memo" placeholder="배송 메모"><label class="checkbox-row"><input name="is_default" type="checkbox"> 기본 배송지로 설정</label><button class="primary-button">배송지 저장</button></form></div></dialog></section>
      <section id="wishlist" class="mypage-section"><h2>찜한 상품</h2><div class="mini-list">${wishlist.results.map(item => `<a class="mini-item" href="/products/${Number(item.id)}/"><span>${h(item.display_name)}</span><strong>${won(item.selling_price_snapshot)}</strong></a>`).join('') || '<p>찜한 상품이 없습니다.</p>'}</div></section>
      <section id="recent" class="mypage-section"><h2>최근 본 상품</h2><div class="mini-list">${recent.results.map(item => `<a class="mini-item" href="/products/${Number(item.id)}/"><span>${h(item.display_name)}</span><strong>${won(item.selling_price_snapshot)}</strong></a>`).join('') || '<p>최근 본 상품이 없습니다.</p>'}</div></section>
      <section class="mypage-section"><h2>1:1 문의</h2><form id="inquiryForm" class="inquiry-form"><select name="category"><option value="order">주문</option><option value="delivery">배송</option><option value="product">상품</option><option value="return">교환·반품</option><option value="other">기타</option></select><input name="subject" required placeholder="문의 제목"><textarea name="body" required placeholder="문의 내용"></textarea><button class="primary-button">문의 등록</button></form><div class="mini-list">${inquiries.results.map(item => `<div class="mini-item"><span>${h(item.subject)}<br><small>${h(item.status)}</small>${item.answer ? `<p class="inquiry-answer">${h(item.answer)}</p>` : ''}</span></div>`).join('')}</div></section>
    </div>
  </div>`;
  document.querySelector('#addressDialog')?.addEventListener('click', event => {
    if (event.target === event.currentTarget) event.currentTarget.close();
  });
  scrollToHashTarget();
}

async function updateCartSelectionUI() {
  const selected = [...document.querySelectorAll('[data-cart-select]:checked')];
  const all = [...document.querySelectorAll('[data-cart-select]')];
  const allToggle = document.querySelector('#selectAllCart');
  if (!allToggle) return;
  allToggle.checked = selected.length === all.length;
  allToggle.indeterminate = selected.length > 0 && selected.length < all.length;
  document.querySelector('#cartSelectedCount').textContent = `${selected.length}개 선택`;
  document.querySelector('#selectedCheckoutButton').disabled = selected.length === 0;
  if (!selected.length) {
    document.querySelector('#selectedSubtotal').textContent = won(0);
    document.querySelector('#selectedShipping').textContent = won(0);
    document.querySelector('#selectedPayment').textContent = won(0);
    return;
  }
  try {
    const quote = await api('/api/commerce/cart/benefit-quote/', { method:'POST', body:JSON.stringify({ cart_item_ids:selected.map(input => Number(input.dataset.cartSelect)) }) });
    document.querySelector('#selectedSubtotal').textContent = won(selected.reduce((sum,input) => sum + Number(input.dataset.lineTotal), 0));
    document.querySelector('#selectedShipping').textContent = won(quote.shipping_fee);
    document.querySelector('#selectedPayment').textContent = won(quote.payment_amount);
  } catch (error) { toast(error.message); }
}

async function renderSupport() {
  const [notices, faqs, shipping, returns] = await Promise.all([
    api('/api/content/notices/'), api('/api/content/faqs/'),
    api('/api/content/policies/shipping/').catch(() => null), api('/api/content/policies/returns/').catch(() => null),
  ]);
  pageContent.innerHTML = `<div class="support-layout"><nav class="support-nav"><a href="#notices">공지사항</a><a href="#faqs">자주 묻는 질문</a><a href="#policies">배송·반품 안내</a></nav><div><section id="notices" class="support-section"><h2>공지사항</h2>${notices.map(item => `<details><summary>${h(item.title)}</summary><p>${h(item.content)}</p></details>`).join('') || '<p>공지사항이 없습니다.</p>'}</section><section id="faqs" class="support-section"><h2>자주 묻는 질문</h2>${faqs.map(item => `<details><summary>[${h(item.category)}] ${h(item.question)}</summary><p>${h(item.answer)}</p></details>`).join('') || '<p>FAQ가 없습니다.</p>'}</section><section id="policies" class="support-section"><h2>배송·반품 안내</h2>${[shipping, returns].filter(Boolean).map(item => `<article><h3>${h(item.title)}</h3><p class="product-description">${h(item.content)}</p></article>`).join('') || '<p>등록된 정책이 없습니다.</p>'}</section></div></div>`;
}

async function renderCheckout() {
  const cart = await refreshCartCount();
  const storedIds = JSON.parse(localStorage.getItem('sequenzCheckoutItemIds') || '[]').map(Number);
  const selectedIds = storedIds.filter(id => cart.results.some(item => Number(item.id) === id));
  const orderItems = selectedIds.length ? cart.results.filter(item => selectedIds.includes(Number(item.id))) : cart.results;
  if (!orderItems.length) { pageContent.innerHTML = '<div class="page-empty"><h2>주문할 상품이 없습니다.</h2><a class="primary-link" href="/cart/">장바구니로 돌아가기</a></div>'; return; }
  let member = null;
  try { member = await api('/api/accounts/me/'); } catch (_) {}
  const addresses = member ? await api('/api/accounts/addresses/') : { results:[] };
  const benefits = member ? await api('/api/benefits/mine/') : null;
  const address = addresses.results[0] || {};
  const initialQuote = await api('/api/commerce/cart/benefit-quote/', { method:'POST', body:JSON.stringify({ cart_item_ids:orderItems.map(item => Number(item.id)) }) });
  pageContent.innerHTML = `<div class="checkout-page-layout"><form id="checkoutForm" class="checkout-form page-checkout-form" data-cart-item-ids="${orderItems.map(item => Number(item.id)).join(',')}"><section><h2>주문자 정보</h2><input name="buyer_name" required placeholder="주문자명" value="${h(member?.name || '')}"><input name="buyer_phone" required placeholder="주문자 연락처" value="${h(member?.phone || '')}"><input name="buyer_email" type="email" placeholder="이메일" value="${h(member?.email || '')}"></section><section><div class="checkout-section-head"><h2>배송지 정보</h2><label class="same-recipient-row"><input id="sameAsBuyer" type="checkbox"> 주문자 이름·연락처와 동일</label></div>${savedAddressChoices(member, addresses.results)}<input name="recipient_name" required placeholder="수취인명" value="${h(address.recipient_name || '')}"><input name="recipient_phone" required placeholder="수취인 연락처" value="${h(address.recipient_phone || '')}">${SequenzPostcode.fields(address)}<input name="delivery_memo" placeholder="배송 메모" value="${h(address.delivery_memo || '')}"></section>${benefits ? `<section><h2>쿠폰·적립금</h2><div class="benefit-fields"><label>쿠폰<select name="coupon_code"><option value="">사용 안 함</option>${benefits.coupons.filter(item => item.status === 'available').map(item => `<option value="${h(item.coupon.code)}">${h(item.coupon.name)}</option>`).join('')}</select></label><label>적립금 사용 <small>보유 ${Number(benefits.account.point_balance).toLocaleString('ko-KR')}P</small><input type="number" name="point_to_use" min="0" max="${Number(benefits.account.point_balance)}" value="0"></label></div></section>` : ''}<section><h2>결제수단</h2><div class="payment-grid"><label class="payment-option"><input type="radio" name="payment_method" value="CARD" checked><span>신용·체크카드</span></label><label class="payment-option"><input type="radio" name="payment_method" value="NAVERPAY"><span>네이버페이</span></label><label class="payment-option"><input type="radio" name="payment_method" value="KAKAOPAY"><span>카카오페이</span></label><label class="payment-option"><input type="radio" name="payment_method" value="TOSSPAY"><span>토스페이</span></label></div></section></form><aside class="order-summary"><h2>ORDER SUMMARY</h2>${orderItems.map(item => `<p class="summary-item"><span>${h(item.display_name)} × ${Number(item.quantity)}</span><strong>${won(item.line_total)}</strong></p>`).join('')}<div class="summary-total"><span>결제 예정 금액</span><strong id="checkoutAmount">${won(initialQuote.payment_amount)}</strong></div><button form="checkoutForm" class="primary-button">결제하기</button></aside></div>`;
  const checkoutForm = document.querySelector('#checkoutForm');
  bindCheckoutAddressControls(checkoutForm, addresses.results);
  const benefitInputs = pageContent.querySelectorAll('[name="coupon_code"], [name="point_to_use"]');
  benefitInputs.forEach(input => input.addEventListener('change', async () => { const form = document.querySelector('#checkoutForm'); const quote = await api('/api/commerce/cart/benefit-quote/', { method:'POST', body:JSON.stringify({ coupon_code:form.coupon_code?.value || '', point_to_use:Number(form.point_to_use?.value || 0), cart_item_ids:form.dataset.cartItemIds.split(',').map(Number) }) }); document.querySelector('#checkoutAmount').textContent = won(quote.payment_amount); }));
}

async function requestPayment(orderNumber, method) {
  const prepare = await api(`/api/commerce/payments/toss/prepare/${encodeURIComponent(orderNumber)}/`);
  if (!window.TossPayments) throw new Error('결제 SDK를 불러오지 못했습니다.');
  const payment = window.TossPayments(prepare.client_key).payment({ customerKey:prepare.customer_key });
  const card = method === 'CARD' ? { flowMode:'DEFAULT' } : { flowMode:'DIRECT', easyPay:method };
  await payment.requestPayment({ method:'CARD', card, amount:{ currency:'KRW', value:prepare.amount }, orderId:prepare.order_id, orderName:prepare.order_name, customerName:prepare.customer_name, customerEmail:prepare.customer_email, customerMobilePhone:prepare.customer_mobile_phone, successUrl:prepare.success_url, failUrl:prepare.fail_url });
}

async function renderOrder() {
  const orderNumber = pageRoot.dataset.orderNumber;
  let order;
  const guestOrder = sessionStorage.getItem(`sequenzGuestOrder:${orderNumber}`);
  if (guestOrder) order = JSON.parse(guestOrder); else order = await api(`/api/commerce/orders/${encodeURIComponent(orderNumber)}/`);
  const claims = guestOrder ? { results:[] } : await api(`/api/commerce/orders/${encodeURIComponent(orderNumber)}/claims/`);
  const canCancel = order.status === 'paid' && !['shipped','in_transit','delivered','returned'].includes(order.fulfillment_status);
  pageContent.innerHTML = `<div class="order-detail-page"><header><p class="brand-name">ORDER DETAIL</p><h2>${h(order.order_number)}</h2><span class="status-badge">${h(order.status)} · ${h(order.fulfillment_status)}</span></header><section class="order-items">${order.items.map(item => `<article class="order-item"><div><strong>${h(item.product_name_snapshot)}</strong><p>${h(item.option_name_snapshot)} · ${Number(item.ordered_quantity)}개</p></div><strong>${won(item.line_total)}</strong></article>`).join('')}</section>${(order.shipments || []).map(item => `<div class="shipment-box">${h(item.carrier_name || item.carrier_code || '택배사')} · ${h(item.tracking_number)} · ${h(item.status)}</div>`).join('')}<div class="checkout-total"><span>결제금액</span><strong>${won(order.payment_amount)}</strong></div>${order.status === 'payment_pending' ? '<select id="retryPaymentMethod" class="variant-select"><option value="CARD">신용·체크카드</option><option value="NAVERPAY">네이버페이</option><option value="KAKAOPAY">카카오페이</option><option value="TOSSPAY">토스페이</option></select><button id="retryPaymentButton" class="primary-button">결제 다시 시도</button>' : ''}${canCancel ? '<button id="cancelOrderButton" class="secondary-button">전체 주문취소</button>' : ''}<section class="claim-history"><h2>취소·교환·반품 현황</h2>${claims.results.map(claim => `<p>${h(claim.claim_type)} · ${h(claim.status)}<br><small>${h(claim.reason)}</small></p>`).join('') || '<p>신청 내역이 없습니다.</p>'}</section></div>`;
  document.querySelector('#retryPaymentButton')?.addEventListener('click', () => requestPayment(order.order_number, document.querySelector('#retryPaymentMethod').value).catch(error => toast(error.message)));
  document.querySelector('#cancelOrderButton')?.addEventListener('click', async () => { const reason = prompt('취소 사유를 입력해 주세요.'); if (!reason) return; await api(`/api/commerce/orders/${encodeURIComponent(order.order_number)}/cancel/`, { method:'POST', body:JSON.stringify({ reason }) }); await renderOrder(); });
}

async function renderContent() {
  const type = pageRoot.dataset.contentType;
  const slug = pageRoot.dataset.contentSlug;
  if (!['collections','promotions','lookbooks'].includes(type)) throw new Error('지원하지 않는 콘텐츠입니다.');
  const item = await api(`/api/content/${type}/${encodeURIComponent(slug)}/`);
  document.querySelector('.page-heading h1').textContent = item.title;
  pageContent.innerHTML = `<article class="editorial-page"><p class="brand-name">${type.toUpperCase()} ${h(item.season_label || '')}</p><p class="editorial-summary">${h(item.summary)}</p>${item.hero_image_url || item.cover_image_url ? `<img class="editorial-hero" src="${h(safeUrl(item.hero_image_url || item.cover_image_url))}" alt="">` : ''}<div class="product-description">${h(new DOMParser().parseFromString(item.body_html || '', 'text/html').body.textContent)}</div>${(item.images || []).map(image => `<figure><img src="${h(safeUrl(image.image_url))}" alt="${h(image.caption)}"><figcaption>${h(image.caption)}</figcaption></figure>`).join('')}<section><h2>연결 상품</h2><div class="product-grid">${item.listings.map(product => `<article class="product-card"><a class="product-card-link" href="/products/${Number(product.id)}/"><div class="product-image">${h(product.product.brand?.name || 'SEQUENZ')}</div><h3>${h(product.display_name)}</h3><p class="price">${won(product.selling_price_snapshot)}</p></a></article>`).join('') || '<p>연결된 상품이 없습니다.</p>'}</div></section></article>`;
}

document.addEventListener('click', async event => {
  if (event.target.dataset.remove) { await api(`/api/commerce/cart/items/${event.target.dataset.remove}/`, { method:'DELETE' }); await renderCart(); }
  if (event.target.dataset.qty) { const value = Number(event.target.dataset.value); if (value > 0) { await api(`/api/commerce/cart/items/${event.target.dataset.qty}/`, { method:'PATCH', body:JSON.stringify({ quantity:value }) }); await renderCart(); } }
  if (event.target.dataset.authTab === 'login') renderLogin();
  if (event.target.dataset.authTab === 'register') renderRegister();
  if (event.target.id === 'selectAllCart') { document.querySelectorAll('[data-cart-select]').forEach(input => { input.checked = event.target.checked; }); await updateCartSelectionUI(); }
  if (event.target.dataset.cartBulk) {
    const itemIds = [...document.querySelectorAll('[data-cart-select]:checked')].map(input => Number(input.dataset.cartSelect));
    if (!itemIds.length) return toast('상품을 선택해 주세요.');
    try { await api('/api/commerce/cart/items/bulk/', { method:'POST', body:JSON.stringify({ item_ids:itemIds, action:event.target.dataset.cartBulk }) }); await renderCart(); toast(event.target.dataset.cartBulk === 'delete' ? '선택 상품을 삭제했습니다.' : '찜으로 이동했습니다.'); } catch (error) { toast(error.message); }
  }
  if (event.target.id === 'selectedCheckoutButton') {
    const itemIds = [...document.querySelectorAll('[data-cart-select]:checked')].map(input => Number(input.dataset.cartSelect));
    if (!itemIds.length) return toast('주문할 상품을 선택해 주세요.');
    localStorage.setItem('sequenzCheckoutItemIds', JSON.stringify(itemIds)); location.href = '/checkout/';
  }
  if (event.target.matches('[data-address-dialog-open]')) document.querySelector('#addressDialog')?.showModal();
  if (event.target.matches('[data-address-dialog-close]')) document.querySelector('#addressDialog')?.close();
  if (event.target.dataset.addressDelete) { await api(`/api/accounts/addresses/${event.target.dataset.addressDelete}/`, { method:'DELETE' }); await renderAccount(); toast('배송지를 삭제했습니다.'); }
});

document.addEventListener('change', async event => {
  if (event.target.dataset.cartSelect) await updateCartSelectionUI();
  if (event.target.dataset.cartOption) {
    try { await api(`/api/commerce/cart/items/${event.target.dataset.cartOption}/`, { method:'PATCH', body:JSON.stringify({ listing_variant_id:Number(event.target.value) }) }); await renderCart(); toast('옵션을 변경했습니다.'); } catch (error) { toast(error.message); await renderCart(); }
  }
});

document.addEventListener('submit', async event => {
  if (event.target.id === 'loginForm') { event.preventDefault(); try { await api('/api/accounts/login/', { method:'POST', body:JSON.stringify(Object.fromEntries(new FormData(event.target))) }); await renderAccount(); toast('로그인했습니다.'); } catch (error) { toast(error.message); } }
  if (event.target.id === 'registerForm') { event.preventDefault(); const form = new FormData(event.target); const data = Object.fromEntries(form); data.terms_agreed = form.has('terms_agreed'); data.marketing_agreed = form.has('marketing_agreed'); try { await api('/api/accounts/register/', { method:'POST', body:JSON.stringify(data) }); await renderAccount(); toast('가입을 완료했습니다.'); } catch (error) { toast(error.message); } }
  if (event.target.id === 'guestOrderLookupForm') { event.preventDefault(); try { const order = await api('/api/commerce/orders/guest-lookup/', { method:'POST', body:JSON.stringify(Object.fromEntries(new FormData(event.target))) }); sessionStorage.setItem(`sequenzGuestOrder:${order.order_number}`, JSON.stringify(order)); location.href = `/orders/${encodeURIComponent(order.order_number)}/`; } catch (error) { toast(error.message); } }
  if (event.target.id === 'inquiryForm') { event.preventDefault(); try { await api('/api/community/inquiries/', { method:'POST', body:JSON.stringify(Object.fromEntries(new FormData(event.target))) }); await renderAccount(); toast('문의를 등록했습니다.'); } catch (error) { toast(error.message); } }
  if (event.target.id === 'newAddressForm') { event.preventDefault(); const form = new FormData(event.target); const data = Object.fromEntries(form); data.is_default = form.has('is_default'); try { await api('/api/accounts/addresses/', { method:'POST', body:JSON.stringify(data) }); await renderAccount(); toast('배송지를 추가했습니다.'); } catch (error) { toast(error.message); } }
  if (event.target.id === 'checkoutForm') { event.preventDefault(); const form = new FormData(event.target); const method = form.get('payment_method'); form.delete('payment_method'); form.delete('saved_address_id'); const data = Object.fromEntries(form); data.cart_item_ids = event.target.dataset.cartItemIds.split(',').map(Number); event.submitter.disabled = true; try { const order = await api('/api/commerce/orders/', { method:'POST', body:JSON.stringify(data) }); localStorage.removeItem('sequenzCheckoutItemIds'); await requestPayment(order.order_number, method); } catch (error) { event.submitter.disabled = false; toast(error.message); } }
});

document.addEventListener('click', async event => {
  if (event.target.id === 'logoutButton') { await api('/api/accounts/logout/', { method:'POST' }); renderLogin(); toast('로그아웃했습니다.'); }
});

const renderers = { cart:renderCart, checkout:renderCheckout, account:renderAccount, support:renderSupport, order:renderOrder, content:renderContent };
refreshCartCount().catch(() => {});

async function startPage() {
  const params = new URLSearchParams(location.search);
  if (pageKind === 'checkout' && params.get('payment') === 'success') {
    const orderNumber = params.get('orderId');
    const paymentKey = params.get('paymentKey');
    const amount = Number(params.get('amount'));
    if (!orderNumber || !paymentKey || !Number.isSafeInteger(amount)) throw new Error('결제 승인 정보가 올바르지 않습니다.');
    await api('/api/commerce/payments/toss/confirm/', { method:'POST', body:JSON.stringify({ order_number:orderNumber, payment_key:paymentKey, amount }) });
    location.replace(`/orders/${encodeURIComponent(orderNumber)}/`);
    return;
  }
  if (pageKind === 'checkout' && params.get('payment') === 'fail') {
    history.replaceState({}, '', '/checkout/');
    toast(params.get('message') || '결제가 취소되었거나 실패했습니다.');
  }
  await renderers[pageKind]?.();
}

startPage().catch(showError);
