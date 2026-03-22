/**
 * =================================================================
 * POS Camera Barcode Scanner  —  scanner.js
 * Electronics POS System
 *
 * Modes:
 *   sell    → scan barcode → lookup product → add to cart → close
 *   restock → scan barcode → lookup product → show restock panel
 *             → enter qty  → POST /api/restock → confirm → close
 *
 * Invoice detection:
 *   barcode starts with "INV-" → close scanner → redirect to
 *   /sales/?search=<invoice_no>  (existing sales.index does exact match)
 *
 * Requires: html5-qrcode.min.js loaded BEFORE this file.
 * Supported formats: Code128, Code39, EAN-13, EAN-8, UPC-A, UPC-E,
 *                    ITF, QR Code.
 * Browsers: Chrome (Android, HTTP OK), Safari iOS 14.3+ (HTTPS needed)
 * =================================================================
 */

const PosScanner = (() => {
    /* ----------------------------------------------------------------
       Private state
    ---------------------------------------------------------------- */
    let _scanner    = null;     // Html5Qrcode instance
    let _isScanning = false;
    let _lastScanMs = 0;
    let _mode       = 'sell';   // 'sell' | 'restock'
    let _pending    = null;     // product object waiting in restock panel

    const COOLDOWN_MS = 2500;   // ignore duplicate detections within this window

    /* ----------------------------------------------------------------
       DOM helpers
    ---------------------------------------------------------------- */
    function _el(id)  { return document.getElementById(id); }

    function _csrf() {
        const m = document.querySelector('meta[name="csrf-token"]');
        return m ? m.getAttribute('content') : '';
    }

    function _setStatus(msg, type /* 'info'|'success'|'warn'|'error' */) {
        const el = _el('scannerStatus');
        if (!el) return;
        el.className  = 'scanner-status scanner-status-' + (type || 'info');
        el.textContent = msg;
    }

    function _setFrame(state /* ''|'success'|'error' */) {
        const frame = _el('scannerFrame');
        if (!frame) return;
        frame.className = 'scanner-frame' + (state ? ' scanner-frame-' + state : '');
    }

    /* ----------------------------------------------------------------
       Backend requests
    ---------------------------------------------------------------- */
    async function _lookupBarcode(barcode) {
        try {
            const res = await fetch('/api/scan-barcode', {
                method:  'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken':  _csrf(),
                    'Accept':       'application/json'
                },
                body: JSON.stringify({ barcode })
            });
            if (!res.ok) throw new Error('HTTP ' + res.status);
            return await res.json();
        } catch (e) {
            console.error('[Scanner] Lookup error:', e);
            return { status: 'error', message: e.message };
        }
    }

    async function _postRestock(barcode, quantity) {
        try {
            const res = await fetch('/api/restock', {
                method:  'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken':  _csrf(),
                    'Accept':       'application/json'
                },
                body: JSON.stringify({ barcode, quantity })
            });
            if (!res.ok) throw new Error('HTTP ' + res.status);
            return await res.json();
        } catch (e) {
            console.error('[Scanner] Restock error:', e);
            return { status: 'error', message: e.message };
        }
    }

    /* ----------------------------------------------------------------
       Cart integration
       Temporarily injects the scanned product into state.products
       (if not already present) so the existing addToCart() can find it.
    ---------------------------------------------------------------- */
    function _addToCartByProduct(product) {
        if (typeof state === 'undefined' || typeof addToCart !== 'function') {
            console.warn('[Scanner] POS state/addToCart not available');
            return;
        }
        if (!state.products.find(p => p.id === product.id)) {
            state.products.push({
                id:                product.id,
                name:              product.name,
                price:             product.price,
                barcode:           product.barcode,
                sku:               product.sku,
                stock:             product.stock,
                wholesale_price:   product.wholesale_price,
                allow_wholesale:   product.allow_wholesale,
                min_wholesale_qty: product.min_wholesale_qty,
                image_url:         product.image_url
            });
        }
        addToCart(product.id);
    }

    /* ----------------------------------------------------------------
       Restock panel helpers
    ---------------------------------------------------------------- */
    function _showRestockPanel(product) {
        _pending = product;

        // Populate panel fields
        const nameEl  = _el('restockProductName');
        const stockEl = _el('restockCurrentStock');
        const qtyEl   = _el('restockQtyInput');
        if (nameEl)  nameEl.textContent  = product.name;
        if (stockEl) stockEl.textContent = product.stock;
        if (qtyEl)   { qtyEl.value = '1'; qtyEl.focus(); }

        // Hide camera area, show panel
        const wrap  = document.querySelector('.scanner-viewport-wrap');
        const panel = _el('restockPanel');
        if (wrap)  wrap.style.display  = 'none';
        if (panel) panel.style.display = 'flex';

        // Update status
        _setStatus('Enter quantity to add', 'info');
    }

    function _hideRestockPanel() {
        _pending = null;
        const wrap  = document.querySelector('.scanner-viewport-wrap');
        const panel = _el('restockPanel');
        if (panel) panel.style.display = 'none';
        if (wrap)  wrap.style.display  = 'block';
    }

    /* ----------------------------------------------------------------
       Scan detection callback
    ---------------------------------------------------------------- */
    async function _onDetected(decodedText) {
        const now = Date.now();
        if (now - _lastScanMs < COOLDOWN_MS) return;  // duplicate guard
        _lastScanMs = now;

        console.log('[Scanner] Detected:', decodedText);

        /* ── 1. Invoice barcode ─────────────────────────────────── */
        if (decodedText.startsWith('INV-')) {
            _setFrame('success');
            _setStatus('Invoice found — redirecting…', 'success');
            await _stopCamera();
            setTimeout(() => {
                close();
                window.location = '/sales/?search=' + encodeURIComponent(decodedText);
            }, 900);
            return;
        }

        /* ── 2. Product lookup ──────────────────────────────────── */
        _setStatus('Detected — looking up product…', 'info');
        const data = await _lookupBarcode(decodedText);

        if (data.status === 'success') {
            _setFrame('success');

            if (_mode === 'sell') {
                /* Sell mode: add to cart and close */
                _setStatus('✓ ' + data.product.name, 'success');
                _addToCartByProduct(data.product);
                setTimeout(() => close(), 1400);

            } else {
                /* Restock mode: pause camera, show restock panel */
                await _stopCamera();
                _setStatus('Product found — enter restock quantity', 'success');
                setTimeout(() => _showRestockPanel(data.product), 300);
            }

        } else if (data.status === 'not_found') {
            _setFrame('error');
            _setStatus('Product not found: ' + decodedText, 'warn');
            setTimeout(() => {
                if (_isScanning) {
                    _setFrame('');
                    _setStatus('Point camera at a barcode', 'info');
                    _lastScanMs = 0;
                }
            }, 2000);

        } else {
            _setFrame('error');
            _setStatus('Error: ' + (data.message || 'Unknown'), 'error');
            setTimeout(() => {
                if (_isScanning) {
                    _setFrame('');
                    _setStatus('Point camera at a barcode', 'info');
                }
            }, 2500);
        }
    }

    function _onScanFailure() { /* called every frame with no code — intentionally silent */ }

    /* ----------------------------------------------------------------
       Camera lifecycle
    ---------------------------------------------------------------- */
    async function _startCamera() {
        if (typeof Html5Qrcode === 'undefined') {
            _setStatus('Scanner library not loaded. Refresh the page and try again.', 'error');
            return;
        }

        try {
            _scanner = new Html5Qrcode('scannerViewport', { verbose: false });

            const config = {
                fps: 10,
                qrbox: (vw, vh) => ({
                    width:  Math.min(Math.round(vw * 0.82), 320),
                    height: Math.min(Math.round(vh * 0.38), 160)
                }),
                experimentalFeatures: { useBarCodeDetectorIfSupported: true },
                formatsToSupport: [
                    Html5QrcodeSupportedFormats.CODE_128,
                    Html5QrcodeSupportedFormats.CODE_39,
                    Html5QrcodeSupportedFormats.EAN_13,
                    Html5QrcodeSupportedFormats.EAN_8,
                    Html5QrcodeSupportedFormats.UPC_A,
                    Html5QrcodeSupportedFormats.UPC_E,
                    Html5QrcodeSupportedFormats.ITF,
                    Html5QrcodeSupportedFormats.QR_CODE
                ]
            };

            await _scanner.start(
                { facingMode: 'environment' },
                config,
                _onDetected,
                _onScanFailure
            );

            _isScanning = true;
            _lastScanMs = 0;
            _setStatus('Point camera at a barcode', 'info');

        } catch (err) {
            console.error('[Scanner] Camera start error:', err);
            _isScanning = false;
            const msg = err.message || '';
            if (/permission|denied/i.test(msg)) {
                _setStatus('Camera permission denied. Allow access in browser settings and try again.', 'error');
            } else if (/not found|no camera/i.test(msg)) {
                _setStatus('No camera found on this device.', 'error');
            } else if (/https|insecure|secure/i.test(msg)) {
                _setStatus('Camera requires HTTPS. Access this page over a secure connection.', 'error');
            } else {
                _setStatus('Camera error: ' + (msg || 'Unknown error'), 'error');
            }
        }
    }

    async function _stopCamera() {
        _isScanning = false;
        if (_scanner) {
            try { await _scanner.stop(); }  catch (e) { /* already stopped */ }
            try { _scanner.clear(); }        catch (e) { /* ignore */ }
            _scanner = null;
        }
        const vp = _el('scannerViewport');
        if (vp) vp.innerHTML = '';
    }

    /* ----------------------------------------------------------------
       Public API
    ---------------------------------------------------------------- */

    /** Open the scanner overlay and start the camera. */
    async function open() {
        const overlay = _el('scannerOverlay');
        if (!overlay) { console.error('[Scanner] #scannerOverlay not found'); return; }

        // Reset visual state
        _hideRestockPanel();
        _setFrame('');
        _setStatus('Starting camera…', 'info');

        // Ensure camera viewport is visible
        const wrap = document.querySelector('.scanner-viewport-wrap');
        if (wrap) wrap.style.display = 'block';

        // Sync mode toggle buttons
        _syncModeButtons();

        overlay.style.display    = 'flex';
        document.body.style.overflow = 'hidden';

        await _startCamera();
    }

    /** Close the scanner overlay and release the camera. */
    async function close() {
        const overlay = _el('scannerOverlay');
        if (overlay) overlay.style.display = 'none';
        document.body.style.overflow = '';

        _hideRestockPanel();
        await _stopCamera();
    }

    /**
     * Switch between 'sell' and 'restock' modes.
     * Can be called from onclick on the toggle buttons.
     */
    function setMode(mode) {
        _mode = mode;
        _syncModeButtons();
        _setFrame('');
        _setStatus('Point camera at a barcode', 'info');
        console.log('[Scanner] Mode set to:', mode);
    }

    function _syncModeButtons() {
        const sellBtn    = _el('scanModeSell');
        const restockBtn = _el('scanModeRestock');
        if (sellBtn)    sellBtn.classList.toggle('active',    _mode === 'sell');
        if (restockBtn) restockBtn.classList.toggle('active', _mode === 'restock');
    }

    /** Increment or decrement the restock quantity input (called by ± buttons). */
    function adjustRestockQty(delta) {
        const input = _el('restockQtyInput');
        if (!input) return;
        const current = parseInt(input.value, 10) || 1;
        const next    = Math.max(1, Math.min(9999, current + delta));
        input.value   = next;
    }

    /** Submit the restock form — called by "Add Stock" button. */
    async function submitRestock() {
        if (!_pending) return;

        const input    = _el('restockQtyInput');
        const quantity = parseInt((input && input.value) || '1', 10);

        if (!quantity || quantity <= 0) {
            _setStatus('Please enter a quantity greater than 0', 'warn');
            return;
        }

        const submitBtn = document.querySelector('.restock-submit-btn');
        if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Saving…'; }

        const data = await _postRestock(_pending.barcode, quantity);

        if (submitBtn) {
            submitBtn.disabled    = false;
            submitBtn.innerHTML   = '<i class="fas fa-plus-circle"></i> Add Stock';
        }

        if (data.status === 'success') {
            _setFrame('success');
            _setStatus(
                '✓ ' + data.product_name + ' — new stock: ' + data.new_stock,
                'success'
            );
            // Show confirmation briefly then close
            setTimeout(() => close(), 1800);

        } else if (data.status === 'not_found') {
            _setStatus('Product not found — cannot restock', 'error');
        } else {
            _setStatus('Error: ' + (data.message || 'Restock failed'), 'error');
        }
    }

    /**
     * Cancel the restock panel and restart the camera in restock mode
     * so the operator can scan a different item.
     */
    async function cancelRestock() {
        _hideRestockPanel();
        _setFrame('');
        _setStatus('Starting camera…', 'info');
        await _startCamera();
    }

    /* expose public surface */
    return { open, close, setMode, adjustRestockQty, submitRestock, cancelRestock };
})();
