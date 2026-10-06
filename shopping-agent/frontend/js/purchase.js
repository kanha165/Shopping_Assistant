/* purchase.js — Human-in-the-loop purchase approval flow */

/**
 * FLOW:
 * 1. User clicks "Buy" on a product card → openPurchaseFlow()
 * 2. Approval modal shows: product summary + price breakdown + payment warning
 * 3. User clicks "Confirm" → confirmPurchase()
 *    - Creates order record in DB (status: pending_user_action)
 *    - Calls /orders/approve → agent prepares cart URL
 *    - Shows order confirmation modal with cart URL
 * 4. User clicks "Open Cart & Pay" → opens marketplace in new tab
 * 5. User completes payment on the platform (agent never touches this step)
 * 6. Optional: user can update order with external_order_id
 *
 * Agent NEVER: handles CVV, OTP, PIN, passwords, or payment credentials.
 */

// Currently selected product for purchase
let _pendingProduct = null;
let _pendingOrderId = null;

async function openPurchaseFlow(product) {
  _pendingProduct = typeof product === 'string' ? JSON.parse(product) : product;
  State.pendingProduct = _pendingProduct;

  const p = _pendingProduct;
  const shipping = p.shipping_cost || 0;
  const total    = p.total_cost || (p.price + shipping) || p.price;

  document.getElementById('approval-modal-body').innerHTML = `
    <h2 style="margin-bottom:16px;font-size:1.1rem">Confirm Purchase</h2>
    <div class="approval-box">

      <!-- Product summary -->
      <div class="approval-product">
        ${p.image_url
          ? `<img class="approval-img" src="${esc(p.image_url)}" alt="${esc(p.product_name)}"
               onerror="this.src=''"/>`
          : `<div class="approval-img" style="display:flex;align-items:center;justify-content:center;font-size:2.5rem;background:#f5f5f5;border-radius:6px">🛍️</div>`}
        <div>
          <span class="platform-badge pb-${esc(p.platform)}">${esc(p.platform)}</span>
          <div class="approval-name">${esc(p.product_name)}</div>
          ${p.seller ? `<div style="font-size:.78rem;color:#777">Sold by ${esc(p.seller)}</div>` : ''}
          ${p.delivery_info ? `<div style="font-size:.78rem;color:#555;margin-top:4px">🚚 ${esc(p.delivery_info)}</div>` : ''}
        </div>
      </div>

      <!-- Price breakdown -->
      <div class="price-breakdown">
        <div class="pb-row">
          <span>Product Price</span>
          <span>${fmtPrice(p.price)}</span>
        </div>
        ${p.original_price && p.original_price > p.price ? `
        <div class="pb-row" style="color:#188038">
          <span>Discount (${Math.round(p.discount_percent||0)}% off)</span>
          <span>−${fmtPrice(p.original_price - p.price)}</span>
        </div>` : ''}
        <div class="pb-row">
          <span>Shipping</span>
          <span>${shipping > 0 ? fmtPrice(shipping) : 'Free'}</span>
        </div>
        <div class="pb-row">
          <span>Total Payable</span>
          <span style="color:#1a73e8">${fmtPrice(total)}</span>
        </div>
      </div>

      <!-- Payment safety warning -->
      <div class="payment-warning">
        🔒 <strong>Your payment is secure</strong><br/>
        The AI agent stops here. You will be taken to <strong>${esc(p.platform)}</strong>
        to complete your payment. <br/>
        <strong>CVV, OTP, PIN, and passwords are never stored or handled by this system.</strong>
      </div>

      <!-- Actions -->
      <div class="approval-actions">
        <button class="btn-outline" onclick="closeModal('approval-modal')">Cancel</button>
        <button class="btn-primary" onclick="confirmPurchase()" id="btn-confirm-purchase">
          ✅ Confirm &amp; Proceed to Cart
        </button>
      </div>
    </div>
  `;

  openModal('approval-modal');
}

async function confirmPurchase() {
  const p = _pendingProduct;
  if (!p) return;

  const btn = document.getElementById('btn-confirm-purchase');
  btn.disabled = true;
  btn.textContent = 'Processing…';

  try {
    // Step 1: Create order record
    const orderPayload = {
      session_id:       State.sessionId,
      search_id:        State.currentSearchId,
      product_id:       p.id || null,
      product_name:     p.product_name,
      brand:            p.brand || null,
      platform:         p.platform,
      marketplace_url:  p.product_url,
      image_url:        p.image_url || null,
      amount:           p.price,
      original_amount:  p.original_price || null,
      shipping_cost:    p.shipping_cost || 0,
      total_amount:     p.total_cost || p.price,
      currency:         'INR',
      discount_percent: p.discount_percent || null,
      delivery_address_id: null,
    };

    const order = await Api.createOrder(orderPayload);
    _pendingOrderId = order.id;
    State.pendingOrder = order;

    // Step 2: User approves → agent prepares cart
    const approved = await Api.approveOrder(order.id, true);

    closeModal('approval-modal');
    showOrderConfirmation(approved, p);

  } catch(e) {
    toast('Could not process order: ' + e.message, 'err');
    btn.disabled = false;
    btn.textContent = '✅ Confirm & Proceed to Cart';
  }
}

function showOrderConfirmation(order, product) {
  const targetUrl = product.product_url || order.cart_url || order.marketplace_url;

  document.getElementById('order-modal-body').innerHTML = `
    <div class="order-confirm">
      <div class="order-icon">🛍️</div>
      <h2 style="font-size:1.15rem;margin-bottom:4px">Ready to Complete Order!</h2>
      <p style="font-size:.85rem;color:#555;margin-bottom:16px">
        Click below to open the product page on <strong>${esc(product.platform)}</strong>, then click <strong>"Buy Now"</strong> or <strong>"Add to Cart"</strong>.
      </p>

      <div class="order-detail-box" style="text-align:left;width:100%">
        <div class="od-row">
          <span class="od-label">Product</span>
          <span class="od-val" style="max-width:220px">${esc(product.product_name.slice(0,60))}…</span>
        </div>
        <div class="od-row">
          <span class="od-label">Platform</span>
          <span class="od-val">
            <span class="platform-badge pb-${esc(product.platform)}">${esc(product.platform)}</span>
          </span>
        </div>
        <div class="od-row">
          <span class="od-label">Total Payable</span>
          <span class="od-val" style="color:#1a73e8;font-size:1rem">${fmtPrice(order.total_amount)}</span>
        </div>
        ${product.delivery_info ? `
        <div class="od-row">
          <span class="od-label">Delivery</span>
          <span class="od-val">${esc(product.delivery_info)}</span>
        </div>` : ''}
        <div class="od-row">
          <span class="od-label">Order #</span>
          <span class="od-val" style="color:#888">${order.id}</span>
        </div>
      </div>

      <div class="payment-warning" style="width:100%;text-align:left">
        🔒 <strong>Agent stops here for payment safety.</strong><br/>
        Click the button below to open <strong>${esc(product.platform)}</strong>.
        Complete payment yourself — CVV, OTP, and PIN are never handled by this system.
      </div>

      <a class="btn-primary btn-full"
         href="${esc(targetUrl)}"
         target="_blank"
         rel="noopener"
         style="display:block;text-decoration:none;text-align:center;padding:12px;margin-top:4px">
        Open Product on ${esc(product.platform)} &amp; Buy Now →
      </a>

      <button class="btn-ghost btn-sm" style="margin-top:8px;width:100%"
        onclick="promptOrderUpdate(${order.id})">
        Already paid? Update order status
      </button>
    </div>
  `;

  openModal('order-modal');
}

async function promptOrderUpdate(orderId) {
  const extId = prompt('Enter the Order ID from ' + (State.pendingProduct?.platform || 'the platform') + ' (optional):');
  if (extId === null) return; // cancelled

  try {
    await Api.updateOrder(orderId, {
      external_order_id: extId || null,
      status: 'confirmed',
    });
    toast('Order updated! Check My Orders for details.', 'ok');
    closeModal('order-modal');
  } catch(e) {
    toast('Could not update order: ' + e.message, 'err');
  }
}
