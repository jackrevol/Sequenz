const csrf = document.querySelector('meta[name="csrf-token"]').content;
const won = value => `${Number(value || 0).toLocaleString('ko-KR')}원`;
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

const labels = {
  payment_pending:'결제 대기', paid:'결제 완료', payment_failed:'결제 실패', cancelled:'취소',
  pending:'상품 준비 전', preparing:'상품 준비 중', ready_to_ship:'출고 대기', shipped:'출고 완료',
  in_transit:'배송 중', delivered:'배송 완료', returned:'반품 완료',
  toss_payments:'토스페이먼츠', sabangnet:'사방넷', payment_lookup:'결제 조회',
  order_export:'주문 전송', order_status_sync:'주문 상태 동기화', product_sync:'상품 동기화'
};
const label = value => labels[value] || value || '-';
const statusTone = value => ({paid:'success',delivered:'success',shipped:'info',in_transit:'info',preparing:'warning',ready_to_ship:'warning',payment_failed:'danger',cancelled:'danger',returned:'danger'}[value] || '');

async function api(url, options = {}) {
  const response = await fetch(url, {...options, headers:{'Content-Type':'application/json','X-CSRFToken':csrf,...options.headers}});
  let body;
  try { body = await response.json(); } catch { body = {}; }
  if (!response.ok) throw new Error(body.detail || '요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.');
  return body;
}

function renderSummary(summary) {
  const metrics = [
    {title:'30일 순매출', value:won(summary.paid_sales_30d), foot:'결제 완료 주문 기준', icon:'↗'},
    {title:'30일 결제 주문', value:`${Number(summary.paid_orders_30d).toLocaleString('ko-KR')}건`, foot:'최근 30일 누적', icon:'□'},
    {title:'사방넷 전송 실패', value:`${Number(summary.failed_exports).toLocaleString('ko-KR')}건`, foot:summary.failed_exports ? '확인이 필요합니다' : '모든 전송이 정상입니다', icon:'!', tone:summary.failed_exports ? 'warning' : ''},
    {title:'24시간 연동 오류', value:`${Number(summary.integration_errors_24h).toLocaleString('ko-KR')}건`, foot:summary.integration_errors_24h ? '최근 오류를 확인해 주세요' : '연동 상태가 안정적입니다', icon:'⌁', tone:summary.integration_errors_24h ? 'alert' : ''}
  ];
  document.querySelector('#summary').innerHTML = metrics.map(item => `<article class="metric-card ${item.tone}"><div class="metric-top"><span>${item.title}</span><i class="metric-icon">${item.icon}</i></div><strong class="metric-value">${item.value}</strong><small class="metric-foot">${item.foot}</small></article>`).join('');
}

function renderOrders(orders) {
  const body = document.querySelector('#ordersBody');
  if (!orders.length) { body.innerHTML = '<tr><td colspan="5" class="empty-state">아직 접수된 주문이 없습니다.</td></tr>'; return; }
  body.innerHTML = orders.map(order => `<tr>
    <td><span class="order-number">${esc(order.order_number)}</span></td>
    <td><span class="customer"><strong>${esc(order.buyer_name)}</strong><small>${esc(order.buyer_phone)}</small></span></td>
    <td><span class="status-badge ${statusTone(order.status)}">${esc(label(order.status))}</span></td>
    <td><span class="status-badge ${statusTone(order.fulfillment_status)}">${esc(label(order.fulfillment_status))}</span></td>
    <td class="align-right amount">${won(order.payment_amount)}</td>
  </tr>`).join('');
}

function renderLogs(logs) {
  const visible = logs.slice(0, 4);
  const errors = logs.filter(log => log.error_code).length;
  const state = document.querySelector('#healthState');
  state.textContent = errors ? `오류 ${errors}건` : '정상'; state.className = `health-state ${errors ? 'bad' : 'ok'}`;
  const list = document.querySelector('#logs');
  if (!visible.length) { list.innerHTML = '<div class="empty-state">최근 연동 기록이 없습니다.</div>'; return; }
  list.innerHTML = visible.map(log => {
    const detail = log.error_message || (log.response_status ? `응답 코드 ${log.response_status}` : '정상 처리되었습니다.');
    const time = log.created_at ? new Intl.DateTimeFormat('ko-KR',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}).format(new Date(log.created_at)) : '';
    return `<div class="log-item"><i class="log-dot ${log.error_code ? 'error' : ''}"></i><div class="log-copy"><time>${esc(time)}</time><strong>${esc(label(log.provider))} · ${esc(label(log.operation))}</strong><small>${esc(detail)}</small></div></div>`;
  }).join('');
}

function renderSales(rows) {
  const chart = document.querySelector('#salesChart');
  const max = Math.max(...rows.map(row => Number(row.sales)), 1);
  const total = rows.reduce((sum, row) => sum + Number(row.sales), 0);
  document.querySelector('#salesTotal').textContent = won(total);
  if (!rows.length) { chart.innerHTML = '<div class="empty-state">표시할 매출 데이터가 없습니다.</div>'; return; }
  chart.innerHTML = rows.map(row => {
    const height = Math.max((Number(row.sales) / max) * 100, 2);
    const date = new Intl.DateTimeFormat('ko-KR',{month:'numeric',day:'numeric'}).format(new Date(`${row.day}T00:00:00`));
    return `<div class="sales-bar-wrap" style="--height:${height}%" data-tooltip="${esc(date)} · ${won(row.sales)}"><i class="sales-bar" style="height:${height}%"></i></div>`;
  }).join('');
}

async function load() {
  const refresh = document.querySelector('#refreshButton');
  const errorBox = document.querySelector('#globalError');
  refresh.classList.add('loading'); errorBox.hidden = true;
  try {
    const [data, sales, logs, policy] = await Promise.all([
      api('/operations/api/dashboard/'), api('/operations/api/sales/'),
      api('/operations/api/logs/'), api('/operations/api/shipping-policy/')
    ]);
    renderSummary(data.summary); renderOrders(data.recent_orders); renderSales(sales.results); renderLogs(logs.results);
    const form = document.querySelector('#shippingPolicy');
    form.name.value = policy.name || ''; form.base_fee.value = policy.base_fee || 0; form.free_shipping_threshold.value = policy.free_shipping_threshold || 0;
    document.querySelector('#updatedAt').textContent = new Intl.DateTimeFormat('ko-KR',{hour:'2-digit',minute:'2-digit'}).format(new Date());
  } catch (error) {
    errorBox.textContent = error.message; errorBox.hidden = false;
  } finally { refresh.classList.remove('loading'); }
}

document.querySelector('#refreshButton').addEventListener('click', load);
document.querySelector('#reconcile').addEventListener('click', async () => {
  const order = document.querySelector('#orderNumber').value.trim();
  const result = document.querySelector('#reconcileResult');
  if (!order) { result.textContent = '주문번호를 입력해 주세요.'; result.className = 'form-message error'; return; }
  result.textContent = '결제 상태를 확인하고 있습니다…'; result.className = 'form-message';
  try { await api(`/operations/api/payments/${encodeURIComponent(order)}/reconcile/`, {method:'POST'}); result.textContent = '최신 결제 상태로 반영했습니다.'; await load(); }
  catch (error) { result.textContent = error.message; result.className = 'form-message error'; }
});
document.querySelector('#shippingPolicy').addEventListener('submit', async event => {
  event.preventDefault(); const button = event.target.querySelector('button'); const message = document.querySelector('#shippingMessage');
  const data = Object.fromEntries(new FormData(event.target)); data.base_fee = Number(data.base_fee); data.free_shipping_threshold = Number(data.free_shipping_threshold);
  button.disabled = true; button.textContent = '저장 중…'; message.textContent = '';
  try { await api('/operations/api/shipping-policy/', {method:'PATCH', body:JSON.stringify(data)}); message.textContent = '배송 정책을 저장했습니다.'; }
  catch (error) { message.textContent = error.message; message.className = 'form-message error'; }
  finally { button.disabled = false; button.textContent = '배송 정책 저장'; }
});
const sidebar = document.querySelector('.sidebar'), backdrop = document.querySelector('#sidebarBackdrop'), menu = document.querySelector('#mobileMenu');
function closeMenu(){sidebar.classList.remove('open');backdrop.classList.remove('open');menu.setAttribute('aria-expanded','false')}
menu.addEventListener('click',()=>{const open=sidebar.classList.toggle('open');backdrop.classList.toggle('open',open);menu.setAttribute('aria-expanded',String(open))});
backdrop.addEventListener('click',closeMenu); document.querySelectorAll('.nav-item').forEach(item=>item.addEventListener('click',closeMenu));
load();
