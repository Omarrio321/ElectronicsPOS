/**
 * =================================================================
 * POS Terminal - Core Logic
 * Electronics POS System
 * =================================================================
 */

/* ================================================================
   API Helpers
   ================================================================ */
const API = {
    getData: async () => {
        console.log('[POS] Fetching initial data...');
        try {
            const res = await fetch('/pos/api/data', { headers: { 'Accept': 'application/json' } });
            if (!res.ok) throw new Error('Failed to load data');
            const data = await res.json();
            console.log('[POS] Data loaded:', data.products?.length, 'products,', data.categories?.length, 'categories');
            return data;
        } catch (e) {
            console.error('[POS] API Error:', e);
            showToast(e.message);
            throw e;
        }
    },

    checkout: async (payload) => {
        console.log('[POS] Processing checkout:', payload);
        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            if (!csrfToken) throw new Error("CSRF Token missing");

            const res = await fetch('/pos/api/checkout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'Accept': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const txt = await res.text();
                let err = "Checkout failed";
                try { const j = JSON.parse(txt); err = j.message || err; } catch (e) { err = txt.substring(0, 200); }
                throw new Error(err);
            }
            return await res.json();
        } catch (e) {
            console.error('[POS] Checkout Error:', e);
            throw e;
        }
    },

    // ============ HOLD SALE API ============
    holdSale: async (cart, customerName) => {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const res = await fetch('/pos/api/hold', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify({ cart, customer_name: customerName })
        });
        return await res.json();
    },

    getHeldSales: async () => {
        const res = await fetch('/pos/api/held');
        return await res.json();
    },

    resumeHeldSale: async (heldId) => {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const res = await fetch(`/pos/api/held/${heldId}/resume`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken }
        });
        return await res.json();
    },

    deleteHeldSale: async (heldId) => {
        const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
        const res = await fetch(`/pos/api/held/${heldId}`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': csrfToken }
        });
        return await res.json();
    }
};

/* ================================================================
   State Management
   ================================================================ */
const state = {
    products: [],
    categories: [],
    cart: [],
    taxRate: 0,
    activeCategory: 'all',
    searchQuery: '',
    selectedPaymentMethod: null
};

/* ================================================================
   Initialization
   ================================================================ */
document.addEventListener('DOMContentLoaded', async () => {
    console.log('[POS] Initializing...');
    await loadInitialData();
    renderCategories();
    renderProducts();
    renderCart();

    // Focus search input
    const searchInput = document.getElementById('productSearch');
    if (searchInput) {
        searchInput.focus();

        // Search input handler
        searchInput.addEventListener('input', (e) => {
            state.searchQuery = e.target.value.toLowerCase();
            document.getElementById('clearSearch').style.display = state.searchQuery ? 'block' : 'none';
            renderProducts();
        });

        // Barcode scanning (Enter key)
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                handleBarcodeScand(searchInput);
            }
        });
    }

    // Clear search button
    const clearSearchBtn = document.getElementById('clearSearch');
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', () => {
            searchInput.value = '';
            state.searchQuery = '';
            clearSearchBtn.style.display = 'none';
            renderProducts();
            searchInput.focus();
        });
    }

    // Discount input handler
    const discountInput = document.getElementById('discountInput');
    if (discountInput) {
        discountInput.addEventListener('input', updateTotals);
    }

    console.log('[POS] Initialization complete');
});

/* ================================================================
   Data Loading
   ================================================================ */
async function loadInitialData() {
    try {
        const data = await API.getData();
        if (data.success) {
            state.products = data.products || [];
            state.categories = data.categories || [];
            state.taxRate = parseFloat(data.tax_rate || 0);
        } else {
            showToast(data.message || "Failed to load POS data");
        }
    } catch (e) {
        showToast("Network Error: " + e.message);
    }
}

/* ================================================================
   Barcode Scanning
   ================================================================ */
function handleBarcodeScand(searchInput) {
    const barcode = searchInput.value.trim();
    if (!barcode) return;

    const product = state.products.find(p => p.barcode === barcode);
    if (product) {
        if (product.stock <= 0) {
            showToast(`Product ${product.name} is out of stock`, 'danger');
        } else {
            addToCart(product.id);
            showToast(`Scanned: ${product.name}`, 'success');

            // Clear and refocus
            searchInput.value = '';
            state.searchQuery = '';
            document.getElementById('clearSearch').style.display = 'none';
            renderProducts();
            searchInput.focus();
        }
    } else {
        showToast(`No product found with barcode: ${barcode}`, 'danger');
    }
}

/* ================================================================
   Category & Product Rendering
   ================================================================ */
function renderCategories() {
    const el = document.getElementById('categoryList');
    if (!el) return;

    if (!state.categories.length) {
        el.innerHTML = `<span class="category-pill active" onclick="filter('all', this)">All Items</span>`;
        return;
    }
    el.innerHTML = `<span class="category-pill active" onclick="filter('all', this)">All Items</span>` +
        state.categories.map(c => `<span class="category-pill" onclick="filter(${c.id}, this)">${escapeHtml(c.name)}</span>`).join('');
}

function filter(id, el) {
    state.activeCategory = id;
    document.querySelectorAll('.category-pill').forEach(x => x.classList.remove('active'));
    el.classList.add('active');
    renderProducts();
}

function renderProducts() {
    let list = state.activeCategory === 'all'
        ? state.products
        : state.products.filter(p => p.category_id === state.activeCategory);

    // Apply search filter
    if (state.searchQuery) {
        list = list.filter(p =>
            p.name.toLowerCase().includes(state.searchQuery) ||
            (p.sku && p.sku.toLowerCase().includes(state.searchQuery)) ||
            (p.barcode && p.barcode.toLowerCase().includes(state.searchQuery))
        );
    }

    const grid = document.getElementById('productGrid');
    if (!grid) return;

    if (!list.length) {
        grid.innerHTML = `
            <div class="col-12 text-center py-5">
                <i class="fas fa-search fa-3x mb-3 text-muted opacity-25"></i>
                <h5 class="text-muted">No products found</h5>
                <p class="text-muted small">Try adjusting your search or category filter</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = list.map(p => `
        <div class="product-card ${p.stock <= 0 ? 'out-of-stock' : ''}" onclick="addToCart(${p.id})" title="${escapeHtml(p.name)}">
            <div>
                <div class="product-name">${escapeHtml(p.name)}</div>
                <div class="product-sku">${escapeHtml(p.sku || '')}</div>
            </div>
            <div class="product-bottom">
                <div class="text-primary fw-bold">$${Number(p.price).toFixed(2)}</div>
                <div><span class="badge badge-stock ${p.stock < 5 ? 'bg-danger' : 'bg-secondary'}">Stock: ${p.stock}</span></div>
            </div>
        </div>
    `).join('');
}

/* ================================================================
   Cart Operations
   ================================================================ */
function addToCart(id) {
    const p = state.products.find(x => x.id === id);
    if (!p) return showToast("Product not found");

    const existing = state.cart.find(x => x.id === id);
    if (existing) {
        if (existing.quantity < p.stock) {
            existing.quantity++;
            console.log('[POS] Cart item quantity updated:', p.name, existing.quantity);
        } else {
            return showToast("Stock limit reached");
        }
    } else {
        state.cart.push({ id: p.id, name: p.name, price: Number(p.price), quantity: 1, max: p.stock });
        console.log('[POS] Added to cart:', p.name);
    }
    renderCart();
}

function renderCart() {
    const container = document.getElementById('cartList');
    if (!container) return;

    if (!state.cart.length) {
        container.innerHTML = `
            <div class="text-center text-muted py-5">
                <i class="fas fa-basket-shopping fa-3x mb-3 opacity-25"></i>
                <p class="mb-1">Cart is empty</p>
                <p class="small mb-0">Click products to add them</p>
            </div>
        `;
        updateTotals();
        const itemCount = document.getElementById('itemCount');
        if (itemCount) itemCount.innerText = `0 Items`;
        return;
    }

    container.innerHTML = state.cart.map((i, idx) => `
        <div class="cart-item-row" role="group" aria-label="${escapeHtml(i.name)}">
            <div class="cart-item-info">
                <div class="name">${escapeHtml(i.name)}</div>
                <div class="meta">$${Number(i.price).toFixed(2)} × ${i.quantity}</div>
            </div>
            <div class="qty-controls">
                <button class="qty-btn" onclick="chgQty(${idx}, -1)" aria-label="Decrease quantity">−</button>
                <span aria-live="polite">${i.quantity}</span>
                <button class="qty-btn" onclick="chgQty(${idx}, 1)" aria-label="Increase quantity">+</button>
            </div>
            <div class="cart-item-total">$${(i.price * i.quantity).toFixed(2)}</div>
        </div>
    `).join('');

    const itemCount = document.getElementById('itemCount');
    if (itemCount) itemCount.innerText = `${state.cart.reduce((a, b) => a + b.quantity, 0)} Items`;

    updateTotals();
    localStorage.setItem('pos_cart', JSON.stringify(state.cart));
}

function chgQty(idx, delta) {
    const item = state.cart[idx];
    if (!item) return;
    const newQ = item.quantity + delta;
    if (newQ <= 0) {
        state.cart.splice(idx, 1);
        console.log('[POS] Removed from cart:', item.name);
    } else if (newQ > item.max) {
        return showToast("Max stock reached");
    } else {
        item.quantity = newQ;
    }
    renderCart();
}

/* ================================================================
   Totals Calculation
   ================================================================ */
function updateTotals() {
    const sub = state.cart.reduce((a, b) => a + (b.price * b.quantity), 0);
    const discountInput = document.getElementById('discountInput');
    const disc = discountInput ? (parseFloat(discountInput.value) || 0) : 0;
    const tax = Math.max(0, sub - disc) * (state.taxRate || 0);
    const total = sub - disc + tax;

    // Update sidebar totals
    const subtotalDisplay = document.getElementById('subtotalDisplay');
    const taxDisplay = document.getElementById('taxDisplay');
    const totalDisplay = document.getElementById('totalDisplay');

    if (subtotalDisplay) subtotalDisplay.innerText = `$${sub.toFixed(2)}`;
    if (taxDisplay) taxDisplay.innerText = `$${tax.toFixed(2)}`;
    if (totalDisplay) totalDisplay.innerText = `$${total.toFixed(2)}`;

    // Update checkout button state
    const checkoutBtn = document.getElementById('checkoutBtn');
    if (checkoutBtn) {
        checkoutBtn.disabled = state.cart.length === 0;
    }

    // Update modal totals if modal elements exist
    const modalSubtotal = document.getElementById('modalSubtotal');
    if (modalSubtotal) {
        modalSubtotal.innerText = `$${sub.toFixed(2)}`;
        const modalTax = document.getElementById('modalTax');
        if (modalTax) modalTax.innerText = `$${tax.toFixed(2)}`;
        const modalDiscountDisplay = document.getElementById('modalDiscountDisplay');
        if (modalDiscountDisplay) modalDiscountDisplay.innerText = `-$${disc.toFixed(2)}`;
        const modalGrandTotal = document.getElementById('modalGrandTotal');
        if (modalGrandTotal) modalGrandTotal.innerText = `$${total.toFixed(2)}`;
    }

    // Update payment totals (defined in payment.js)
    if (typeof updatePaymentTotals === 'function') {
        updatePaymentTotals();
    }
}

/* ================================================================
   UI Helpers
   ================================================================ */
function showToast(msg, type = 'danger') {
    const t = document.getElementById('liveToast');
    const toastBody = document.getElementById('toastMessage');
    if (!t || !toastBody) return;

    // Set alert type
    t.classList.remove('bg-danger', 'bg-success', 'bg-primary');
    t.classList.add(`bg-${type}`);

    toastBody.innerText = msg;
    new bootstrap.Toast(t).show();
}

function escapeHtml(str = '') {
    return String(str).replace(/[&<>"']/g, s => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": "&#39;" }[s]));
}

/* ================================================================
   HOLD SALE FUNCTIONS
   ================================================================ */

// State for held sales
let heldSalesCache = [];

async function holdCurrentSale() {
    if (state.cart.length === 0) {
        showToast('Cart is empty. Nothing to hold.', 'danger');
        return;
    }

    // Prompt for customer name (optional)
    const customerName = prompt('Enter customer name (optional):') || '';

    try {
        const res = await API.holdSale(state.cart, customerName);
        if (res.success) {
            // Clear the current cart
            state.cart = [];
            localStorage.removeItem('pos_cart');
            renderCart();

            showToast(`Sale held${customerName ? ' for ' + customerName : ''}`, 'success');

            // Refresh held sales badge
            loadHeldSalesCount();
        } else {
            showToast(res.message || 'Failed to hold sale', 'danger');
        }
    } catch (e) {
        console.error('[POS] Hold Sale Error:', e);
        showToast('Error holding sale: ' + e.message, 'danger');
    }
}

async function loadHeldSalesCount() {
    try {
        const res = await API.getHeldSales();
        if (res.success) {
            heldSalesCache = res.held_sales || [];
            const badge = document.getElementById('heldSalesBadge');
            if (badge) {
                badge.textContent = heldSalesCache.length;
                badge.style.display = heldSalesCache.length > 0 ? 'inline-block' : 'none';
            }
        }
    } catch (e) {
        console.error('[POS] Load Held Sales Error:', e);
    }
}

function showHeldSalesModal() {
    loadHeldSalesModal();
    const modal = document.getElementById('heldSalesModal');
    if (modal) {
        bootstrap.Modal.getOrCreateInstance(modal).show();
    }
}

async function loadHeldSalesModal() {
    try {
        const res = await API.getHeldSales();
        if (res.success) {
            heldSalesCache = res.held_sales || [];
            renderHeldSalesList();
        }
    } catch (e) {
        console.error('[POS] Load Held Sales Error:', e);
    }
}

function renderHeldSalesList() {
    const container = document.getElementById('heldSalesList');
    if (!container) return;

    if (heldSalesCache.length === 0) {
        container.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="fas fa-inbox fa-2x mb-2 opacity-50"></i>
                <p class="mb-0">No held sales</p>
            </div>
        `;
        return;
    }

    container.innerHTML = heldSalesCache.map(hs => `
        <div class="held-sale-item d-flex justify-content-between align-items-center p-3 border-bottom">
            <div>
                <div class="fw-semibold">${escapeHtml(hs.customer_name)}</div>
                <div class="small text-muted">
                    ${hs.item_count} item${hs.item_count > 1 ? 's' : ''} · $${hs.total_amount.toFixed(2)} · ${hs.created_at}
                </div>
            </div>
            <div class="btn-group">
                <button class="btn btn-success btn-sm" onclick="resumeSale(${hs.id})" title="Resume">
                    <i class="fas fa-play"></i>
                </button>
                <button class="btn btn-outline-danger btn-sm" onclick="deleteSale(${hs.id})" title="Delete">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

async function resumeSale(heldId) {
    // Check if current cart has items
    if (state.cart.length > 0) {
        const confirm = window.confirm('Current cart has items. Hold current cart before resuming?');
        if (confirm) {
            await holdCurrentSale();
        } else {
            // Clear current cart without holding
            state.cart = [];
            localStorage.removeItem('pos_cart');
        }
    }

    try {
        const res = await API.resumeHeldSale(heldId);
        if (res.success) {
            // Load the held cart into state
            state.cart = res.cart || [];
            localStorage.setItem('pos_cart', JSON.stringify(state.cart));
            renderCart();

            // Close the modal
            const modal = document.getElementById('heldSalesModal');
            if (modal) {
                bootstrap.Modal.getInstance(modal)?.hide();
            }

            showToast(`Sale resumed${res.customer_name ? ' for ' + res.customer_name : ''}`, 'success');
            loadHeldSalesCount();
        } else {
            showToast(res.message || 'Failed to resume sale', 'danger');
        }
    } catch (e) {
        console.error('[POS] Resume Sale Error:', e);
        showToast('Error resuming sale: ' + e.message, 'danger');
    }
}

async function deleteSale(heldId) {
    if (!confirm('Delete this held sale?')) return;

    try {
        const res = await API.deleteHeldSale(heldId);
        if (res.success) {
            showToast('Held sale deleted', 'success');
            loadHeldSalesModal();
            loadHeldSalesCount();
        } else {
            showToast(res.message || 'Failed to delete', 'danger');
        }
    } catch (e) {
        console.error('[POS] Delete Sale Error:', e);
        showToast('Error deleting sale: ' + e.message, 'danger');
    }
}

// Load held sales count on init
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(loadHeldSalesCount, 500);
});
