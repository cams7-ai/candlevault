"""Persistência SQLite. Operações financeiras ficam no domínio Decimal."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from .domain import Candle, canonical, parse_candle

SCHEMA = '''
CREATE TABLE IF NOT EXISTS candles (
    source TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
    open_time TEXT NOT NULL, close_time TEXT NOT NULL,
    open TEXT NOT NULL, high TEXT NOT NULL, low TEXT NOT NULL,
    close TEXT NOT NULL, volume TEXT NOT NULL,
    is_closed INTEGER NOT NULL CHECK(is_closed IN (0, 1)),
    snapshot_at TEXT NOT NULL, received_at TEXT NOT NULL,
    PRIMARY KEY(source, symbol, interval, open_time)
);
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY, filename TEXT NOT NULL, received_at TEXT NOT NULL,
    total INTEGER NOT NULL, inseridos INTEGER NOT NULL, atualizados INTEGER NOT NULL,
    ignorados INTEGER NOT NULL, rejeitados INTEGER NOT NULL,
    CHECK(total = inseridos + atualizados + ignorados + rejeitados)
);
'''


@contextmanager
def connect(path: str | Path, *, create: bool = False):
    path = Path(path).resolve()
    if create:
        path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path.as_uri() + ('?mode=rwc' if create else '?mode=ro'), uri=True)
    db.row_factory = sqlite3.Row
    try:
        if create:
            db.executescript(SCHEMA)
        yield Repository(db)
    finally:
        db.close()


class Repository:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    @staticmethod
    def decode(row: sqlite3.Row) -> Candle:
        data = dict(row)
        del data['received_at']
        data['is_closed'] = bool(data['is_closed'])
        return parse_candle(data)

    def get(self, candle: Candle) -> Candle | None:
        row = self.db.execute('''SELECT * FROM candles
            WHERE source=? AND symbol=? AND interval=? AND open_time=?''', candle.key).fetchone()
        return self.decode(row) if row else None

    def save(self, candle: Candle, received_at: str) -> None:
        data = candle.as_dict() | {'received_at': received_at}
        columns = ', '.join(data)
        placeholders = ', '.join('?' for _ in data)
        updates = ', '.join(f'{name}=excluded.{name}' for name in data if name not in (
            'source', 'symbol', 'interval', 'open_time'))
        self.db.execute(f'''INSERT INTO candles ({columns}) VALUES ({placeholders})
            ON CONFLICT(source, symbol, interval, open_time) DO UPDATE SET {updates}''',
                        tuple(data.values()))

    def summary(self, filename: str, received_at: str, counts: dict) -> None:
        self.db.execute('''INSERT INTO imports
            (filename, received_at, total, inseridos, atualizados, ignorados, rejeitados)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        (filename, received_at, sum(counts.values()), *counts.values()))

    def query(self, source, symbol, interval, start, end, closed_only=False) -> list[Candle]:
        sql = '''SELECT * FROM candles WHERE source=? AND symbol=? AND interval=?
                 AND open_time>=? AND open_time<?'''
        if closed_only:
            sql += ' AND is_closed=1'
        rows = self.db.execute(sql + ' ORDER BY open_time',
                               (source, symbol, interval, canonical(start), canonical(end)))
        return [self.decode(row) for row in rows]
