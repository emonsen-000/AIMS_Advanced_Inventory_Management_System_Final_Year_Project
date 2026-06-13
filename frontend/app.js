const API_BASE_URL = window.location.origin.includes('onrender.com')
    ? 'https://YOUR-RENDER-APP.onrender.com/api'
    : 'http://127.0.0.1:5000/api';

let products = [];
let suppliers = [];
let predictions = [];
let supplierAnalytics = [];
let roles = [];
let users = [];
let currentUser = null;

const pageTitles = {
    'dashboard-section': 'Advanced Inventory Management System',
    'products-section': 'Product Inventory',
    'suppliers-section': 'Supplier Management',
    'movements-section': 'Stock Movement Control',
    'analytics-section': 'Stock Prediction and Supplier Analytics',
    'users-section': 'User Access Management'
};

const takaFormatter = new Intl.NumberFormat('en-BD', {
    style: 'currency',
    currency: 'BDT',
    maximumFractionDigits: 0
});

function qs(selector) {
    return document.querySelector(selector);
}

function qsa(selector) {
    return [...document.querySelectorAll(selector)];
}

async function apiRequest(path, options = {}) {
    const response = await fetch(`${API_BASE_URL}${path}`, {
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        ...options
    });

    const payload = await response.json().catch(() => ({
        ok: false,
        message: 'Invalid server response'
    }));

    if (!response.ok || !payload.ok) {
        throw new Error(payload.message || 'Request failed');
    }

    return payload.data;
}

function showToast(message, isError = false) {
    const toast = qs('#toast');

    if (!toast) {
        alert(message);
        return;
    }

    toast.textContent = message;
    toast.classList.toggle('error', isError);
    toast.classList.remove('hidden');

    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

function tableEmptyMessage(colspan, message) {
    return `<tr><td colspan="${colspan}" class="empty-state">${message}</td></tr>`;
}

function statusBadge(status) {
    if (status === 'Reorder Now' || status === 'Risky') {
        return `<span class="badge danger">${status}</span>`;
    }

    if (status === 'Watch Closely' || status === 'Average') {
        return `<span class="badge warning">${status}</span>`;
    }

    return `<span class="badge success">${status}</span>`;
}

function setConnectionStatus(text, offline = false) {
    const badge = qs('#connection-status');

    if (!badge) return;

    badge.textContent = text;
    badge.classList.toggle('offline', offline);
}

function hasRole(...allowedRoles) {
    return currentUser && allowedRoles.includes(currentUser.role);
}

function updateRoleBasedUI() {
    const isAdmin = hasRole('Admin');
    const canEditMasterData = hasRole('Admin', 'Manager');

    qsa('.admin-only').forEach(element => element.classList.toggle('hidden', !isAdmin));
    qsa('.master-data-form').forEach(element => element.classList.toggle('hidden', !canEditMasterData));

    const userChip = qs('#current-user-chip');
    if (userChip && currentUser) {
        userChip.textContent = `${currentUser.username} (${currentUser.role})`;
    }
}

async function checkAuth() {
    try {
        const data = await apiRequest('/auth/me');
        if (data.logged_in) {
            currentUser = data.user;
            qs('#login-screen').classList.add('hidden');
            qs('#app-layout').classList.remove('hidden');
            updateRoleBasedUI();
            await refreshAllData();
        } else {
            qs('#login-screen').classList.remove('hidden');
            qs('#app-layout').classList.add('hidden');
        }
    } catch (error) {
        qs('#login-screen').classList.remove('hidden');
        qs('#app-layout').classList.add('hidden');
    }
}

async function loginUser(event) {
    event.preventDefault();
    const message = qs('#login-message');
    if (message) message.textContent = '';

    try {
        const data = await apiRequest('/auth/login', {
            method: 'POST',
            body: JSON.stringify({
                username: qs('#login-username').value.trim(),
                password: qs('#login-password').value
            })
        });
        currentUser = data;
        qs('#login-form').reset();
        qs('#login-screen').classList.add('hidden');
        qs('#app-layout').classList.remove('hidden');
        updateRoleBasedUI();
        showToast('Login successful');
        await refreshAllData();
    } catch (error) {
        if (message) message.textContent = error.message;
        showToast(error.message, true);
    }
}

async function logoutUser() {
    await apiRequest('/auth/logout', { method: 'POST' });
    currentUser = null;
    qs('#app-layout').classList.add('hidden');
    qs('#login-screen').classList.remove('hidden');
    showToast('Logged out');
}

async function checkConnection() {
    try {
        const data = await apiRequest('/health');

        if (data.database === 'connected') {
            setConnectionStatus('Database Connected');
        } else {
            setConnectionStatus('Backend Online');
        }
    } catch (error) {
        setConnectionStatus('Connection Failed', true);
        showToast(error.message, true);
    }
}

async function loadDashboard() {
    const data = await apiRequest('/dashboard');

    qs('#total-products').textContent = data.total_products;
    qs('#total-suppliers').textContent = data.total_suppliers;
    qs('#low-stock-items').textContent = data.low_stock_items;
    qs('#inventory-value').textContent = takaFormatter.format(data.inventory_value || 0);

    const rows = data.low_stock_products.map(item => `
        <tr>
            <td>${item.sku}</td>
            <td>${item.name}</td>
            <td>${item.current_stock}</td>
            <td>${item.reorder_level}</td>
            <td>${item.supplier_name || 'No supplier'}</td>
        </tr>
    `).join('');

    qs('#low-stock-table').innerHTML = rows || tableEmptyMessage(5, 'No low stock items right now.');
}

async function loadProducts() {
    products = await apiRequest('/products');

    renderProductOptions();
    renderProductsTable();
    renderStockBarChart();
}

function renderProductsTable() {
    const searchBox = qs('#product-search');
    const search = searchBox ? searchBox.value.toLowerCase().trim() : '';

    const filtered = products.filter(product => {
        const text = `${product.sku} ${product.name} ${product.category} ${product.supplier_name || ''}`.toLowerCase();
        return text.includes(search);
    });

    const rows = filtered.map(product => `
        <tr>
            <td>${product.sku}</td>
            <td>${product.name}</td>
            <td>${product.category}</td>
            <td>${product.current_stock}</td>
            <td>${product.reorder_level}</td>
            <td>${takaFormatter.format(product.unit_price || 0)}</td>
            <td>${product.supplier_name || 'No supplier'}</td>
            <td>
                ${hasRole('Admin', 'Manager') ? `<button class="action-btn edit-btn" onclick="editProduct(${product.id})">Edit</button>` : ''}
                ${hasRole('Admin') ? `<button class="action-btn delete-btn" onclick="deleteProduct(${product.id})">Delete</button>` : ''}
                ${!hasRole('Admin', 'Manager') ? '<span class="muted-text">View only</span>' : ''}
            </td>
        </tr>
    `).join('');

    qs('#products-table').innerHTML = rows || tableEmptyMessage(8, 'No products found.');
}

function renderStockBarChart() {
    const chartContainer = document.getElementById('stockBarChart');

    if (!chartContainer) return;

    if (!products || products.length === 0) {
        chartContainer.innerHTML = `<div class="no-chart-data">No product data available.</div>`;
        return;
    }

    const chartProducts = products
        .map(product => {
            return {
                name: product.name || product.product_name || 'Unnamed Product',
                stock: Number(product.current_stock || product.stock_quantity || product.stock || 0)
            };
        })
        .sort((a, b) => b.stock - a.stock)
        .slice(0, 8);

    const maxStock = Math.max(...chartProducts.map(product => product.stock), 1);

    chartContainer.innerHTML = chartProducts.map(product => {
        const widthPercent = (product.stock / maxStock) * 100;

        return `
            <div class="stock-bar-row">
                <div class="stock-bar-header">
                    <span class="stock-bar-label">${product.name}</span>
                    <span class="stock-bar-value">${product.stock}</span>
                </div>

                <div class="stock-bar-track">
                    <div class="stock-bar-fill" style="width: ${widthPercent}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

function renderProductOptions() {
    const supplierOptions = ['<option value="">No supplier</option>']
        .concat(suppliers.map(supplier => `<option value="${supplier.id}">${supplier.name}</option>`))
        .join('');

    const productSupplierSelect = qs('#product-supplier');
    if (productSupplierSelect) {
        productSupplierSelect.innerHTML = supplierOptions;
    }

    const productOptions = products
        .map(product => `<option value="${product.id}">${product.sku} - ${product.name}</option>`)
        .join('');

    const movementProductSelect = qs('#movement-product');
    if (movementProductSelect) {
        movementProductSelect.innerHTML = productOptions || '<option value="">No products available</option>';
    }
}

function editProduct(id) {
    const product = products.find(item => item.id === id);

    if (!product) return;

    qs('#product-form-title').textContent = 'Edit Product';
    qs('#product-id').value = product.id;
    qs('#product-sku').value = product.sku;
    qs('#product-name').value = product.name;
    qs('#product-category').value = product.category;
    qs('#product-stock').value = product.current_stock;
    qs('#product-reorder').value = product.reorder_level;
    qs('#product-price').value = product.unit_price;
    qs('#product-supplier').value = product.supplier_id || '';
}

function clearProductForm() {
    qs('#product-form-title').textContent = 'Add Product';
    qs('#product-form').reset();
    qs('#product-id').value = '';
}

async function deleteProduct(id) {
    const shouldDelete = confirm('Delete this product? Related stock movements will also be deleted.');

    if (!shouldDelete) return;

    try {
        await apiRequest(`/products/${id}`, {
            method: 'DELETE'
        });

        showToast('Product deleted');
        await refreshAllData();
    } catch (error) {
        showToast(error.message, true);
    }
}

async function loadSuppliers() {
    suppliers = await apiRequest('/suppliers');

    renderSuppliersTable();
    renderProductOptions();
}

function renderSuppliersTable() {
    const rows = suppliers.map(supplier => `
        <tr>
            <td>
                <strong>${supplier.name}</strong><br>
                <small>${supplier.contact_person || ''} ${supplier.phone ? '· ' + supplier.phone : ''}</small>
            </td>
            <td>${supplier.category}</td>
            <td>${supplier.reliability_rating}/10</td>
            <td>${supplier.average_lead_time_days} days</td>
            <td>${supplier.cost_rating}/10</td>
            <td>
                ${hasRole('Admin', 'Manager') ? `<button class="action-btn edit-btn" onclick="editSupplier(${supplier.id})">Edit</button>` : ''}
                ${hasRole('Admin') ? `<button class="action-btn delete-btn" onclick="deleteSupplier(${supplier.id})">Delete</button>` : ''}
                ${!hasRole('Admin', 'Manager') ? '<span class="muted-text">View only</span>' : ''}
            </td>
        </tr>
    `).join('');

    qs('#suppliers-table').innerHTML = rows || tableEmptyMessage(6, 'No suppliers found.');
}

function editSupplier(id) {
    const supplier = suppliers.find(item => item.id === id);

    if (!supplier) return;

    qs('#supplier-form-title').textContent = 'Edit Supplier';
    qs('#supplier-id').value = supplier.id;
    qs('#supplier-name').value = supplier.name;
    qs('#supplier-contact').value = supplier.contact_person || '';
    qs('#supplier-phone').value = supplier.phone || '';
    qs('#supplier-email').value = supplier.email || '';
    qs('#supplier-category').value = supplier.category;
    qs('#supplier-reliability').value = supplier.reliability_rating;
    qs('#supplier-lead-time').value = supplier.average_lead_time_days;
    qs('#supplier-cost').value = supplier.cost_rating;
}

function clearSupplierForm() {
    qs('#supplier-form-title').textContent = 'Add Supplier';
    qs('#supplier-form').reset();
    qs('#supplier-id').value = '';
}

async function deleteSupplier(id) {
    const shouldDelete = confirm('Delete this supplier? Products will remain but supplier field will become empty.');

    if (!shouldDelete) return;

    try {
        await apiRequest(`/suppliers/${id}`, {
            method: 'DELETE'
        });

        showToast('Supplier deleted');
        await refreshAllData();
    } catch (error) {
        showToast(error.message, true);
    }
}

async function loadMovements() {
    const movements = await apiRequest('/movements');

    const rows = movements.map(item => `
        <tr>
            <td>${item.movement_date}</td>
            <td>${item.sku}</td>
            <td>${item.product_name}</td>
            <td>
                ${
                    item.movement_type === 'IN'
                        ? statusBadge('Stable').replace('Stable', 'IN')
                        : statusBadge('Risky').replace('Risky', 'OUT')
                }
            </td>
            <td>${item.quantity}</td>
            <td>${item.note || '-'}</td>
        </tr>
    `).join('');

    qs('#movements-table').innerHTML = rows || tableEmptyMessage(6, 'No stock movements recorded yet.');
}

async function loadPredictions() {
    predictions = await apiRequest('/predictions');

    const rows = predictions.map(item => `
        <tr>
            <td>
                <strong>${item.product_name}</strong><br>
                <small>${item.sku}</small>
            </td>
            <td>${item.current_stock}</td>
            <td>${item.avg_daily_demand}</td>
            <td>${item.predicted_next_7_days}</td>
            <td>${item.days_until_stockout ?? 'N/A'}</td>
            <td>${item.recommended_reorder_qty}</td>
            <td>${statusBadge(item.status)}</td>
        </tr>
    `).join('');

    qs('#prediction-table').innerHTML = rows || tableEmptyMessage(7, 'No prediction data available.');
}

async function loadSupplierAnalytics() {
    supplierAnalytics = await apiRequest('/supplier-analytics');

    const rows = supplierAnalytics.map(item => `
        <tr>
            <td>
                <strong>${item.name}</strong><br>
                <small>${item.category}</small>
            </td>
            <td>${item.product_count}</td>
            <td>${takaFormatter.format(item.inventory_value || 0)}</td>
            <td>${item.performance_score}/10</td>
            <td>${statusBadge(item.performance_level)}</td>
        </tr>
    `).join('');

    qs('#supplier-analytics-table').innerHTML = rows || tableEmptyMessage(5, 'No supplier analytics available.');
}

async function loadRoles() {
    if (!hasRole('Admin')) return;
    roles = await apiRequest('/roles');
    const roleSelect = qs('#new-role');
    if (roleSelect) {
        roleSelect.innerHTML = roles.map(role => `<option value="${role.id}">${role.role_name}</option>`).join('');
    }
}

async function loadUsers() {
    if (!hasRole('Admin')) return;
    users = await apiRequest('/users');
    const rows = users.map(user => `
        <tr>
            <td>${user.username}</td>
            <td>${user.full_name || '-'}</td>
            <td>${user.email || '-'}</td>
            <td><span class="badge success">${user.role_name}</span></td>
            <td>${user.is_active ? 'Active' : 'Inactive'}</td>
        </tr>
    `).join('');
    qs('#users-table').innerHTML = rows || tableEmptyMessage(5, 'No users found.');
}

async function refreshAllData() {
    try {
        await checkConnection();
        await loadSuppliers();
        await loadProducts();
        await loadDashboard();
        await loadMovements();
        await loadPredictions();
        await loadSupplierAnalytics();
        await loadRoles();
        await loadUsers();
    } catch (error) {
        showToast(error.message, true);
    }
}

function setupNavigation() {
    qsa('.nav-link').forEach(button => {
        button.addEventListener('click', () => {
            qsa('.nav-link').forEach(item => item.classList.remove('active'));
            qsa('.page-section').forEach(section => section.classList.remove('active-section'));

            button.classList.add('active');

            const sectionId = button.dataset.section;

            qs(`#${sectionId}`).classList.add('active-section');
            qs('#page-title').textContent = pageTitles[sectionId];
        });
    });
}

function setupForms() {
    const productForm = qs('#product-form');
    const supplierForm = qs('#supplier-form');
    const movementForm = qs('#movement-form');
    const userForm = qs('#user-form');

    if (productForm) {
        productForm.addEventListener('submit', async event => {
            event.preventDefault();

            const id = qs('#product-id').value;

            const payload = {
                sku: qs('#product-sku').value.trim(),
                name: qs('#product-name').value.trim(),
                category: qs('#product-category').value.trim(),
                current_stock: Number(qs('#product-stock').value),
                reorder_level: Number(qs('#product-reorder').value),
                unit_price: Number(qs('#product-price').value),
                supplier_id: qs('#product-supplier').value || null
            };

            try {
                if (id) {
                    await apiRequest(`/products/${id}`, {
                        method: 'PUT',
                        body: JSON.stringify(payload)
                    });

                    showToast('Product updated');
                } else {
                    await apiRequest('/products', {
                        method: 'POST',
                        body: JSON.stringify(payload)
                    });

                    showToast('Product created');
                }

                clearProductForm();
                await refreshAllData();
            } catch (error) {
                showToast(error.message, true);
            }
        });
    }

    if (supplierForm) {
        supplierForm.addEventListener('submit', async event => {
            event.preventDefault();

            const id = qs('#supplier-id').value;

            const payload = {
                name: qs('#supplier-name').value.trim(),
                contact_person: qs('#supplier-contact').value.trim(),
                phone: qs('#supplier-phone').value.trim(),
                email: qs('#supplier-email').value.trim(),
                category: qs('#supplier-category').value.trim(),
                reliability_rating: Number(qs('#supplier-reliability').value),
                average_lead_time_days: Number(qs('#supplier-lead-time').value),
                cost_rating: Number(qs('#supplier-cost').value)
            };

            try {
                if (id) {
                    await apiRequest(`/suppliers/${id}`, {
                        method: 'PUT',
                        body: JSON.stringify(payload)
                    });

                    showToast('Supplier updated');
                } else {
                    await apiRequest('/suppliers', {
                        method: 'POST',
                        body: JSON.stringify(payload)
                    });

                    showToast('Supplier created');
                }

                clearSupplierForm();
                await refreshAllData();
            } catch (error) {
                showToast(error.message, true);
            }
        });
    }

    if (movementForm) {
        movementForm.addEventListener('submit', async event => {
            event.preventDefault();

            const payload = {
                product_id: Number(qs('#movement-product').value),
                movement_type: qs('#movement-type').value,
                quantity: Number(qs('#movement-quantity').value),
                movement_date: qs('#movement-date').value || null,
                note: qs('#movement-note').value.trim()
            };

            try {
                await apiRequest('/movements', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });

                showToast('Stock movement saved');

                qs('#movement-form').reset();

                await refreshAllData();
            } catch (error) {
                showToast(error.message, true);
            }
        });
    }

    if (userForm) {
        userForm.addEventListener('submit', async event => {
            event.preventDefault();

            const payload = {
                username: qs('#new-username').value.trim(),
                password: qs('#new-password').value,
                full_name: qs('#new-full-name').value.trim(),
                email: qs('#new-email').value.trim(),
                role_id: Number(qs('#new-role').value)
            };

            try {
                await apiRequest('/users', {
                    method: 'POST',
                    body: JSON.stringify(payload)
                });
                showToast('User created');
                userForm.reset();
                await loadUsers();
            } catch (error) {
                showToast(error.message, true);
            }
        });
    }

    const clearProductButton = qs('#clear-product-form');
    const clearSupplierButton = qs('#clear-supplier-form');
    const refreshButton = qs('#refresh-button');
    const productSearch = qs('#product-search');

    if (clearProductButton) {
        clearProductButton.addEventListener('click', clearProductForm);
    }

    if (clearSupplierButton) {
        clearSupplierButton.addEventListener('click', clearSupplierForm);
    }

    if (refreshButton) {
        refreshButton.addEventListener('click', refreshAllData);
    }

    if (productSearch) {
        productSearch.addEventListener('input', renderProductsTable);
    }

    const loginForm = qs('#login-form');
    const logoutButton = qs('#logout-button');
    if (loginForm) loginForm.addEventListener('submit', loginUser);
    if (logoutButton) logoutButton.addEventListener('click', logoutUser);
}

window.editProduct = editProduct;
window.deleteProduct = deleteProduct;
window.editSupplier = editSupplier;
window.deleteSupplier = deleteSupplier;

document.addEventListener('DOMContentLoaded', () => {
    setupNavigation();
    setupForms();
    checkAuth();
});
