import sqlite3
import time

from aicostmanager.delivery.persistent_queue_manager import PersistentQueueManager


def _init_db(path):
    conn = sqlite3.connect(path)
    with conn:
        conn.execute(
            """
            CREATE TABLE queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                retry_count INTEGER NOT NULL DEFAULT 0,
                scheduled_at REAL NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        now = time.time()
        conn.execute(
            "INSERT INTO queue (payload, status, retry_count, scheduled_at, created_at, updated_at) VALUES ('{}', 'failed', 1, ?, ?, ?)",
            (now, now, now),
        )
    conn.close()


def test_manager_lists_and_requeues_failed(tmp_path):
    db = tmp_path / "queue.db"
    _init_db(str(db))
    mgr = PersistentQueueManager(str(db))
    stats = mgr.stats()
    assert stats.get("failed") == 1
    failed = mgr.list_failed()
    assert len(failed) == 1
    mgr.requeue_failed()
    stats = mgr.stats()
    assert stats.get("failed", 0) == 0
