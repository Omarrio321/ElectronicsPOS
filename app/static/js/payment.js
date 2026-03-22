/**
 * =================================================================
 * POS Terminal - Payment & Modal Logic
 * Electronics POS System
 *
 * Dual-currency support: USD (base) + SLSH (secondary)
 * Card is restricted to USD only.
 * Exchange rate: 1 USD = X SLSH (loaded from server on POS init)
 * =================================================================
 */

/* ================================================================
   Modal State - Single Instance Pattern
   ================================================================ */
let checkoutModalInstance = null;
let isModalInitialized = false;

/* ================================================================
   Debug Logging (can be disabled in production)
   ================================================================ */
const DEBUG = false;
function logDebug(...args) {
    if (DEBUG) console.log('[Payment]', ...args);
}

function debugModalState() {
    if (!DEBUG) return;
    const backdrops = document.querySelectorAll('.modal-backdrop');
    logDebug('Backdrop count:', backdrops.length);
    logDebug('Body has modal-open:', document.body.classList.contains('modal-open'));
}

/* ================================================================
   Initialize Modal - Called ONCE on page load
   ================================================================ */
function initializeCheckoutModal() {
    if (isModalInitialized) return;

    const modalElement = document.getElementById('checkoutModal');
    if (!modalElement) {
        console.error('[Payment] Cannot initialize - modal element not found');
        return;
    }

    if (modalElement.parentElement !== document.body) {
        document.body.appendChild(modalElement);
    }

    checkoutModalInstance = bootstrap.Modal.getOrCreateInstance(modalElement, {
        backdrop: true,
        keyboard: true,
        focus: true
    });

    modalElement.addEventListener('hidden.bs.modal', onModalHidden);
    modalElement.addEventListener('shown.bs.modal', onModalShown);
    modalElement.addEventListener('hide.bs.modal', onModalHide);

    isModalInitialized = true;
    logDebug('Modal initialized successfully');
}

/* ================================================================
   Modal Event Handlers
   ================================================================ */
function onModalShown() { logDebug('EVENT: shown.bs.modal'); }
function onModalHide()   { logDebug('EVENT: hide.bs.modal'); }

function onModalHidden() {
    logDebug('EVENT: hidden.bs.modal');
    forceCleanupModalState();
}

function forceCleanupModalState() {
    document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');

    const modalEl = document.getElementById('checkoutModal');
    if (modalEl) {
        modalEl.classList.remove('show');
        modalEl.style.display = 'none';
        modalEl.setAttribute('aria-hidden', 'true');
        modalEl.removeAttribute('aria-modal');
        modalEl.removeAttribute('role');
    }
}

/* ================================================================
   Open Checkout Modal
   ================================================================ */
function openCheckoutModal() {
    if (state.cart.length === 0) {
        showToast("Please add items to cart first");
        return;
    }

    try {
        const modalElement = document.getElementById('checkoutModal');
        if (!modalElement) { showToast("Error: Modal not found"); return; }

        if (!isModalInitialized) initializeCheckoutModal();

        // Pre-cleanup stale backdrops
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        document.body.classList.remove('modal-open');

        checkoutModalInstance = bootstrap.Modal.getOrCreateInstance(modalElement);

        populateModalCart();
        clearPayments();
        updateModalTotals();
        updatePaymentTotals();

        checkoutModalInstance.show();

    } catch (error) {
        console.error('[Payment] Error opening modal:', error);
        showToast("Error opening checkout: " + error.message);
        forceCleanupModalState();
    }
}

/* ================================================================
   Close Checkout Modal
   ================================================================ */
function closeCheckoutModal() {
    if (checkoutModalInstance) {
        checkoutModalInstance.hide();
    } else {
        forceCleanupModalState();
    }
}

/* ================================================================
   Modal Content Population
   ================================================================ */
function populateModalCart() {
    const modalCartItems = document.getElementById('modalCartItems');
    if (!modalCartItems) return;

    modalCartItems.innerHTML = state.cart.map(i => `
        <div class="d-flex justify-content-between align-items-center mb-2">
            <div>
                <span class="fw-semibold">${escapeHtml(i.name)}</span>
                <span class="text-muted small ms-2">×${i.quantity}</span>
            </div>
            <span class="fw-semibold">$${(i.price * i.quantity).toFixed(2)}</span>
        </div>
    `).join('');
}

function updateModalTotals() {
    const sub = state.cart.reduce((a, b) => a + (b.price * b.quantity), 0);
    const discountInput = document.getElementById('discountInput');
    const disc = discountInput ? (parseFloat(discountInput.value) || 0) : 0;
    const taxable = Math.max(0, sub - disc);
    const tax = taxable * (state.taxRate || 0);
    const total = taxable + tax;

    const rate = state.exchangeRate || 1000;

    const set = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
    set('modalSubtotal', `$${sub.toFixed(2)}`);
    set('modalTax', `$${tax.toFixed(2)}`);
    set('modalDiscountDisplay', `-$${disc.toFixed(2)}`);
    set('modalGrandTotal', `$${total.toFixed(2)}`);

    // Show SLSH equivalent of total
    const slshEl = document.getElementById('modalGrandTotalSLSH');
    if (slshEl) slshEl.innerText = `SLSH ${Math.round(total * rate).toLocaleString()}`;

    // Show exchange rate
    const rateEl = document.getElementById('exchangeRateDisplay');
    if (rateEl) rateEl.innerText = `1 USD = ${rate.toLocaleString()} SLSH`;
}

/* ================================================================
   Exchange Rate Helper
   ================================================================ */
function getExchangeRate() {
    return state.exchangeRate || 1000;
}

/* ================================================================
   Grand Total Calculation (USD)
   ================================================================ */
function getGrandTotal() {
    const sub = state.cart.reduce((a, b) => a + (b.price * b.quantity), 0);
    const discountInput = document.getElementById('discountInput');
    const disc = discountInput ? (parseFloat(discountInput.value) || 0) : 0;
    const taxable = Math.max(0, sub - disc);
    const tax = taxable * (state.taxRate || 0);
    return taxable + tax;
}

/* ================================================================
   Payment Amount Helpers - returns USD equivalents
   ================================================================ */

/**
 * Get raw (original-currency) values from all inputs.
 * Used for building the payments array to submit.
 */
function getRawPaymentInputs() {
    const rate = getExchangeRate();
    return {
        cash_usd:    parseFloat(document.getElementById('payCash_usd')?.value)    || 0,
        cash_slsh:   parseFloat(document.getElementById('payCash_slsh')?.value)   || 0,
        card_usd:    parseFloat(document.getElementById('payCard')?.value)         || 0,
        edahab_usd:  parseFloat(document.getElementById('payEDahab_usd')?.value)  || 0,
        edahab_slsh: parseFloat(document.getElementById('payEDahab_slsh')?.value) || 0,
        zaad_usd:    parseFloat(document.getElementById('payZaad_usd')?.value)    || 0,
        zaad_slsh:   parseFloat(document.getElementById('payZaad_slsh')?.value)   || 0,
        storeCredit: parseFloat(document.getElementById('payStoreCredit')?.value) || 0,
        rate
    };
}

/**
 * Return USD-equivalent totals for all payment inputs.
 * SLSH amounts are divided by the exchange rate.
 */
function getPaymentAmountsUSD() {
    const raw = getRawPaymentInputs();
    const r = raw.rate;
    return {
        cash:        raw.cash_usd    + (raw.cash_slsh   / r),
        card:        raw.card_usd,
        edahab:      raw.edahab_usd  + (raw.edahab_slsh / r),
        zaad:        raw.zaad_usd    + (raw.zaad_slsh   / r),
        storeCredit: raw.storeCredit
    };
}

/* ================================================================
   Live SLSH→USD Hint Updates
   ================================================================ */
function updateSlshHint(slshInputId, hintId) {
    const rate = getExchangeRate();
    const slsh = parseFloat(document.getElementById(slshInputId)?.value) || 0;
    const hintEl = document.getElementById(hintId);
    if (hintEl) {
        hintEl.innerText = slsh > 0 ? `≈ $${(slsh / rate).toFixed(2)}` : '';
    }
}

/* ================================================================
   Update Payment Totals (called on any input change)
   ================================================================ */
// Helper to toggle visibility for d-flex elements
function toggleFlexRow(el, show) {
    if (!el) return;
    if (show) {
        el.classList.remove('d-none');
        el.classList.add('d-flex');
        el.style.display = '';
    } else {
        el.classList.remove('d-flex');
        el.classList.add('d-none');
        el.style.display = 'none';
    }
}

function updatePaymentTotals() {
    try {
        const remainingRow    = document.getElementById('remainingRow');
        const changeRow       = document.getElementById('changeRow');
        const completeBtn     = document.getElementById('completeBtn');
        const amountDueRow    = document.getElementById('amountDueRow');
        const totalPaidDisplay = document.getElementById('totalPaidDisplay');
        const digitalOverpayError = document.getElementById('digitalOverpayError');
        const paymentError    = document.getElementById('paymentError');

        if (!remainingRow || !changeRow || !completeBtn) return;

        updateModalTotals();  // Refresh totals (in case discount changed)

        const grandTotal = getGrandTotal();
        const amounts    = getPaymentAmountsUSD();
        const totalPaid  = amounts.cash + amounts.card + amounts.edahab + amounts.zaad + amounts.storeCredit;
        const digitalPaid = amounts.card + amounts.edahab + amounts.zaad + amounts.storeCredit;

        const remaining = Math.max(0, parseFloat((grandTotal - totalPaid).toFixed(2)));
        const change    = Math.max(0, parseFloat((totalPaid - grandTotal).toFixed(2)));

        if (totalPaidDisplay) totalPaidDisplay.innerText = `$${totalPaid.toFixed(2)}`;

        const partialCheckbox = document.getElementById('allowPartialPayment');
        const allowPartial = partialCheckbox && partialCheckbox.checked && state.selectedCustomer;
        const isDigitalOverpay = digitalPaid > grandTotal + 0.005;

        // Reset errors
        if (paymentError) paymentError.style.display = 'none';
        if (digitalOverpayError) digitalOverpayError.style.display = 'none';
        toggleFlexRow(amountDueRow, false);

        // --- Store Credit UI ---
        const storeCreditCard = document.getElementById('storeCreditCard');
        const payStoreCredit  = document.getElementById('payStoreCredit');
        const storeCreditAvailable = document.getElementById('storeCreditAvailable');
        if (storeCreditCard && payStoreCredit) {
            const customer = state.selectedCustomer;
            if (customer && customer.credit_balance > 0) {
                storeCreditCard.style.display = 'flex';
                if (storeCreditAvailable) storeCreditAvailable.innerText = `$${parseFloat(customer.credit_balance).toFixed(2)}`;
                const entered = parseFloat(payStoreCredit.value) || 0;
                payStoreCredit.classList.toggle('is-invalid', entered > customer.credit_balance);
            } else {
                storeCreditCard.style.display = 'none';
                payStoreCredit.value = '';
            }
        }

        // --- Highlight active cards ---
        ['payCash_usd', 'payCash_slsh', 'payCard', 'payEDahab_usd', 'payEDahab_slsh',
         'payZaad_usd', 'payZaad_slsh'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                const card = el.closest('.payment-method-card');
                if (card) {
                    const hasValue = [...card.querySelectorAll('input[type="number"]')]
                        .some(inp => parseFloat(inp.value) > 0);
                    card.classList.toggle('active', hasValue);
                }
            }
        });

        // --- Decision logic ---
        if (isDigitalOverpay) {
            toggleFlexRow(remainingRow, false);
            toggleFlexRow(changeRow, false);
            completeBtn.disabled = true;
            if (digitalOverpayError) digitalOverpayError.style.display = 'block';
        } else if (remaining > 0.005) {
            if (allowPartial) {
                toggleFlexRow(remainingRow, false);
                toggleFlexRow(changeRow, false);
                toggleFlexRow(amountDueRow, true);
                const amountDueDisplay = document.getElementById('amountDueDisplay');
                if (amountDueDisplay) amountDueDisplay.innerText = `$${remaining.toFixed(2)}`;
                completeBtn.disabled = false;
            } else {
                toggleFlexRow(remainingRow, true);
                toggleFlexRow(changeRow, false);
                const remainingDisplay = document.getElementById('remainingDisplay');
                if (remainingDisplay) remainingDisplay.innerText = `$${remaining.toFixed(2)}`;
                completeBtn.disabled = true;
                if (paymentError && totalPaid <= 0) paymentError.style.display = 'block';
            }
        } else {
            // Paid in full or cash overpayment
            toggleFlexRow(remainingRow, false);
            toggleFlexRow(changeRow, true);
            const changeDisplay = document.getElementById('changeDisplay');
            if (changeDisplay) {
                const rate = getExchangeRate();
                changeDisplay.innerText = `$${change.toFixed(2)}`;
                const slshHint = document.getElementById('changeSlshHint');
                if (slshHint) slshHint.innerText = change > 0 ? ` (≈ ${Math.round(change * rate).toLocaleString()} SLSH)` : '';
            }
            completeBtn.disabled = false;
        }

    } catch (e) {
        console.error("Error in updatePaymentTotals", e);
    }
}

/* ================================================================
   UI Helpers
   ================================================================ */
function focusPaymentInput(inputId) {
    const el = document.getElementById(inputId);
    if (el) el.focus();
}

function useMaxCredit(e) {
    if (e) e.preventDefault();
    const grandTotal = getGrandTotal();
    const amounts = getPaymentAmountsUSD();
    const otherPayments = amounts.cash + amounts.card + amounts.edahab + amounts.zaad;
    const remainingToPay = Math.max(0, grandTotal - otherPayments);
    const customer = state.selectedCustomer;
    if (!customer || !customer.credit_balance) return;
    const available = parseFloat(customer.credit_balance);
    const useAmount = Math.min(remainingToPay, available);
    const input = document.getElementById('payStoreCredit');
    if (input) { input.value = useAmount.toFixed(2); updatePaymentTotals(); }
}

/* ================================================================
   Clear Payments
   ================================================================ */
function clearPayments() {
    const fields = [
        'payCash_usd', 'payCash_slsh',
        'payCard', 'refCard',
        'payEDahab_usd', 'payEDahab_slsh', 'refEDahab',
        'payZaad_usd', 'payZaad_slsh', 'refZaad',
        'payStoreCredit'
    ];
    fields.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    // Clear SLSH hints
    ['cashSlshHint', 'edahabSlshHint', 'zaadSlshHint'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerText = '';
    });

    const discountInput = document.getElementById('discountInput');
    if (discountInput) discountInput.value = '';

    document.querySelectorAll('.payment-method-card').forEach(c => c.classList.remove('active'));

    updatePaymentTotals();
}

/* ================================================================
   Build Payments Array for Submission
   ================================================================ */
function buildPaymentsArray() {
    const payments = [];
    const raw = getRawPaymentInputs();
    const refCard    = document.getElementById('refCard');
    const refEDahab  = document.getElementById('refEDahab');
    const refZaad    = document.getElementById('refZaad');

    if (raw.cash_usd > 0)
        payments.push({ method: 'Cash', currency: 'USD', amount: raw.cash_usd, reference: '' });
    if (raw.cash_slsh > 0)
        payments.push({ method: 'Cash', currency: 'SLSH', amount: raw.cash_slsh, reference: '' });

    if (raw.card_usd > 0)
        payments.push({ method: 'Card', currency: 'USD', amount: raw.card_usd, reference: refCard?.value || '' });

    if (raw.edahab_usd > 0)
        payments.push({ method: 'E-Dahab', currency: 'USD', amount: raw.edahab_usd, reference: refEDahab?.value || '' });
    if (raw.edahab_slsh > 0)
        payments.push({ method: 'E-Dahab', currency: 'SLSH', amount: raw.edahab_slsh, reference: refEDahab?.value || '' });

    if (raw.zaad_usd > 0)
        payments.push({ method: 'Zaad', currency: 'USD', amount: raw.zaad_usd, reference: refZaad?.value || '' });
    if (raw.zaad_slsh > 0)
        payments.push({ method: 'Zaad', currency: 'SLSH', amount: raw.zaad_slsh, reference: refZaad?.value || '' });

    if (raw.storeCredit > 0)
        payments.push({ method: 'Store Credit', currency: 'USD', amount: raw.storeCredit, reference: '' });

    return payments;
}

/* ================================================================
   Checkout Processing
   ================================================================ */
async function processCheckout() {
    if (!state.cart.length) { showToast("Cart is empty"); return; }

    const payments = buildPaymentsArray();
    const partialCheckbox = document.getElementById('allowPartialPayment');
    const allowPartial = partialCheckbox && partialCheckbox.checked && state.selectedCustomer;

    if (payments.length === 0 && !allowPartial) {
        const paymentError = document.getElementById('paymentError');
        if (paymentError) paymentError.style.display = 'block';
        return;
    }

    const discountInput = document.getElementById('discountInput');
    const payload = {
        items: state.cart.map(i => ({ product_id: i.id, quantity: i.quantity, price: i.price })),
        discount: discountInput ? (parseFloat(discountInput.value) || 0) : 0,
        payments: payments,
        customer_id: state.selectedCustomer?.id || null,
        sale_type: state.saleType || 'RETAIL',
        allow_partial_payment: allowPartial || false
    };

    try {
        logDebug('Submitting checkout:', payload);
        const res = await API.checkout(payload);

        if (res.success) {
            if (checkoutModalInstance) checkoutModalInstance.hide();

            if (res.invoice_status === 'Partial' || res.amount_due > 0) {
                showToast(`Invoice created! Amount due: $${res.amount_due.toFixed(2)}`, 'success');
            } else if (res.change && res.change > 0) {
                const rate = getExchangeRate();
                const slshChange = Math.round(res.change * rate).toLocaleString();
                showToast(`Sale complete! Change: $${res.change.toFixed(2)} (≈ ${slshChange} SLSH)`, 'success');
            } else {
                showToast('Sale completed successfully!', 'success');
            }

            window.open(`/pos/receipt/${res.sale_id}`, '_blank', 'noopener,noreferrer');

            state.cart = [];
            state.selectedCustomer = null;
            state.saleType = 'RETAIL';
            localStorage.removeItem('pos_cart');
            clearPayments();
            renderCart();

            if (typeof resetCheckoutModal === 'function') resetCheckoutModal();

        } else {
            showToast(res.message || "Checkout failed");
        }
    } catch (e) {
        console.error('[Payment] Checkout error:', e);
        showToast("Checkout Error: " + e.message);
    }
}

/* ================================================================
   Auto-initialize on DOM ready
   ================================================================ */
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => { initializeCheckoutModal(); }, 100);
});
