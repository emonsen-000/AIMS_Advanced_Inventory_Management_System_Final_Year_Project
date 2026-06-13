CREATE DATABASE IF NOT EXISTS advanced_inventory_db;
USE advanced_inventory_db;

DROP TABLE IF EXISTS stock_movements;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS roles;

CREATE TABLE roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role_id INT NOT NULL,
    full_name VARCHAR(120),
    email VARCHAR(120),
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_role
        FOREIGN KEY (role_id) REFERENCES roles(id)
        ON DELETE RESTRICT
);

CREATE TABLE suppliers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    contact_person VARCHAR(120),
    phone VARCHAR(40),
    email VARCHAR(120),
    category VARCHAR(80) NOT NULL,
    reliability_rating DECIMAL(4,2) NOT NULL DEFAULT 7.00,
    average_lead_time_days INT NOT NULL DEFAULT 7,
    cost_rating DECIMAL(4,2) NOT NULL DEFAULT 5.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(60) NOT NULL UNIQUE,
    name VARCHAR(150) NOT NULL,
    category VARCHAR(80) NOT NULL,
    current_stock INT NOT NULL DEFAULT 0,
    reorder_level INT NOT NULL DEFAULT 10,
    unit_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    supplier_id INT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_products_supplier
        FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
        ON DELETE SET NULL
);

CREATE TABLE stock_movements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    movement_type ENUM('IN', 'OUT') NOT NULL,
    quantity INT NOT NULL,
    note VARCHAR(255),
    movement_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_movements_product
        FOREIGN KEY (product_id) REFERENCES products(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_movements_product_date ON stock_movements(product_id, movement_date);
CREATE INDEX idx_products_stock ON products(current_stock, reorder_level);
CREATE INDEX idx_users_role ON users(role_id);

INSERT INTO roles (role_name)
VALUES ('Admin'), ('Manager'), ('Staff');

INSERT INTO suppliers
(name, contact_person, phone, email, category, reliability_rating, average_lead_time_days, cost_rating)
VALUES
('Global Office Supply', 'Rahim Ahmed', '+8801700000001', 'orders@globaloffice.com', 'Office Items', 8.80, 5, 4.50),
('TechSource Bangladesh', 'Nadia Karim', '+8801700000002', 'sales@techsource.com', 'Electronics', 7.60, 8, 6.20),
('FreshPack Logistics', 'Imran Hossain', '+8801700000003', 'support@freshpack.com', 'Packaging', 8.20, 4, 5.10),
('Budget Wholesale Ltd.', 'Sadia Islam', '+8801700000004', 'info@budgetwholesale.com', 'General', 6.50, 10, 3.80);

INSERT INTO products
(sku, name, category, current_stock, reorder_level, unit_price, supplier_id)
VALUES
('PEN-BLK-001', 'Black Ballpoint Pen', 'Stationery', 250, 80, 12.00, 1),
('NOTE-A4-100', 'A4 Notebook 100 Pages', 'Stationery', 65, 70, 65.00, 1),
('USB-32GB-01', 'USB Flash Drive 32GB', 'Electronics', 34, 25, 520.00, 2),
('HDMI-2M-01', 'HDMI Cable 2 Meter', 'Electronics', 18, 20, 350.00, 2),
('BOX-MED-01', 'Medium Packaging Box', 'Packaging', 120, 50, 38.00, 3),
('TAPE-PACK-01', 'Packaging Tape', 'Packaging', 42, 45, 90.00, 3),
('MASK-BOX-01', 'Disposable Mask Box', 'General', 90, 40, 180.00, 4),
('BAT-AA-04', 'AA Battery 4 Pack', 'Electronics', 22, 35, 240.00, 2);

INSERT INTO stock_movements (product_id, movement_type, quantity, note, movement_date)
VALUES
(1, 'OUT', 12, 'Daily sale', CURDATE() - INTERVAL 1 DAY),
(1, 'OUT', 15, 'Daily sale', CURDATE() - INTERVAL 2 DAY),
(1, 'OUT', 10, 'Daily sale', CURDATE() - INTERVAL 3 DAY),
(1, 'IN', 120, 'Restock from supplier', CURDATE() - INTERVAL 7 DAY),
(2, 'OUT', 8, 'Daily sale', CURDATE() - INTERVAL 1 DAY),
(2, 'OUT', 9, 'Daily sale', CURDATE() - INTERVAL 2 DAY),
(2, 'OUT', 7, 'Daily sale', CURDATE() - INTERVAL 4 DAY),
(3, 'OUT', 3, 'Daily sale', CURDATE() - INTERVAL 1 DAY),
(3, 'OUT', 4, 'Daily sale', CURDATE() - INTERVAL 3 DAY),
(3, 'IN', 25, 'Restock from supplier', CURDATE() - INTERVAL 12 DAY),
(4, 'OUT', 5, 'Daily sale', CURDATE() - INTERVAL 1 DAY),
(4, 'OUT', 4, 'Daily sale', CURDATE() - INTERVAL 2 DAY),
(5, 'OUT', 11, 'Daily sale', CURDATE() - INTERVAL 1 DAY),
(5, 'OUT', 10, 'Daily sale', CURDATE() - INTERVAL 2 DAY),
(6, 'OUT', 6, 'Daily sale', CURDATE() - INTERVAL 1 DAY),
(6, 'OUT', 5, 'Daily sale', CURDATE() - INTERVAL 3 DAY),
(7, 'OUT', 4, 'Daily sale', CURDATE() - INTERVAL 1 DAY),
(8, 'OUT', 6, 'Daily sale', CURDATE() - INTERVAL 1 DAY),
(8, 'OUT', 7, 'Daily sale', CURDATE() - INTERVAL 2 DAY);
