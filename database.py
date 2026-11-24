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