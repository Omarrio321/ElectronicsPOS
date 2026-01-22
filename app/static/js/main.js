// Main JavaScript file for Electronics POS System

// Utility Functions
function formatCurrency(amount) {
    const symbol = window.CURRENCY_SYMBOL || '$';
    // Format with commas and 2 decimal places
    return symbol + Number(amount).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Form Validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return true;

    const inputs = form.querySelectorAll('input[required], select[required], textarea[required]');
    let isValid = true;

    inputs.forEach(input => {
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
        }
    });

    return isValid;
}

// Auto-hide Alerts
document.addEventListener('DOMContentLoaded', function () {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.classList.add('fade');
            setTimeout(() => alert.remove(), 150);
        }, 5000);
    });
});

// Confirm Delete
function confirmDelete(message = 'Are you sure you want to delete this item?') {
    return confirm(message);
}

// Loading Spinner
function showSpinner(element) {
    element.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"></div>';
}

function hideSpinner(element, originalContent) {
    element.innerHTML = originalContent;
}

// API Helper
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
        }
    };

    const mergedOptions = { ...defaultOptions, ...options };

    try {
        const response = await fetch(url, mergedOptions);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('API request failed:', error);
        throw error;
    }
}

// Search Auto-complete
function setupSearchAutoComplete(inputId, resultsId, searchUrl) {
    const input = document.getElementById(inputId);
    const results = document.getElementById(resultsId);
    let debounceTimer;

    input.addEventListener('input', function () {
        clearTimeout(debounceTimer);
        const query = this.value.trim();

        if (query.length < 2) {
            results.innerHTML = '';
            return;
        }

        debounceTimer = setTimeout(async () => {
            try {
                const data = await apiRequest(`${searchUrl}?q=${encodeURIComponent(query)}`);
                displaySearchResults(data, results);
            } catch (error) {
                console.error('Search failed:', error);
            }
        }, 300);
    });
}

function displaySearchResults(items, container) {
    container.innerHTML = '';

    if (items.length === 0) {
        container.innerHTML = '<div class="text-muted">No results found</div>';
        return;
    }

    const list = document.createElement('div');
    list.className = 'list-group';

    items.forEach(item => {
        const listItem = document.createElement('a');
        listItem.href = item.url || '#';
        listItem.className = 'list-group-item list-group-item-action';
        listItem.innerHTML = `
            <div class="d-flex justify-content-between">
                <div>
                    <h6 class="mb-1">${item.name}</h6>
                    <small class="text-muted">${item.description || ''}</small>
                </div>
                ${item.price ? `<span class="text-primary">${formatCurrency(item.price)}</span>` : ''}
            </div>
        `;

        listItem.addEventListener('click', function (e) {
            if (item.onClick) {
                e.preventDefault();
                item.onClick(item);
            }
        });

        list.appendChild(listItem);
    });

    container.appendChild(list);
}

// Cart Management
class ShoppingCart {
    constructor() {
        this.items = [];
        this.listeners = [];
    }

    addItem(product, quantity = 1) {
        const existingItem = this.items.find(item => item.id === product.id);

        if (existingItem) {
            existingItem.quantity += quantity;
        } else {
            this.items.push({
                id: product.id,
                name: product.name,
                price: product.price,
                quantity: quantity
            });
        }

        this.notifyListeners();
    }

    removeItem(productId) {
        this.items = this.items.filter(item => item.id !== productId);
        this.notifyListeners();
    }

    updateQuantity(productId, quantity) {
        const item = this.items.find(item => item.id === productId);
        if (item) {
            item.quantity = quantity;
            this.notifyListeners();
        }
    }

    clear() {
        this.items = [];
        this.notifyListeners();
    }

    getTotal() {
        return this.items.reduce((total, item) => total + (item.price * item.quantity), 0);
    }

    getItemCount() {
        return this.items.reduce((count, item) => count + item.quantity, 0);
    }

    subscribe(listener) {
        this.listeners.push(listener);
    }

    notifyListeners() {
        this.listeners.forEach(listener => listener(this.items));
    }
}

// Initialize Cart
const cart = new ShoppingCart();

// Chart Helper
function createChart(canvasId, type, data, options = {}) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: type,
        data: data,
        options: options
    });
}

// Date Range Picker
function setupDateRangePicker(startId, endId, presetButtons) {
    const startDate = document.getElementById(startId);
    const endDate = document.getElementById(endId);

    presetButtons.forEach(button => {
        button.addEventListener('click', function () {
            const range = this.dataset.range;
            const dates = getDateRange(range);
            startDate.value = dates.start;
            endDate.value = dates.end;
        });
    });
}

function getDateRange(range) {
    const today = new Date();
    const start = new Date(today);
    const end = new Date(today);

    switch (range) {
        case 'today':
            break;
        case 'yesterday':
            start.setDate(today.getDate() - 1);
            end.setDate(today.getDate() - 1);
            break;
        case 'this_week':
            start.setDate(today.getDate() - today.getDay());
            break;
        case 'last_week':
            start.setDate(today.getDate() - today.getDay() - 7);
            end.setDate(today.getDate() - today.getDay() - 1);
            break;
        case 'this_month':
            start.setDate(1);
            break;
        case 'last_month':
            start.setMonth(today.getMonth() - 1);
            start.setDate(1);
            end.setMonth(today.getMonth() - 1);
            end.setDate(new Date(today.getFullYear(), today.getMonth(), 0).getDate());
            break;
    }

    return {
        start: start.toISOString().split('T')[0],
        end: end.toISOString().split('T')[0]
    };
}

// Export Functions
function exportToCSV(data, filename) {
    const csv = convertToCSV(data);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');

    if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
}

function convertToCSV(data) {
    if (data.length === 0) return '';

    const headers = Object.keys(data[0]);
    const csvRows = [
        headers.join(','),
        ...data.map(row => headers.map(header => `"${row[header]}"`).join(','))
    ];

    return csvRows.join('\n');
}

// Print Function
function printElement(elementId) {
    const element = document.getElementById(elementId);
    const printWindow = window.open('', '_blank');

    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Print</title>
            <style>
                body { font-family: Arial, sans-serif; }
                .no-print { display: none; }
                @media print { .no-print { display: none; } }
            </style>
        </head>
        <body>
            ${element.innerHTML}
        </body>
        </html>
    `);

    printWindow.document.close();
    printWindow.print();
    printWindow.close();
}

// Keyboard Shortcuts
document.addEventListener('keydown', function (e) {
    // Ctrl/Cmd + K for search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('input[type="search"]');
        if (searchInput) searchInput.focus();
    }

    // Escape to close modals
    if (e.key === 'Escape') {
        const modals = document.querySelectorAll('.modal.show');
        modals.forEach(modal => {
            const modalInstance = bootstrap.Modal.getInstance(modal);
            if (modalInstance) modalInstance.hide();
        });
    }
});

// Initialize Tooltips
document.addEventListener('DOMContentLoaded', function () {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// Sidebar Toggle Logic
document.addEventListener('DOMContentLoaded', function () {
    const sidebarToggle = document.getElementById('sidebarToggle');
    const body = document.body;

    // Check local storage
    if (localStorage.getItem('sidebar-collapsed') === 'true') {
        body.classList.add('sidebar-collapsed');
    }

    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function () {
            body.classList.toggle('sidebar-collapsed');
            localStorage.setItem('sidebar-collapsed', body.classList.contains('sidebar-collapsed'));
        });
    }
});