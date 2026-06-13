"""Database connection helper for the inventory system."""

from __future__ import annotations

import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_db_connection(use_database: bool = True):
    """Return a MySQL connection.

    use_database=True connects directly to the project database.
    use_database=False connects to the MySQL server only, useful during setup.
    """
    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "port": int(os.getenv("DB_PORT", "3306")),
    }

    if use_database:
        config["database"] = os.getenv("DB_NAME", "advanced_inventory_db")

    return mysql.connector.connect(**config)
