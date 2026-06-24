"""Shared test fixtures for Sentinel notification tests.

All DB modules (auth_db, watchlist_db, notification_db) share a single
``watchlist.db`` file in production. The ``notification_db`` fixture below
creates one temp file and monkeypatches ``_get_conn`` in all three modules
so they all hit the same database. This is the correct approach since
production code relies on cross-table queries (e.g.
``get_user_ids_needing_checks`` joins ``user_watchlist`` from auth_db with
``custom_alert_rules`` from notification_db).
"""

import os
import sqlite3
import tempfile

import pytest

# Must be set before any app imports
os.environ.setdefault("SENTINEL_API_KEY", "test-key")


@pytest.fixture
def notification_db():
    """Create a unified temp-file DB with all tables.

    Patches ``_get_conn`` in ``auth_db``, ``watchlist_db``, and
    ``notification_db`` so every call from any module hits the same
    temp file. Initializes all schemas. The file is cleaned up when
    the test ends.

    Yields a ``sqlite3.Connection`` for direct SQL in tests.
    """
    import src.data.auth_db as adb_mod
    import src.data.watchlist_db as wdb_mod
    import src.data.notification_db as ndb_mod

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name

    def _test_conn():
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    # Save originals
    adb_real = adb_mod._get_conn
    wdb_real = wdb_mod._get_conn
    ndb_real = ndb_mod._get_conn

    adb_mod._get_conn = _test_conn
    wdb_mod._get_conn = _test_conn
    ndb_mod._get_conn = _test_conn

    # Initialize all schemas
    adb_mod.init_auth_db()
    wdb_mod.init_db()
    ndb_mod.init_notification_db()

    yield _test_conn()

    # Restore originals
    adb_mod._get_conn = adb_real
    wdb_mod._get_conn = wdb_real
    ndb_mod._get_conn = ndb_real
    os.unlink(db_path)
