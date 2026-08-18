from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from itemadapter import ItemAdapter


class SqlitePipeline:
    """Writes items to SQLite (WAL mode, batch INSERT OR REPLACE)."""

    def __init__(self, db_path: str, batch_size: int = 500):
        self.db_path = db_path
        self.batch_size = batch_size
        self.conn: sqlite3.Connection | None = None
        self.buffer: list[dict] = []

    @classmethod
    def from_crawler(cls, crawler):
        return cls(
            db_path=crawler.settings.get("SQLITE_PATH", "data/scraw.db"),
            batch_size=crawler.settings.getint("SQLITE_BATCH_SIZE", 500),
        )

    def open_spider(self, spider):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                key TEXT PRIMARY KEY,
                value TEXT,
                crawl_time TEXT,
                source TEXT
            )
            """
        )
        self.conn.commit()

    def close_spider(self, spider):
        self._flush()
        if self.conn:
            self.conn.close()

    def process_item(self, item, spider):
        self.buffer.append(ItemAdapter(item).asdict())
        if len(self.buffer) >= self.batch_size:
            self._flush()
        return item

    def _flush(self):
        if not self.buffer or not self.conn:
            return
        self.conn.executemany(
            "INSERT OR REPLACE INTO records (key, value, crawl_time, source) "
            "VALUES (:key, :value, :crawl_time, :source)",
            self.buffer,
        )
        self.conn.commit()
        self.buffer.clear()


class JsonLinesPipeline:
    """Appends items as JSON lines to output/items.jl."""

    def __init__(self, out_path: str):
        self.out_path = out_path
        self.fh = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(out_path=crawler.settings.get("JSONL_PATH", "output/items.jl"))

    def open_spider(self, spider):
        Path(self.out_path).parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.out_path, "a", encoding="utf-8")

    def close_spider(self, spider):
        if self.fh:
            self.fh.close()

    def process_item(self, item, spider):
        if self.fh:
            self.fh.write(json.dumps(ItemAdapter(item).asdict(), ensure_ascii=False) + "\n")
        return item
