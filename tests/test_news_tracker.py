"""Tests for ticker_news_tracker CRUD in notification_db.py.

Covers insert, dedup (URL hash PK + title hash secondary),
count, mark notified/skipped, purge, and edge cases.
"""

import hashlib

from src.data.notification_db import (
    insert_news_article,
    count_unnotified_news,
    get_unnotified_articles,
    mark_article_notified,
    mark_articles_notified,
    mark_old_news_skipped,
    purge_old_news_entries,
    get_tickers_with_unnotified_news,
    count_news_title_hash,
)

_PUBLISHED = "2026-06-24T10:00:00Z"


def _article_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def _title_hash(title: str) -> str:
    return hashlib.sha256(title.lower().strip().encode()).hexdigest()


def _insert(ticker: str, url: str, title: str,
            summary: str = "Summary", **kw) -> bool:
    """Shorthand: insert a news article with published default."""
    return insert_news_article(
        ticker=ticker,
        article_id=_article_id(url),
        title_hash=_title_hash(title),
        url=url,
        title=title,
        summary=summary,
        publisher="Bloomberg",
        published=_PUBLISHED,
        **kw,
    )


# ─── insert_news_article — Dedup & Insert ────────────────────────────

class TestInsertNewsArticle:
    """insert_news_article must handle first insert and dedup correctly."""

    def test_insert_new_article(self, notification_db):
        """A fresh article should return True (inserted)."""
        assert _insert("AAPL", "https://example.com/aapl-1", "Apple News 1") is True

    def test_duplicate_primary_key_ignored(self, notification_db):
        """Same (ticker, article_id) inserted twice should return False (IGNOREd)."""
        assert _insert("AAPL", "https://example.com/dupe", "Duplicate") is True
        assert _insert("AAPL", "https://example.com/dupe", "Duplicate") is False

    def test_different_url_same_ticker(self, notification_db):
        """Different URLs for the same ticker should both be inserted."""
        assert _insert("AAPL", "https://example.com/a1", "Article 1") is True
        assert _insert("AAPL", "https://example.com/a2", "Article 2") is True
        assert count_unnotified_news("AAPL") == 2

    def test_same_url_different_ticker(self, notification_db):
        """Same article URL for different tickers should be allowed (PK is composite)."""
        assert _insert("AAPL", "https://example.com/shared", "Shared") is True
        assert _insert("MSFT", "https://example.com/shared", "Shared") is True
        assert count_unnotified_news("AAPL") == 1
        assert count_unnotified_news("MSFT") == 1

    def test_ticker_uppercased(self, notification_db):
        """Ticker should be stored uppercase."""
        assert _insert("aapl", "https://example.com/case", "Case Test") is True
        assert count_unnotified_news("AAPL") == 1
        assert count_unnotified_news("aapl") == 1  # query also uppercased

    def test_minimal_fields(self, notification_db):
        """Only required fields — summary/publisher default to None."""
        aid = _article_id("https://example.com/minimal")
        th = _title_hash("Minimal")
        inserted = insert_news_article(
            ticker="TSLA",
            article_id=aid,
            title_hash=th,
            url="https://example.com/minimal",
            title="Minimal",
            published=_PUBLISHED,
        )
        assert inserted is True
        assert count_unnotified_news("TSLA") == 1


# ─── count_unnotified_news ──────────────────────────────────────────

class TestCountUnnotifiedNews:
    """count_unnotified_news must return accurate counts."""

    def test_no_articles(self, notification_db):
        assert count_unnotified_news("AAPL") == 0

    def test_count_after_insert(self, notification_db):
        _insert("AAPL", "https://example.com/u1", "Unnotified 1")
        assert count_unnotified_news("AAPL") == 1

    def test_count_excludes_notified(self, notification_db):
        """Articles marked notified should not be counted."""
        aid = _insert_marked(notification_db, "AAPL")
        mark_article_notified("AAPL", aid)
        assert count_unnotified_news("AAPL") == 0

    def test_count_excludes_skipped(self, notification_db):
        """Articles with notified=2 should not be counted."""
        aid = _article_id("https://example.com/skipped-test")
        _insert("AAPL", "https://example.com/skipped-test", "Skipped Test")
        conn = notification_db
        conn.execute(
            "UPDATE ticker_news_tracker SET notified = 2 WHERE article_id = ?",
            (aid,),
        )
        conn.commit()
        assert count_unnotified_news("AAPL") == 0


def _insert_marked(conn, ticker: str = "AAPL", i: int = 0) -> str:
    """Insert an article and return its article_id."""
    url = f"https://example.com/marked-{i}"
    aid = _article_id(url)
    _insert(ticker, url, f"Marked {i}")
    return aid


# ─── get_unnotified_articles ────────────────────────────────────────

class TestGetUnnotifiedArticles:
    """get_unnotified_articles returns correct articles ordered by detected_at ASC."""

    def test_empty_when_none(self, notification_db):
        assert get_unnotified_articles("AAPL") == []

    def test_returns_unnotified_only(self, notification_db):
        aid_n = _insert_marked(notification_db, "AAPL", 1)
        aid_u = _insert_marked(notification_db, "AAPL", 2)
        mark_article_notified("AAPL", aid_n)
        articles = get_unnotified_articles("AAPL")
        assert len(articles) == 1
        assert articles[0]["article_id"] == aid_u

    def test_ordered_by_detected_asc(self, notification_db):
        aid1 = _article_id("https://example.com/order1")
        _insert("AAPL", "https://example.com/order1", "Order 1")
        import time
        time.sleep(1.1)  # ensure second boundary crossed for datetime('now')
        aid2 = _article_id("https://example.com/order2")
        _insert("AAPL", "https://example.com/order2", "Order 2")
        articles = get_unnotified_articles("AAPL")
        assert [a["article_id"] for a in articles] == [aid1, aid2]


# ─── mark_article_notified / mark_articles_notified ─────────────────

class TestMarkNotified:
    """Marking articles as notified must work individually and in batch."""

    def test_mark_single(self, notification_db):
        aid = _insert_marked(notification_db, "AAPL", 1)
        mark_article_notified("AAPL", aid)
        assert count_unnotified_news("AAPL") == 0

    def test_mark_nonexistent_does_not_error(self, notification_db):
        """Marking a non-existent article_id should not raise."""
        mark_article_notified("AAPL", _article_id("https://example.com/nonexistent"))

    def test_mark_batch(self, notification_db):
        aids = [_insert_marked(notification_db, "AAPL", i) for i in range(5)]
        mark_articles_notified("AAPL", aids[:3])
        assert count_unnotified_news("AAPL") == 2

    def test_mark_batch_empty(self, notification_db):
        """mark_articles_notified with empty list should be a no-op."""
        mark_articles_notified("AAPL", [])  # should not raise


# ─── mark_old_news_skipped (24h safety limit) ──────────────────────

class TestMarkOldNewsSkipped:
    """mark_old_news_skipped must mark aged unnotified articles as skipped."""

    def test_skips_old_articles(self, notification_db):
        aid = _article_id("https://example.com/old")
        _insert("AAPL", "https://example.com/old", "Old Article")
        conn = notification_db
        conn.execute(
            "UPDATE ticker_news_tracker SET detected_at = ? WHERE article_id = ?",
            ("2026-06-01T00:00:00", aid),
        )
        conn.commit()
        skipped = mark_old_news_skipped(hours=1)
        assert skipped >= 1
        assert count_unnotified_news("AAPL") == 0

    def test_does_not_skip_recent(self, notification_db):
        _insert("AAPL", "https://example.com/recent", "Recent Article")
        skipped = mark_old_news_skipped(hours=24)
        assert count_unnotified_news("AAPL") == 1

    def test_handles_empty_table(self, notification_db):
        skipped = mark_old_news_skipped(hours=24)
        assert skipped == 0


# ─── purge_old_news_entries (7 day cleanup) ────────────────────────

class TestPurgeOldNews:
    """Purge must remove entries older than N days."""

    def test_purges_old_entries(self, notification_db):
        aid = _article_id("https://example.com/purge-old")
        _insert("AAPL", "https://example.com/purge-old", "Purge Old")
        conn = notification_db
        conn.execute(
            "UPDATE ticker_news_tracker SET detected_at = ? WHERE article_id = ?",
            ("2026-06-01T00:00:00", aid),
        )
        conn.commit()
        purged = purge_old_news_entries(days=1)
        assert purged >= 1
        assert count_unnotified_news("AAPL") == 0

    def test_keeps_recent_entries(self, notification_db):
        _insert("AAPL", "https://example.com/purge-keep", "Purge Keep")
        purged = purge_old_news_entries(days=7)
        assert purged == 0
        assert count_unnotified_news("AAPL") == 1


# ─── get_tickers_with_unnotified_news ──────────────────────────────

class TestGetTickersWithUnnotifiedNews:
    """Must return tickers that have unnotified articles."""

    def test_empty_db(self, notification_db):
        assert get_tickers_with_unnotified_news() == []

    def test_single_ticker(self, notification_db):
        _insert("AAPL", "https://example.com/a1", "A1")
        result = get_tickers_with_unnotified_news()
        assert len(result) == 1
        assert result[0][0] == "AAPL"
        assert result[0][1] == 1

    def test_multiple_tickers(self, notification_db):
        _insert("AAPL", "https://example.com/a1", "A1")
        _insert("AAPL", "https://example.com/a2", "A2")
        _insert("MSFT", "https://example.com/m1", "M1")
        result = dict(get_tickers_with_unnotified_news())
        assert result["AAPL"] == 2
        assert result["MSFT"] == 1

    def test_excludes_notified(self, notification_db):
        aid = _insert_marked(notification_db, "AAPL", 1)
        mark_article_notified("AAPL", aid)
        assert get_tickers_with_unnotified_news() == []


# ─── count_news_title_hash (secondary dedup) ───────────────────────

class TestCountNewsTitleHash:
    """Title hash dedup must detect near-duplicates within the time window."""

    def test_no_match(self, notification_db):
        assert count_news_title_hash("AAPL", _title_hash("Unique Title"), hours=24) == 0

    def test_match_found(self, notification_db):
        th = _title_hash("Duplicate Title")
        _insert("AAPL", "https://example.com/orig", "Duplicate Title")
        assert count_news_title_hash("AAPL", th, hours=24) == 1

    def test_outside_window(self, notification_db):
        th = _title_hash("Old Article")
        aid = _article_id("https://example.com/old-title")
        _insert("AAPL", "https://example.com/old-title", "Old Article")
        conn = notification_db
        conn.execute(
            "UPDATE ticker_news_tracker SET detected_at = ? WHERE article_id = ?",
            ("2026-06-01T00:00:00", aid),
        )
        conn.commit()
        assert count_news_title_hash("AAPL", th, hours=1) == 0

    def test_different_ticker_no_match(self, notification_db):
        th = _title_hash("Cross Ticker")
        _insert("AAPL", "https://example.com/cross", "Cross Ticker")
        assert count_news_title_hash("MSFT", th, hours=24) == 0


# ─── Schema & Indexes ──────────────────────────────────────────────

class TestNewsTrackerSchema:
    """ticker_news_tracker table must have correct schema and indexes."""

    def test_table_exists(self, notification_db):
        conn = notification_db
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ticker_news_tracker'"
        ).fetchall()
        assert len(rows) == 1

    def test_columns(self, notification_db):
        conn = notification_db
        cols = {
            r["name"]: r["type"]
            for r in conn.execute("PRAGMA table_info(ticker_news_tracker)").fetchall()
        }
        assert cols["ticker"] == "TEXT"
        assert cols["article_id"] == "TEXT"
        assert cols["title_hash"] == "TEXT"
        assert cols["url"] == "TEXT"
        assert cols["title"] == "TEXT"
        assert cols["notified"] == "INTEGER"
        assert "publisher" in cols

    def test_composite_primary_key(self, notification_db):
        conn = notification_db
        pks = [
            r["name"]
            for r in conn.execute("PRAGMA table_info(ticker_news_tracker)").fetchall()
            if r["pk"] > 0
        ]
        assert "ticker" in pks
        assert "article_id" in pks

    def test_news_indexes_exist(self, notification_db):
        conn = notification_db
        indexes = [r["name"] for r in conn.execute("PRAGMA index_list(ticker_news_tracker)").fetchall()]
        names = set(indexes)
        assert "idx_news_detected" in names
        assert "idx_news_notified" in names
