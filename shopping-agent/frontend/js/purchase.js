/* purchase.js — Buy Now direct link to marketplace */

function openPurchaseFlow(product) {
  if (!product || !product.product_url) {
    toast('Product link not available', 'err');
    return;
  }
  // Direct link — open product page on the marketplace
  window.open(product.product_url, '_blank', 'noopener,noreferrer');
}
