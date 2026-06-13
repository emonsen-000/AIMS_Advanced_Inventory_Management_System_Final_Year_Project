"""Create the first Admin user.

Run after setup_database.py:
    python create_admin.py
"""

from __future__ import annotations

from getpass import getpass

from mysql.connector import Error
from werkzeug.security import generate_password_hash

from db_config import get_db_connection


def main():
    print("Create Admin Account")
    username = input("Username [admin]: ").strip() or "admin"
    full_name = input("Full name [System Admin]: ").strip() or "System Admin"
    email = input("Email [admin@example.com]: ").strip() or "admin@example.com"

    password = getpass("Password: ")
    confirm = getpass("Confirm password: ")

    if not password:
        print("Password cannot be empty.")
        return
    if password != confirm:
        print("Passwords do not match.")
        return

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM roles WHERE role_name='Admin'")
        role = cursor.fetchone()
        if not role:
            print("Admin role not found. Run setup_database.py first.")
            return

        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        if cursor.fetchone():
            print("A user with this username already exists.")
            return

        cursor.execute(
            """
            INSERT INTO users (username, password_hash, role_id, full_name, email, is_active)
            VALUES (%s, %s, %s, %s, %s, 1)
            """,
            (username, generate_password_hash(password), role["id"], full_name, email),
        )
        conn.commit()
        print(f"Admin user '{username}' created successfully.")
    except Error as exc:
        conn.rollback()
        print(f"Database error: {exc}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
