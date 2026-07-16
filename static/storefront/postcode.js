(function () {
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, character => ({
    '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;',
  })[character]);

  function fields(address = {}) {
    return `<div class="postcode-fields">
      <div class="postcode-search-row">
        <input name="postal_code" required inputmode="numeric" autocomplete="postal-code" placeholder="우편번호" value="${escapeHtml(address.postal_code || '')}" readonly>
        <button type="button" class="postcode-search-button" data-postcode-search>주소 검색</button>
      </div>
      <input name="address1" required autocomplete="address-line1" placeholder="기본주소" value="${escapeHtml(address.address1 || '')}" readonly>
      <input name="address2" autocomplete="address-line2" placeholder="상세주소 (동·호수 등)" value="${escapeHtml(address.address2 || '')}">
      <small class="postcode-help" data-postcode-status aria-live="polite">주소 검색 후 상세주소를 입력해 주세요.</small>
    </div>`;
  }

  function selectedAddress(data) {
    const baseAddress = (
      data.userSelectedType === 'R' ? data.roadAddress : data.jibunAddress
    ) || data.roadAddress || data.jibunAddress || data.address || '';
    if (data.userSelectedType !== 'R') return baseAddress;

    const extra = [];
    if (data.bname && /[동로가]$/.test(data.bname)) extra.push(data.bname);
    if (data.buildingName && data.apartment === 'Y') extra.push(data.buildingName);
    return extra.length ? `${baseAddress} (${extra.join(', ')})` : baseAddress;
  }

  function setManualMode(form, status) {
    const postalCode = form.elements.postal_code;
    const address1 = form.elements.address1;
    postalCode.readOnly = false;
    address1.readOnly = false;
    status.textContent = '주소 검색 서비스를 불러오지 못했습니다. 우편번호와 기본주소를 직접 입력해 주세요.';
    postalCode.focus();
  }

  function open(button) {
    const form = button.closest('form');
    if (!form) return;
    const postalCode = form.elements.postal_code;
    const address1 = form.elements.address1;
    const address2 = form.elements.address2;
    const status = form.querySelector('[data-postcode-status]');
    if (!postalCode || !address1 || !address2 || !status) return;
    if (!globalThis.kakao?.Postcode) {
      setManualMode(form, status);
      return;
    }

    status.textContent = '주소 검색창에서 배송지를 선택해 주세요.';
    new globalThis.kakao.Postcode({
      oncomplete(data) {
        postalCode.value = data.zonecode || '';
        address1.value = selectedAddress(data);
        address2.value = '';
        postalCode.dispatchEvent(new Event('change', { bubbles:true }));
        address1.dispatchEvent(new Event('change', { bubbles:true }));
        status.textContent = '주소가 입력되었습니다. 상세주소를 확인해 주세요.';
        address2.focus();
      },
    }).open();
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-postcode-search]');
    if (button) open(button);
  });

  globalThis.SequenzPostcode = { fields, open };
})();
