"""Create the MySQL database and tables for the project.

Before running:
1. Install MySQL Server.
2. Update .env with your MySQL username/password.
3. Run: python setup_database.py
"""

from __future__ import annotations

import os
import re

from db_config import get_db_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(BASE_DIR, "schema.sql")


def split_sql_statements(sql_text: str):
    """Split SQL statements safely enough for this schema file."""
    cleaned_lines = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)
    return [stmt.strip() for stmt in re.split(r";\s*(?:\n|$)", cleaned) if stmt.strip()]


def main():
    connection = get_db_connection(use_database=False)
    cursor = connection.cursor()

    with open(SCHEMA_FILE, "r", encoding="utf-8") as file:
        sql_text = file.read()

    for statement in split_sql_statements(sql_text):
        cursor.execute(statement)

    connection.commit()
    cursor.close()
    connection.close()
    print("Database setup completed successfully.")


if __name__ == "__main__":
    main()
