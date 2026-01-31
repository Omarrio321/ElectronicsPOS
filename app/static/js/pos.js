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
        console.log('[POS] Fetching initial config...');
        try {
            const res = await fetch(`/pos/api/data?_=${new Date().getTime()}`, { headers: { 'Accept': 'application/json' } });
            if (!res.ok) throw new Error('Failed to load config');
            return await res.json();
        } catch (e) {
            console.error('[POS] API Error:', e);
            showToast(e.message);
            throw e;
        }
    },

    getProducts: async (page = 1, categoryId = 'all', search = '') => {
        try {
            const params = new URLSearchParams({
                page: page,
                limit: 24,
                category_id: categoryId,
                q: search
            });
            const res = await fetch(`/pos/api/products?${params.toString()}`);
            if (!res.ok) throw new Error('Failed to load products');
            return await res.json();
        } catch (e) {
            console.error('[POS] Product Load Error:', e);
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
    },

    // ============ CUSTOMER API ============
    searchCustomers: async (query) => {
        const res = await fetch(`/customers/api/search?q=${encodeURIComponent(query)}`);
        return await res.json();
    },

    getCustomer: async (customerId) => {
        const res = await fetch(`/customers/api/${customerId}`);
        return await res.json();
    }
};

/* ================================================================
   State Management
   ================================================================ */
const state = {
    products: [],      // Currently displayed products
    allProducts: [],   // kept for legacy compat if needed, but we rely on current view now
    categories: [],
    cart: [],
    taxRate: 0,

    // Filters & Pagination
    activeCategory: 'all',
    searchQuery: '',
    pagination: {
        page: 1,
        hasMore: true,
        isLoading: false
    },

    selectedPaymentMethod: null,
    // Customer + Sale Type
    selectedCustomer: null,
    saleType: 'RETAIL'
};


/* ================================================================
   Initialization
   ================================================================ */
document.addEventListener('DOMContentLoaded', async () => {
    console.log('[POS] Initializing...');
    await loadInitialData();
    renderCategories();

    // Initial product load
    await loadProducts(true);
    renderCart();

    // Focus search input
    const searchInput = document.getElementById('productSearch');
    if (searchInput) {
        searchInput.focus();

        // Search input handler (Debounced)
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            const val = e.target.value.toLowerCase();
            if (state.searchQuery === val) return;

            state.searchQuery = val;
            document.getElementById('clearSearch').style.display = state.searchQuery ? 'block' : 'none';

            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                loadProducts(true);
            }, 400);
        });

        // Barcode scanning (Enter key)
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                // For barcode, we trigger immediate search
                state.searchQuery = searchInput.value.trim();
                loadProducts(true);
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
            loadProducts(true);
            searchInput.focus();
        });
    }

    // Discount input handler
    const discountInput = document.getElementById('discountInput');
    if (discountInput) {
        discountInput.addEventListener('input', updateTotals);
    }

    // init Load More button
    const loadMoreBtn = document.getElementById('loadMoreBtn');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', () => {
            loadProducts(false);
        });
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
            state.categories = data.categories || [];
            state.taxRate = parseFloat(data.tax_rate || 0);
        } else {
            showToast(data.message || "Failed to load POS configuration");
        }
    } catch (e) {
        showToast("Network Error: " + e.message);
    }
}

async function loadProducts(reset = false) {
    if (state.pagination.isLoading) return;

    if (reset) {
        state.pagination.page = 1;
        state.products = [];
        state.pagination.hasMore = true;
        // Scroll to top of grid
        const grid = document.getElementById('productGrid');
        if (grid) grid.scrollTop = 0;
    }

    if (!state.pagination.hasMore) return;

    state.pagination.isLoading = true;
    updateLoadMoreButton(); // show spinner

    try {
        const data = await API.getProducts(
            state.pagination.page,
            state.activeCategory,
            state.searchQuery
        );

        if (data.success) {
            if (reset) {
                state.products = data.products;
            } else {
                state.products = [...state.products, ...data.products];
            }

            state.pagination.hasMore = data.has_more;
            if (state.pagination.hasMore) {
                state.pagination.page++;
            }
        }
    } catch (e) {
        showToast("Error loading products");
    } finally {
        state.pagination.isLoading = false;
        renderProducts();
        updateLoadMoreButton();
    }
}

function updateLoadMoreButton() {
    const btn = document.getElementById('loadMoreBtn');
    const container = document.getElementById('loadMoreContainer');

    if (!container) return; // Should be added to HTML

    if (!state.pagination.hasMore && state.products.length > 0) {
        container.style.display = 'none';
        return;
    }

    // If we have products and more to load, or if we have 0 products but are loading (initial state)
    if (state.pagination.hasMore) {
        container.style.display = 'block';
        if (state.pagination.isLoading) {
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...';
            btn.disabled = true;
        } else {
            btn.innerHTML = 'Load More';
            btn.disabled = false;
        }
    } else {
        container.style.display = 'none';
    }
}

/* ================================================================
   Barcode Scanning (Re-impl to plain search for now)
   ================================================================ */
// Deprecated specific barcode function in favor of unified search API
// But kept if we want to handle exact match auto-add
function handleBarcodeScand(searchInput) {
    // Logic merged into loadProducts search
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
    if (state.activeCategory === id) return;
    state.activeCategory = id;

    document.querySelectorAll('.category-pill').forEach(x => x.classList.remove('active'));
    el.classList.add('active');

    loadProducts(true);
}

function renderProducts() {
    const grid = document.getElementById('productGrid');
    if (!grid) return;

    if (!state.products.length && !state.pagination.isLoading) {
        grid.innerHTML = `
            <div class="col-12 text-center py-5">
                <i class="fas fa-search fa-3x mb-3 text-muted opacity-25"></i>
                <h5 class="text-muted">No products found</h5>
                <p class="text-muted small">Try adjusting your search or category filter</p>
            </div>
        `;
        return;
    }

    const html = state.products.map(p => `
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

    // We only update innerHTML - this might be jarring if appending, but 'state.products' has ALL currently loaded.
    // Ideally for "Load More" we should append, but full re-render is safer for state sync unless perf is awful.
    // Given < 500 items usually, full render is fine.
    grid.innerHTML = html;
}

/* ================================================================
   Cart Operations
   ================================================================ */
function getProductPrice(product) {
    if (state.saleType === 'WHOLESALE' && product.allow_wholesale && product.wholesale_price) {
        return Number(product.wholesale_price);
    }
    return Number(product.price);
}

function addToCart(id) {
    const p = state.products.find(x => x.id === id);
    if (!p) {
        // Fallback: If product in cart but not in current view (pagination), assume it's valid if in cart?
        // Actually, we must have it to add it.
        // POS usually allows scanning items not in view. 
        // Improvement: If search was by barcode and returned 1 exact match, auto-add.
        return showToast("Product not found (try searching to load it)");
    }

    const existing = state.cart.find(x => x.id === id);
    if (existing) {
        if (existing.quantity < p.stock) {
            existing.quantity++;
            console.log('[POS] Cart item quantity updated:', p.name, existing.quantity);
        } else {
            return showToast("Stock limit reached");
        }
    } else {
        const price = getProductPrice(p);
        state.cart.push({ id: p.id, name: p.name, price: price, quantity: 1, max: p.stock });
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
    initCustomerSearch();
});

/* ================================================================
   Customer Search & Selection
   ================================================================ */
let customerSearchTimeout = null;

function initCustomerSearch() {
    const searchInput = document.getElementById('customerSearch');
    if (!searchInput) return;

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();

        // Clear previous timeout
        if (customerSearchTimeout) clearTimeout(customerSearchTimeout);

        if (query.length < 2) {
            document.getElementById('customerSearchResults').style.display = 'none';
            return;
        }

        // Debounce search
        customerSearchTimeout = setTimeout(() => searchCustomers(query), 300);
    });

    // Close dropdown on outside click
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#customerSearch') && !e.target.closest('#customerSearchResults')) {
            document.getElementById('customerSearchResults').style.display = 'none';
        }
    });
}

async function searchCustomers(query) {
    try {
        const res = await API.searchCustomers(query);
        const resultsDiv = document.getElementById('customerSearchResults');

        if (res.customers && res.customers.length > 0) {
            resultsDiv.innerHTML = res.customers.map(c => `
                <div class="p-2 border-bottom customer-result" style="cursor:pointer;" 
                     onclick="selectCustomer(${c.id}, '${c.name.replace(/'/g, "\\'")}', ${c.balance}, ${c.credit_balance})">
                    <div class="fw-semibold">${c.name}</div>
                    <div class="small text-muted">
                        ${c.phone ? '<i class="fas fa-phone me-1"></i>' + c.phone : ''}
                        ${c.balance > 0 ? '<span class="text-danger ms-2">Balance: $' + c.balance.toFixed(2) + '</span>' : ''}
                        ${c.credit_balance > 0 ? '<span class="text-success ms-2">Credit: $' + c.credit_balance.toFixed(2) + '</span>' : ''}
                    </div>
                </div>
            `).join('');
            resultsDiv.style.display = 'block';
        } else {
            resultsDiv.innerHTML = '<div class="p-2 text-muted">No customers found</div>';
            resultsDiv.style.display = 'block';
        }
    } catch (e) {
        console.error('[POS] Customer Search Error:', e);
    }
}

function selectCustomer(customerId, customerName, balance, creditBalance = 0) {
    state.selectedCustomer = { id: customerId, name: customerName, balance: balance, credit_balance: creditBalance };

    // Update UI
    document.getElementById('customerSearch').value = customerName;
    document.getElementById('selectedCustomerId').value = customerId;
    document.getElementById('customerSearchResults').style.display = 'none';
    document.getElementById('clearCustomerBtn').style.display = 'block';

    // Show balance info
    const balanceDisplay = document.getElementById('customerBalance');
    const infoDiv = document.getElementById('customerInfo');
    if (balance > 0) {
        balanceDisplay.innerHTML = `<span class="text-danger">$${balance.toFixed(2)} outstanding</span>`;
    } else {
        balanceDisplay.innerHTML = `<span class="text-success">No outstanding balance</span>`;
    }
    infoDiv.style.display = 'block';

    // Show partial payment option
    document.getElementById('partialPaymentSection').style.display = 'block';

    updatePaymentTotals();
}

function clearSelectedCustomer() {
    state.selectedCustomer = null;

    document.getElementById('customerSearch').value = '';
    document.getElementById('selectedCustomerId').value = '';
    document.getElementById('clearCustomerBtn').style.display = 'none';
    document.getElementById('customerInfo').style.display = 'none';
    document.getElementById('partialPaymentSection').style.display = 'none';

    // Uncheck partial payment
    const partialCheckbox = document.getElementById('allowPartialPayment');
    if (partialCheckbox) partialCheckbox.checked = false;

    updatePaymentTotals();
}

function updateSaleType() {
    const saleType = document.querySelector('input[name="saleType"]:checked')?.value || 'RETAIL';
    state.saleType = saleType;
    console.log('[POS] Sale type changed to:', saleType);

    // Recalculate prices for all items in cart
    let updated = false;
    state.cart.forEach(item => {
        const product = state.products.find(p => p.id === item.id);
        // If product isn't in current view, we can't update its price accurately if it depends on backend data not loaded.
        // But for wholesale/retail, we usually have data if we loaded it. 
        // With pagination, if user has item in cart that is NOT in current 'state.products', this might fail to update price.
        // Limit: Price update only works for loaded products. 
        // Fix: We should probably store wholesale price in cart item or re-fetch cart items.
        // For now, accept limitation or assume we preserve needed data in cart.

        if (product) {
            const newPrice = getProductPrice(product);
            if (item.price !== newPrice) {
                item.price = newPrice;
                updated = true;
            }
        }
    });

    if (updated) {
        renderCart();
        showToast(`Prices updated to ${saleType} rates`, 'success');
    }
}

// Reset customer state when modal opens
function resetCheckoutModal() {
    clearSelectedCustomer();
    document.getElementById('saleTypeRetail').checked = true;
    state.saleType = 'RETAIL';
}
