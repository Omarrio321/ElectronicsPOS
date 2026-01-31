/**
 * =================================================================
 * POS Terminal - Payment & Modal Logic
 * Electronics POS System
 * 
 * PRODUCTION FIX: Proper Bootstrap Modal lifecycle management
 * Root cause: Event handlers and modal instance corruption
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
const DEBUG = true;
function logDebug(...args) {
    if (DEBUG) console.log('[Payment]', ...args);
}

function debugModalState() {
    const backdrops = document.querySelectorAll('.modal-backdrop');
    const modalEl = document.getElementById('checkoutModal');
    const bodyHasModalOpen = document.body.classList.contains('modal-open');

    logDebug('=== Modal State Debug ===');
    logDebug('Backdrop count:', backdrops.length);
    logDebug('Modal element exists:', !!modalEl);
    if (modalEl) {
        logDebug('Modal classList:', modalEl.className);
        logDebug('Modal display:', getComputedStyle(modalEl).display);
        logDebug('Modal z-index:', getComputedStyle(modalEl).zIndex);
    }
    logDebug('Body has modal-open:', bodyHasModalOpen);
    logDebug('Body overflow:', document.body.style.overflow);
    logDebug('========================');
}

/* ================================================================
   Initialize Modal - Called ONCE on page load
   ================================================================ */
function initializeCheckoutModal() {
    if (isModalInitialized) {
        logDebug('Modal already initialized, skipping');
        return;
    }

    const modalElement = document.getElementById('checkoutModal');
    if (!modalElement) {
        console.error('[Payment] Cannot initialize - modal element not found');
        return;
    }

    // DEFENSIVE GUARD: Ensure modal is direct child of body
    // This prevents stacking context issues
    if (modalElement.parentElement !== document.body) {
        logDebug('Moving modal to body (was inside stacking context)');
        document.body.appendChild(modalElement);
    }

    logDebug('Initializing modal with event listeners...');

    // Use getOrCreateInstance - Bootstrap 5 best practice
    checkoutModalInstance = bootstrap.Modal.getOrCreateInstance(modalElement, {
        backdrop: true,
        keyboard: true,
        focus: true
    });

    // Bind events ONCE using the modal element
    modalElement.addEventListener('hidden.bs.modal', onModalHidden);
    modalElement.addEventListener('shown.bs.modal', onModalShown);
    modalElement.addEventListener('hide.bs.modal', onModalHide);

    isModalInitialized = true;
    logDebug('Modal initialized successfully');
}

/* ================================================================
   Modal Event Handlers
   ================================================================ */
function onModalShown(event) {
    logDebug('EVENT: shown.bs.modal fired');
    debugModalState();
}

function onModalHide(event) {
    logDebug('EVENT: hide.bs.modal fired (modal starting to close)');
}

function onModalHidden(event) {
    logDebug('EVENT: hidden.bs.modal fired (modal fully closed)');

    // CRITICAL: Force cleanup after modal is fully hidden
    forceCleanupModalState();

    debugModalState();
}

function forceCleanupModalState() {
    logDebug('Executing forced cleanup...');

    // Remove ALL backdrop elements (should be 0 but clean up any orphans)
    const backdrops = document.querySelectorAll('.modal-backdrop');
    if (backdrops.length > 0) {
        logDebug('WARNING: Found', backdrops.length, 'orphan backdrop(s), removing...');
        backdrops.forEach(el => el.remove());
    }

    // Restore body state
    document.body.classList.remove('modal-open');
    document.body.style.removeProperty('overflow');
    document.body.style.removeProperty('padding-right');

    // Ensure modal element is in correct state
    const modalEl = document.getElementById('checkoutModal');
    if (modalEl) {
        modalEl.classList.remove('show');
        modalEl.style.display = 'none';
        modalEl.setAttribute('aria-hidden', 'true');
        modalEl.removeAttribute('aria-modal');
        modalEl.removeAttribute('role');
    }

    logDebug('Cleanup complete');
}

/* ================================================================
   Open Checkout Modal
   ================================================================ */
function openCheckoutModal() {
    logDebug('openCheckoutModal() called, cart items:', state.cart.length);
    debugModalState();

    if (state.cart.length === 0) {
        showToast("Please add items to cart first");
        return;
    }

    try {
        const modalElement = document.getElementById('checkoutModal');
        if (!modalElement) {
            console.error('[Payment] Modal element not found');
            showToast("Error: Modal not found");
            return;
        }

        // Initialize if not already done
        if (!isModalInitialized) {
            initializeCheckoutModal();
        }

        // Pre-cleanup: Remove any stale state BEFORE opening
        const existingBackdrops = document.querySelectorAll('.modal-backdrop');
        if (existingBackdrops.length > 0) {
            logDebug('Pre-open cleanup: removing', existingBackdrops.length, 'stale backdrop(s)');
            existingBackdrops.forEach(el => el.remove());
            document.body.classList.remove('modal-open');
        }

        // Get fresh instance reference
        checkoutModalInstance = bootstrap.Modal.getOrCreateInstance(modalElement);

        // Populate modal with cart data
        populateModalCart();

        // Reset payment fields
        clearPayments();

        // Calculate and display totals
        updateModalTotals();
        updatePaymentTotals();

        // Show modal using Bootstrap API
        logDebug('Calling checkoutModalInstance.show()');
        checkoutModalInstance.show();

    } catch (error) {
        console.error('[Payment] Error opening modal:', error);
        showToast("Error opening checkout: " + error.message);
        forceCleanupModalState();
    }
}

/* ================================================================
   Close Checkout Modal (explicit close function)
   ================================================================ */
function closeCheckoutModal() {
    logDebug('closeCheckoutModal() called');

    if (checkoutModalInstance) {
        checkoutModalInstance.hide();
    } else {
        // Fallback: force cleanup if no instance
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
    const tax = sub * (state.taxRate || 0);
    const total = sub + tax;

    const modalSubtotal = document.getElementById('modalSubtotal');
    if (modalSubtotal) modalSubtotal.innerText = `$${sub.toFixed(2)}`;

    const modalTax = document.getElementById('modalTax');
    if (modalTax) modalTax.innerText = `$${tax.toFixed(2)}`;

    const modalDiscountDisplay = document.getElementById('modalDiscountDisplay');
    if (modalDiscountDisplay) modalDiscountDisplay.innerText = `-$0.00`;

    const modalGrandTotal = document.getElementById('modalGrandTotal');
    if (modalGrandTotal) modalGrandTotal.innerText = `$${total.toFixed(2)}`;
}

/* ================================================================
   Payment Calculations
   ================================================================ */
function getGrandTotal() {
    const sub = state.cart.reduce((a, b) => a + (b.price * b.quantity), 0);
    const discountInput = document.getElementById('discountInput');
    const disc = discountInput ? (parseFloat(discountInput.value) || 0) : 0;
    const tax = Math.max(0, sub - disc) * (state.taxRate || 0);
    return sub - disc + tax;
}

function getPaymentAmounts() {
    const payCash = document.getElementById('payCash');
    const payCard = document.getElementById('payCard');
    const payEDahab = document.getElementById('payEDahab');
    const payZaad = document.getElementById('payZaad');
    return {
        cash: payCash ? (parseFloat(payCash.value) || 0) : 0,
        card: payCard ? (parseFloat(payCard.value) || 0) : 0,
        edahab: payEDahab ? (parseFloat(payEDahab.value) || 0) : 0,
        zaad: payZaad ? (parseFloat(payZaad.value) || 0) : 0,
        storeCredit: (() => {
            const el = document.getElementById('payStoreCredit');
            return el ? (parseFloat(el.value) || 0) : 0;
        })()
    };
}

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

/* ================================================================
   UI Helpers
   ================================================================ */
function focusPaymentInput(inputId) {
    const el = document.getElementById(inputId);
    if (el) {
        el.focus();
        // Highlight parent card
        const card = el.closest('.payment-method-card');
        if (card) showActiveCard(card);
    }
}

function showActiveCard(card) {
    // Optional: could implement radio-like behavior if we wanted only one active
    // For now, just focus effect handled by CSS focus-within or manual class
}

function useMaxCredit(e) {
    if (e) e.preventDefault();

    // Get current totals
    const grandTotal = getGrandTotal();
    const amounts = getPaymentAmounts();
    const otherPayments = amounts.cash + amounts.card + amounts.edahab + amounts.zaad;
    const remainingToPay = Math.max(0, grandTotal - otherPayments);

    // Get available
    const customer = state.selectedCustomer;
    if (!customer || !customer.credit_balance) return;

    const available = parseFloat(customer.credit_balance);
    const useAmount = Math.min(remainingToPay, available);

    const input = document.getElementById('payStoreCredit');
    if (input) {
        input.value = useAmount.toFixed(2);
        updatePaymentTotals();
    }
}

function updatePaymentTotals() {
    try {
        const remainingRow = document.getElementById('remainingRow');
        const changeRow = document.getElementById('changeRow');
        const completeBtn = document.getElementById('completeBtn');
        const amountDueRow = document.getElementById('amountDueRow');
        const partialPaymentInfo = document.getElementById('partialPaymentInfo');
        const totalPaidDisplay = document.getElementById('totalPaidDisplay');
        const digitalOverpayError = document.getElementById('digitalOverpayError');
        const paymentError = document.getElementById('paymentError');

        if (!remainingRow || !changeRow || !completeBtn) return;

        const grandTotal = getGrandTotal();
        const amounts = getPaymentAmounts();
        // Credit counts towards total paid
        const totalPaid = amounts.cash + amounts.card + amounts.edahab + amounts.zaad + amounts.storeCredit;
        const digitalPaid = amounts.card + amounts.edahab + amounts.zaad + amounts.storeCredit;

        // Ensure floating point precision stability
        const remaining = Math.max(0, parseFloat((grandTotal - totalPaid).toFixed(2)));
        const change = Math.max(0, parseFloat((totalPaid - grandTotal).toFixed(2)));

        // Update Total Paid Display
        if (totalPaidDisplay) totalPaidDisplay.innerText = `$${totalPaid.toFixed(2)}`;

        // Check permissions
        const partialCheckbox = document.getElementById('allowPartialPayment');
        const allowPartial = partialCheckbox && partialCheckbox.checked && state.selectedCustomer;
        const isDigitalOverpay = digitalPaid > grandTotal + 0.005;

        // Reset all error/info states first
        if (paymentError) paymentError.style.display = 'none';
        if (digitalOverpayError) digitalOverpayError.style.display = 'none';
        if (partialPaymentInfo) partialPaymentInfo.style.display = 'none';

        // Hide amount due row by default (it's d-flex)
        toggleFlexRow(amountDueRow, false);

        // --- STORE CREDIT UI LOGIC ---
        const storeCreditCard = document.getElementById('storeCreditCard');
        const payStoreCredit = document.getElementById('payStoreCredit');
        const storeCreditAvailable = document.getElementById('storeCreditAvailable');

        if (storeCreditCard && payStoreCredit) {
            const customer = state.selectedCustomer;

            if (customer && customer.credit_balance > 0) {
                storeCreditCard.style.display = 'flex';
                if (storeCreditAvailable) {
                    storeCreditAvailable.innerText = `$${parseFloat(customer.credit_balance).toFixed(2)}`;
                }

                // Validate limits
                const entered = parseFloat(payStoreCredit.value) || 0;
                if (entered > customer.credit_balance) {
                    payStoreCredit.classList.add('is-invalid');
                } else {
                    payStoreCredit.classList.remove('is-invalid');
                }
            } else {
                storeCreditCard.style.display = 'none';
                payStoreCredit.value = '';
            }
        }

        // --- HIGHLIGHT ACTIVE CARDS ---
        ['payCash', 'payCard', 'payEDahab', 'payZaad'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                const card = el.closest('.payment-method-card');
                if (card) {
                    if (el.value && parseFloat(el.value) > 0) {
                        card.classList.add('active');
                    } else {
                        card.classList.remove('active');
                    }
                }
            }
        });

        // Logic branching
        if (isDigitalOverpay) {
            toggleFlexRow(remainingRow, false);
            toggleFlexRow(changeRow, false);
            completeBtn.disabled = true;
            if (digitalOverpayError) digitalOverpayError.style.display = 'block';
        } else if (remaining > 0.005) {
            // Still owe money
            if (allowPartial) {
                // Partial payment allowed
                toggleFlexRow(remainingRow, false);
                toggleFlexRow(changeRow, false);

                toggleFlexRow(amountDueRow, true);
                const amountDueDisplay = document.getElementById('amountDueDisplay');
                if (amountDueDisplay) amountDueDisplay.innerText = `$${remaining.toFixed(2)}`;

                if (partialPaymentInfo) partialPaymentInfo.style.display = 'block';
                completeBtn.disabled = false;
            } else {
                // Must pay in full
                toggleFlexRow(remainingRow, true);
                toggleFlexRow(changeRow, false);

                const remainingDisplay = document.getElementById('remainingDisplay');
                if (remainingDisplay) remainingDisplay.innerText = `$${remaining.toFixed(2)}`;

                completeBtn.disabled = true;

                if (paymentError && totalPaid <= 0) {
                    paymentError.style.display = 'block';
                }
            }
        } else {
            // Paid in full or overpaid
            toggleFlexRow(remainingRow, false);
            toggleFlexRow(changeRow, true);

            const changeDisplay = document.getElementById('changeDisplay');
            if (changeDisplay) changeDisplay.innerText = `$${change.toFixed(2)}`;

            completeBtn.disabled = false;
        }

    } catch (e) {
        console.error("Error in updatePaymentTotals", e);
    }
}

function clearPayments() {
    const fields = ['payCash', 'payCard', 'payEDahab', 'payZaad', 'payStoreCredit', 'refCard', 'refEDahab', 'refZaad'];
    fields.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = '';
    });

    const discountInput = document.getElementById('discountInput');
    if (discountInput) discountInput.value = '';

    // Clear active classes
    document.querySelectorAll('.payment-method-card').forEach(c => c.classList.remove('active'));

    updatePaymentTotals();
}

function buildPaymentsArray() {
    const payments = [];
    const amounts = getPaymentAmounts();

    if (amounts.cash > 0) {
        payments.push({ method: 'Cash', amount: amounts.cash, reference: '' });
    }
    if (amounts.card > 0) {
        const refCard = document.getElementById('refCard');
        payments.push({ method: 'Card', amount: amounts.card, reference: refCard?.value || '' });
    }
    if (amounts.edahab > 0) {
        const refEDahab = document.getElementById('refEDahab');
        payments.push({ method: 'E-Dahab', amount: amounts.edahab, reference: refEDahab?.value || '' });
    }
    if (amounts.zaad > 0) {
        const refZaad = document.getElementById('refZaad');
        payments.push({ method: 'Zaad', amount: amounts.zaad, reference: refZaad?.value || '' });
    }
    if (amounts.storeCredit > 0) {
        payments.push({ method: 'Store Credit', amount: amounts.storeCredit, reference: '' });
    }

    return payments;
}

/* ================================================================
   Checkout Processing
   ================================================================ */
async function processCheckout() {
    logDebug('processCheckout() called');

    if (!state.cart.length) {
        showToast("Cart is empty");
        return;
    }

    const payments = buildPaymentsArray();
    const partialCheckbox = document.getElementById('allowPartialPayment');
    const allowPartial = partialCheckbox && partialCheckbox.checked && state.selectedCustomer;

    if (payments.length === 0 && !allowPartial) {
        const paymentError = document.getElementById('paymentError');
        if (paymentError) paymentError.style.display = 'block';
        logDebug('No payment entered');
        return;
    }

    const discountInput = document.getElementById('discountInput');
    const payload = {
        items: state.cart.map(i => ({ product_id: i.id, quantity: i.quantity, price: i.price })),
        discount: discountInput ? (parseFloat(discountInput.value) || 0) : 0,
        payments: payments,
        // New fields for customer/wholesale/partial
        customer_id: state.selectedCustomer?.id || null,
        sale_type: state.saleType || 'RETAIL',
        allow_partial_payment: allowPartial || false
    };

    try {
        logDebug('Submitting checkout:', payload);
        const res = await API.checkout(payload);

        if (res.success) {
            logDebug('Checkout successful, sale_id:', res.sale_id);

            // Close the modal using proper API
            if (checkoutModalInstance) {
                checkoutModalInstance.hide();
            }

            // Show success message
            if (res.invoice_status === 'PARTIAL' || res.amount_due > 0) {
                showToast(`Invoice created! Amount due: $${res.amount_due.toFixed(2)}`, 'success');
            } else if (res.change && res.change > 0) {
                showToast(`Sale completed! Change: $${res.change.toFixed(2)}`, 'success');
            } else {
                showToast('Sale completed successfully!', 'success');
            }

            // Open receipt in new tab
            window.open(`/pos/receipt/${res.sale_id}`, '_blank', 'noopener,noreferrer');

            // Clear cart and reset state
            state.cart = [];
            state.selectedCustomer = null;
            state.saleType = 'RETAIL';
            localStorage.removeItem('pos_cart');
            clearPayments();
            renderCart();

            // Reset customer search
            if (typeof resetCheckoutModal === 'function') {
                resetCheckoutModal();
            }

            logDebug('Cart cleared, ready for next sale');
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
    // Initialize modal after a short delay to ensure DOM is fully rendered
    setTimeout(() => {
        initializeCheckoutModal();
    }, 100);
});
