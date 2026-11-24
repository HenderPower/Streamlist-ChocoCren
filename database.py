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
            
def _next_code(conn: sqlite3.Connection, table: str, prefix: str) -> str:
    row = conn.execute(f"SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM {table}").fetchone()
    return f"{prefix}-{int(row['next_id']):05d}"


def _validate_product_fields(
    name: str, category: str, flavor: str, size: str, price_cents: int, stock: int, min_stock: int
) -> None:
    if len(name.strip()) < 2 or len(name.strip()) > 120:
        raise RuleError("O nome do produto deve ter entre 2 e 120 caracteres.")
    if category not in PRODUCT_CATEGORIES:
        raise RuleError("Selecione uma categoria válida: Trufa, Barra ou Ovo de Páscoa.")
    if not flavor.strip() or len(flavor.strip()) > 60:
        raise RuleError("Informe um sabor com até 60 caracteres.")
    size_value = size.strip()
    if len(size_value) > 20 or not re.fullmatch(r"\d+(?:[.,]\d+)?\s?(?:g|kg)", size_value, flags=re.IGNORECASE):
        raise RuleError("Informe um peso válido em gramas ou quilogramas (ex.: 100g ou 1kg).")
    if Decimal(re.match(r"\d+(?:[.,]\d+)?", size_value).group(0).replace(",", ".")) <= 0:
        raise RuleError("O peso do produto deve ser maior que zero.")
    if price_cents <= 0:
        raise RuleError("O preço unitário deve ser maior que zero.")
    if not 0 <= stock <= 1_000_000:
        raise RuleError("O estoque deve estar entre 0 e 1.000.000 unidades.")
    if not 0 <= min_stock <= 1_000_000:
        raise RuleError("O estoque mínimo deve estar entre 0 e 1.000.000 unidades.")


def list_products(include_inactive: bool = True) -> list[dict]:
    with connection() as conn:
        sql = "SELECT * FROM products"
        if not include_inactive:
            sql += " WHERE active = 1"
        sql += " ORDER BY category, flavor, size"
        return [dict(row) for row in conn.execute(sql).fetchall()]


def get_product(product_id: int) -> dict | None:
    with connection() as conn:
        row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return dict(row) if row else None


def create_product(
    name: str, category: str, flavor: str, size: str, price_cents: int, stock: int,
    min_stock: int = DEFAULT_MIN_STOCK,
) -> str:
    _validate_product_fields(name, category, flavor, size, price_cents, stock, min_stock)
    timestamp = now_iso()
    try:
        with connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            code = _next_code(conn, "products", "CH")
            cur = conn.execute(
                """INSERT INTO products
                (sku,name,category,flavor,size,category_key,flavor_key,size_key,price_cents,stock,min_stock,active,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                (code, name.strip(), category, flavor.strip(), size.strip(), normalize_key(category),
                 normalize_key(flavor), normalize_key(size), price_cents, stock, min_stock, timestamp, timestamp),
            )
            product_id = int(cur.lastrowid)
            if stock:
                conn.execute(
                    "INSERT INTO stock_movements(product_id,movement_type,quantity_change,note,created_at) VALUES(?,?,?,?,?)",
                    (product_id, "ESTOQUE_INICIAL", stock, "Saldo informado no cadastro", timestamp),
                )
            conn.commit()
            return code
    except sqlite3.IntegrityError as exc:
        if "products.category_key" in str(exc) or "UNIQUE constraint failed: products.category_key" in str(exc):
            raise RuleError("Já existe um produto com essa combinação de tipo, sabor e peso.") from exc
        raise RuleError("Não foi possível cadastrar: já existe um SKU ou variação igual.") from exc


def update_product(
    product_id: int, name: str, category: str, flavor: str, size: str, price_cents: int,
    new_stock: int, min_stock: int,
) -> None:
    _validate_product_fields(name, category, flavor, size, price_cents, new_stock, min_stock)
    timestamp = now_iso()
    try:
        with connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            old = conn.execute("SELECT stock FROM products WHERE id=?", (product_id,)).fetchone()
            if not old:
                raise RuleError("Produto não encontrado.")
            delta = int(new_stock) - int(old["stock"])
            conn.execute(
                """UPDATE products SET name=?,category=?,flavor=?,size=?,category_key=?,flavor_key=?,size_key=?,
                price_cents=?,stock=?,min_stock=?,updated_at=? WHERE id=?""",
                (name.strip(), category, flavor.strip(), size.strip(), normalize_key(category), normalize_key(flavor),
                 normalize_key(size), price_cents, new_stock, min_stock, timestamp, product_id),
            )
            if delta:
                conn.execute(
                    "INSERT INTO stock_movements(product_id,movement_type,quantity_change,note,created_at) VALUES(?,?,?,?,?)",
                    (product_id, "AJUSTE", delta, "Ajuste manual de estoque no cadastro do produto", timestamp),
                )
            conn.commit()
    except sqlite3.IntegrityError as exc:
        raise RuleError("Essa combinação de tipo, sabor e peso já está cadastrada em outro produto.") from exc


def set_product_active(product_id: int, active: bool) -> None:
    with connection() as conn:
        conn.execute("UPDATE products SET active=?,updated_at=? WHERE id=?", (int(active), now_iso(), product_id))


def delete_product_if_unused(product_id: int) -> None:
    with connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        history = conn.execute("SELECT 1 FROM order_items WHERE product_id=? LIMIT 1", (product_id,)).fetchone()
        if history:
            conn.rollback()
            raise RuleError("Este produto possui histórico de pedidos. Use Inativar em vez de excluir.")
        conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        conn.commit() 