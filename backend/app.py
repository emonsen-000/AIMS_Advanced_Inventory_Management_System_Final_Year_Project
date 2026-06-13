from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import wraps
from typing import Any, Dict, Iterable, List

from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from mysql.connector import Error
from werkzeug.security import check_password_hash, generate_password_hash

from backend.db_config import get_db_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret-key-in-production")
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="None",
)
CORS(app, supports_credentials=True)

ROLE_ADMIN = "Admin"
ROLE_MANAGER = "Manager"
ROLE_STAFF = "Staff"
ALL_ROLES = [ROLE_ADMIN, ROLE_MANAGER, ROLE_STAFF]


def make_json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def rows_to_dicts(cursor) -> List[Dict[str, Any]]:
    rows = cursor.fetchall()
    return [{key: make_json_safe(value) for key, value in row.items()} for row in rows]


def success(data: Any = None, message: str = "Success", status: int = 200):
    payload = {"ok": True, "message": message}
    if data is not None:
        payload["data"] = data
    return jsonify(payload), status


def failure(message: str, status: int = 400):
    return jsonify({"ok": False, "message": message}), status


def required_fields(payload: Dict[str, Any], fields: Iterable[str]) -> List[str]:
    return [field for field in fields if payload.get(field) in (None, "")]


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return failure("Login required", 401)
        return func(*args, **kwargs)
    return wrapper


def require_roles(*allowed_roles: str):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                return failure("Login required", 401)
            if session.get("role_name") not in allowed_roles:
                return failure("You do not have permission for this action", 403)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def current_user_payload() -> Dict[str, Any]:
    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "role": session.get("role_name"),
    }


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/api/health")
def health():
    try:
        conn = get_db_connection()
        conn.close()
        return success({"database": "connected"}, "Backend and database are running")
    except Error as exc:
        return failure(f"Database connection failed: {exc}", 500)


@app.route("/api/auth/login", methods=["POST"])
def login():
    payload = request.get_json(force=True)
    missing = required_fields(payload, ["username", "password"])
    if missing:
        return failure(f"Missing fields: {', '.join(missing)}")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT u.id, u.username, u.password_hash, r.role_name
            FROM users u
            INNER JOIN roles r ON r.id = u.role_id
            WHERE u.username=%s AND u.is_active=1
            """,
            (payload["username"].strip(),),
        )
        user = cursor.fetchone()
        if not user or not check_password_hash(user["password_hash"], payload["password"]):
            return failure("Invalid username or password", 401)

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role_name"] = user["role_name"]
        return success(current_user_payload(), "Login successful")
    finally:
        cursor.close()
        conn.close()


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return success(message="Logged out")


@app.route("/api/auth/me")
def me():
    if not session.get("user_id"):
        return success({"logged_in": False})
    return success({"logged_in": True, "user": current_user_payload()})


@app.route("/api/roles")
@require_roles(ROLE_ADMIN)
def get_roles():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, role_name FROM roles ORDER BY id")
    roles = rows_to_dicts(cursor)
    cursor.close()
    conn.close()
    return success(roles)


@app.route("/api/users", methods=["GET"])
@require_roles(ROLE_ADMIN)
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT u.id, u.username, u.full_name, u.email, u.is_active, u.created_at, r.role_name
        FROM users u
        INNER JOIN roles r ON r.id = u.role_id
        ORDER BY u.id DESC
        """
    )
    users = rows_to_dicts(cursor)
    cursor.close()
    conn.close()
    return success(users)


@app.route("/api/users", methods=["POST"])
@require_roles(ROLE_ADMIN)
def create_user():
    payload = request.get_json(force=True)
    missing = required_fields(payload, ["username", "password", "role_id"])
    if missing:
        return failure(f"Missing fields: {', '.join(missing)}")

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, role_id, full_name, email, is_active)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                payload["username"].strip(),
                generate_password_hash(payload["password"]),
                int(payload["role_id"]),
                payload.get("full_name", ""),
                payload.get("email", ""),
                int(payload.get("is_active", 1)),
            ),
        )
        conn.commit()
        return success({"id": cursor.lastrowid}, "User created", 201)
    except Error as exc:
        conn.rollback()
        return failure(str(exc), 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total_products FROM products")
    total_products = cursor.fetchone()["total_products"]
    cursor.execute("SELECT COUNT(*) AS total_suppliers FROM suppliers")
    total_suppliers = cursor.fetchone()["total_suppliers"]
    cursor.execute("SELECT COUNT(*) AS low_stock_items FROM products WHERE current_stock <= reorder_level")
    low_stock_items = cursor.fetchone()["low_stock_items"]
    cursor.execute("SELECT COALESCE(SUM(current_stock * unit_price), 0) AS inventory_value FROM products")
    inventory_value = make_json_safe(cursor.fetchone()["inventory_value"])
    cursor.execute(
        """
        SELECT p.id, p.name, p.sku, p.current_stock, p.reorder_level, s.name AS supplier_name
        FROM products p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        WHERE p.current_stock <= p.reorder_level
        ORDER BY (p.current_stock - p.reorder_level) ASC
        LIMIT 8
        """
    )
    low_stock_products = rows_to_dicts(cursor)
    cursor.execute(
        """
        SELECT DATE(movement_date) AS day, COALESCE(SUM(quantity), 0) AS units_sold
        FROM stock_movements
        WHERE movement_type = 'OUT' AND movement_date >= CURDATE() - INTERVAL 13 DAY
        GROUP BY DATE(movement_date)
        ORDER BY day
        """
    )
    sales_trend = rows_to_dicts(cursor)
    cursor.close()
    conn.close()
    return success({"total_products": total_products, "total_suppliers": total_suppliers, "low_stock_items": low_stock_items, "inventory_value": inventory_value, "low_stock_products": low_stock_products, "sales_trend": sales_trend})


@app.route("/api/products", methods=["GET"])
@login_required
def get_products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT p.id, p.sku, p.name, p.category, p.current_stock, p.reorder_level,
               p.unit_price, p.supplier_id, s.name AS supplier_name, p.created_at
        FROM products p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        ORDER BY p.id DESC
        """
    )
    products = rows_to_dicts(cursor)
    cursor.close()
    conn.close()
    return success(products)


@app.route("/api/products", methods=["POST"])
@require_roles(ROLE_ADMIN, ROLE_MANAGER)
def create_product():
    payload = request.get_json(force=True)
    missing = required_fields(payload, ["sku", "name", "category", "current_stock", "reorder_level", "unit_price"])
    if missing:
        return failure(f"Missing fields: {', '.join(missing)}")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            INSERT INTO products (sku, name, category, current_stock, reorder_level, unit_price, supplier_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (payload["sku"], payload["name"], payload["category"], int(payload["current_stock"]), int(payload["reorder_level"]), float(payload["unit_price"]), payload.get("supplier_id") or None),
        )
        conn.commit()
        return success({"id": cursor.lastrowid}, "Product created", 201)
    except Error as exc:
        conn.rollback()
        return failure(str(exc), 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/products/<int:product_id>", methods=["PUT"])
@require_roles(ROLE_ADMIN, ROLE_MANAGER)
def update_product(product_id: int):
    payload = request.get_json(force=True)
    missing = required_fields(payload, ["sku", "name", "category", "current_stock", "reorder_level", "unit_price"])
    if missing:
        return failure(f"Missing fields: {', '.join(missing)}")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE products
            SET sku=%s, name=%s, category=%s, current_stock=%s, reorder_level=%s,
                unit_price=%s, supplier_id=%s
            WHERE id=%s
            """,
            (payload["sku"], payload["name"], payload["category"], int(payload["current_stock"]), int(payload["reorder_level"]), float(payload["unit_price"]), payload.get("supplier_id") or None, product_id),
        )
        conn.commit()
        return success(message="Product updated")
    except Error as exc:
        conn.rollback()
        return failure(str(exc), 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/products/<int:product_id>", methods=["DELETE"])
@require_roles(ROLE_ADMIN)
def delete_product(product_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM products WHERE id=%s", (product_id,))
        conn.commit()
        return success(message="Product deleted")
    except Error as exc:
        conn.rollback()
        return failure(str(exc), 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/suppliers", methods=["GET"])
@login_required
def get_suppliers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM suppliers ORDER BY id DESC")
    suppliers = rows_to_dicts(cursor)
    cursor.close()
    conn.close()
    return success(suppliers)


@app.route("/api/suppliers", methods=["POST"])
@require_roles(ROLE_ADMIN, ROLE_MANAGER)
def create_supplier():
    payload = request.get_json(force=True)
    missing = required_fields(payload, ["name", "category", "reliability_rating", "average_lead_time_days", "cost_rating"])
    if missing:
        return failure(f"Missing fields: {', '.join(missing)}")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO suppliers
            (name, contact_person, phone, email, category, reliability_rating, average_lead_time_days, cost_rating)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (payload["name"], payload.get("contact_person", ""), payload.get("phone", ""), payload.get("email", ""), payload["category"], float(payload["reliability_rating"]), int(payload["average_lead_time_days"]), float(payload["cost_rating"])),
        )
        conn.commit()
        return success({"id": cursor.lastrowid}, "Supplier created", 201)
    except Error as exc:
        conn.rollback()
        return failure(str(exc), 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/suppliers/<int:supplier_id>", methods=["PUT"])
@require_roles(ROLE_ADMIN, ROLE_MANAGER)
def update_supplier(supplier_id: int):
    payload = request.get_json(force=True)
    missing = required_fields(payload, ["name", "category", "reliability_rating", "average_lead_time_days", "cost_rating"])
    if missing:
        return failure(f"Missing fields: {', '.join(missing)}")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE suppliers
            SET name=%s, contact_person=%s, phone=%s, email=%s, category=%s,
                reliability_rating=%s, average_lead_time_days=%s, cost_rating=%s
            WHERE id=%s
            """,
            (payload["name"], payload.get("contact_person", ""), payload.get("phone", ""), payload.get("email", ""), payload["category"], float(payload["reliability_rating"]), int(payload["average_lead_time_days"]), float(payload["cost_rating"]), supplier_id),
        )
        conn.commit()
        return success(message="Supplier updated")
    except Error as exc:
        conn.rollback()
        return failure(str(exc), 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/suppliers/<int:supplier_id>", methods=["DELETE"])
@require_roles(ROLE_ADMIN)
def delete_supplier(supplier_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM suppliers WHERE id=%s", (supplier_id,))
        conn.commit()
        return success(message="Supplier deleted")
    except Error as exc:
        conn.rollback()
        return failure(str(exc), 500)
    finally:
        cursor.close()
        conn.close()


@app.route("/api/movements", methods=["GET"])
@login_required
def get_movements():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT sm.id, sm.product_id, p.name AS product_name, p.sku, sm.movement_type,
               sm.quantity, sm.note, sm.movement_date
        FROM stock_movements sm
        INNER JOIN products p ON sm.product_id = p.id
        ORDER BY sm.movement_date DESC, sm.id DESC
        LIMIT 100
        """
    )
    movements = rows_to_dicts(cursor)
    cursor.close()
    conn.close()
    return success(movements)


@app.route("/api/movements", methods=["POST"])
@require_roles(ROLE_ADMIN, ROLE_MANAGER, ROLE_STAFF)
def create_movement():
    payload = request.get_json(force=True)
    missing = required_fields(payload, ["product_id", "movement_type", "quantity"])
    if missing:
        return failure(f"Missing fields: {', '.join(missing)}")
    movement_type = payload["movement_type"].upper()
    if movement_type not in ("IN", "OUT"):
        return failure("movement_type must be IN or OUT")
    quantity = int(payload["quantity"])
    if quantity <= 0:
        return failure("Quantity must be greater than zero")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT current_stock FROM products WHERE id=%s FOR UPDATE", (payload["product_id"],))
        product = cursor.fetchone()
        if not product:
            return failure("Product not found", 404)
        new_stock = product["current_stock"] + quantity if movement_type == "IN" else product["current_stock"] - quantity
        if new_stock < 0:
            return failure("Not enough stock for this OUT movement")
        cursor.execute(
            """
            INSERT INTO stock_movements (product_id, movement_type, quantity, note, movement_date)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (payload["product_id"], movement_type, quantity, payload.get("note", ""), payload.get("movement_date") or date.today().isoformat()),
        )
        cursor.execute("UPDATE products SET current_stock=%s WHERE id=%s", (new_stock, payload["product_id"]))
        conn.commit()
        return success({"new_stock": new_stock}, "Stock movement saved", 201)
    except Error as exc:
        conn.rollback()
        return failure(str(exc), 500)
    finally:
        cursor.close()
        conn.close()


def linear_regression_slope(values: List[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    x_values = list(range(1, n + 1))
    x_mean = sum(x_values) / n
    y_mean = sum(values) / n
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, values))
    denominator = sum((x - x_mean) ** 2 for x in x_values)
    return numerator / denominator if denominator else 0.0


@app.route("/api/predictions")
@login_required
def predictions():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT p.id, p.name, p.sku, p.current_stock, p.reorder_level,
               COALESCE(s.average_lead_time_days, 7) AS lead_time
        FROM products p
        LEFT JOIN suppliers s ON p.supplier_id = s.id
        ORDER BY p.name
        """
    )
    products = rows_to_dicts(cursor)
    result = []
    today = date.today()
    start_day = today - timedelta(days=29)
    for product in products:
        cursor.execute(
            """
            SELECT DATE(movement_date) AS sale_day, SUM(quantity) AS units
            FROM stock_movements
            WHERE product_id=%s AND movement_type='OUT' AND movement_date >= %s
            GROUP BY DATE(movement_date)
            """,
            (product["id"], start_day),
        )
        raw_sales = {row["sale_day"]: float(row["units"] or 0) for row in cursor.fetchall()}
        daily_values = [raw_sales.get(start_day + timedelta(days=offset), 0.0) for offset in range(30)]
        avg_daily_demand = sum(daily_values) / 30
        slope = linear_regression_slope(daily_values)
        predicted_daily_demand = max(0.0, avg_daily_demand + slope * 7)
        predicted_next_7_days = round(predicted_daily_demand * 7, 2)
        days_until_stockout = round(product["current_stock"] / predicted_daily_demand, 1) if predicted_daily_demand > 0 else None
        lead_time = int(product["lead_time"] or 7)
        safety_stock = max(product["reorder_level"], round(predicted_daily_demand * 3))
        reorder_point = round((predicted_daily_demand * lead_time) + safety_stock)
        recommended_reorder_qty = max(0, reorder_point - int(product["current_stock"]))
        if product["current_stock"] <= product["reorder_level"]:
            status = "Reorder Now"
        elif days_until_stockout is not None and days_until_stockout <= lead_time + 3:
            status = "Watch Closely"
        else:
            status = "Stable"
        result.append({"product_id": product["id"], "sku": product["sku"], "product_name": product["name"], "current_stock": product["current_stock"], "avg_daily_demand": round(avg_daily_demand, 2), "trend_slope": round(slope, 3), "predicted_next_7_days": predicted_next_7_days, "days_until_stockout": days_until_stockout, "recommended_reorder_qty": recommended_reorder_qty, "status": status})
    cursor.close()
    conn.close()
    return success(result)


@app.route("/api/supplier-analytics")
@login_required
def supplier_analytics():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT s.id, s.name, s.category, s.reliability_rating, s.average_lead_time_days,
               s.cost_rating, COUNT(p.id) AS product_count,
               COALESCE(SUM(p.current_stock * p.unit_price), 0) AS inventory_value
        FROM suppliers s
        LEFT JOIN products p ON p.supplier_id = s.id
        GROUP BY s.id, s.name, s.category, s.reliability_rating, s.average_lead_time_days, s.cost_rating
        ORDER BY s.name
        """
    )
    rows = rows_to_dicts(cursor)
    analytics = []
    for row in rows:
        reliability = float(row["reliability_rating"] or 0)
        lead_time = float(row["average_lead_time_days"] or 0)
        cost = float(row["cost_rating"] or 0)
        lead_time_score = max(0, 10 - min(10, lead_time))
        performance_score = (reliability * 0.50) + (lead_time_score * 0.30) + ((10 - cost) * 0.20)
        if performance_score >= 8:
            level = "Excellent"
        elif performance_score >= 6.5:
            level = "Good"
        elif performance_score >= 5:
            level = "Average"
        else:
            level = "Risky"
        analytics.append({**row, "performance_score": round(performance_score, 2), "performance_level": level})
    cursor.close()
    conn.close()
    return success(analytics)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
