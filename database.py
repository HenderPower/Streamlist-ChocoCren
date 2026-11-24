from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable

DB_PATH = Path(os.getenv("CHOCOCREN_DB_PATH", "/data/chococren.db"))
PRODUCT_CATEGORIES = ("Trufa", "Barra", "Ovo de Páscoa")
ORDER_STATUSES = ("Em Preparo", "Saiu para Entrega", "Entregue", "Cancelado")
COURIER_STATUSES = ("Disponível", "Em Entrega", "Indisponível", "Em Manutenção")
DEFAULT_MIN_STOCK = 5

class RuleError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return re.sub(r"\s+", " ", value)


def money_to_cents(value: Decimal | float | int | str) -> int:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(amount * 100)


def cents_to_money(cents: int) -> Decimal:
    return (Decimal(int(cents)) / Decimal(100)).quantize(Decimal("0.01"))


@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 20000")
    try:
        yield conn
    finally:
        conn.close()

def initialize_database() -> None:
        with connection() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.executescript(
        """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                category TEXT NOT NULL CHECK(category IN ('Trufa','Barra','Ovo de Páscoa')),
                flavor TEXT NOT NULL,
                size TEXT NOT NULL,
                category_key TEXT NOT NULL,
                flavor_key TEXT NOT NULL,
                size_key TEXT NOT NULL,
                price_cents INTEGER NOT NULL CHECK(price_cents > 0),
                stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
                min_stock INTEGER NOT NULL DEFAULT 5 CHECK(min_stock >= 0),
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(category_key, flavor_key, size_key)
            );

            CREATE TABLE IF NOT EXISTS motoboys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                phone TEXT NOT NULL UNIQUE,
                plate TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK(status IN ('Disponível','Em Entrega','Indisponível','Em Manutenção')),
                active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                observations TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                customer_name TEXT NOT NULL,
                customer_phone TEXT NOT NULL,
                delivery_address TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('Em Preparo','Saiu para Entrega','Entregue','Cancelado')),
                motoboy_id INTEGER REFERENCES motoboys(id) ON DELETE RESTRICT,
                subtotal_cents INTEGER NOT NULL CHECK(subtotal_cents >= 0),
                discount_percent TEXT NOT NULL DEFAULT '0',
                discount_cents INTEGER NOT NULL DEFAULT 0 CHECK(discount_cents >= 0),
                delivery_fee_cents INTEGER NOT NULL DEFAULT 0 CHECK(delivery_fee_cents >= 0),
                service_fee_cents INTEGER NOT NULL DEFAULT 0 CHECK(service_fee_cents >= 0),
                total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
                cancellation_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                delivered_at TEXT
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                flavor TEXT NOT NULL,
                size TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents > 0),
                subtotal_cents INTEGER NOT NULL CHECK(subtotal_cents >= 0)
            );

            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                movement_type TEXT NOT NULL,
                quantity_change INTEGER NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_products_active ON products(active);
            CREATE INDEX IF NOT EXISTS idx_products_stock ON products(stock, min_stock);
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
            CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
            CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
            CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements(product_id);
            """
        )  