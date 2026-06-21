"""Integration tests for the Flask API response schemas."""
import os
import pytest

# Must be set before importing server module (it checks at import time)
os.environ.setdefault("SENTINEL_API_KEY", "test-key")

from src.api.server import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Health endpoint must always return the full response schema."""

    REQUIRED_KEYS = {
        "score", "name", "sector", "price", "change", "change_pct",
        "verdict", "fscore", "criteria",
        "zscore_score", "zscore_zone", "zscore_explanation",
        "zscore_normalized", "zscore_x1", "zscore_x2", "zscore_x3", "zscore_x4",
        "news",
    }

    def test_health_returns_all_fields(self, client):
        """Health endpoint must include every expected field, especially news."""
        resp = client.get("/api/data/AAPL/health", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        missing = self.REQUIRED_KEYS - set(data.keys())
        assert not missing, f"Health endpoint missing fields: {missing}"

    def test_news_field_is_list(self, client):
        """The news field must be a list (may be empty but never missing or wrong type)."""
        resp = client.get("/api/data/AAPL/health", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data["news"], list), f"news must be a list, got {type(data['news'])}"

    def test_news_items_have_required_keys(self, client):
        """Each news item must have the expected shape."""
        resp = client.get("/api/data/AAPL/health", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        for item in data["news"]:
            assert "title" in item, "news item missing 'title'"
            assert "url" in item, "news item missing 'url'"
            assert "publisher" in item, "news item missing 'publisher'"
            assert "published" in item, "news item missing 'published'"


class TestSupplyChainEndpoint:
    """Supply chain endpoint must return curated + Vala-Fi merged data."""

    def test_supply_chain_returns_curated_relationships(self, client):
        """NVDA has 18 curated relationships in company_links.json.
        The endpoint must return them even when Vala-Fi returns empty.
        Regression test for: endpoint only called Vala-Fi, ignoring curated data.
        """
        resp = client.get("/api/data/NVDA/supply-chain", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "relationships" in data, "supply-chain must include relationships key"
        assert len(data["relationships"]) >= 18, (
            f"Expected >=18 curated relationships for NVDA, got {len(data['relationships'])}"
        )

    def test_supply_chain_relationship_has_geo(self, client):
        """Each relationship must include target_geo with domicile."""
        resp = client.get("/api/data/NVDA/supply-chain", headers={"X-API-Key": "test-key"})
        data = resp.get_json()
        for rel in data["relationships"][:5]:
            assert "target_geo" in rel, "relationship missing target_geo"
            assert "domicile" in rel["target_geo"], "target_geo missing domicile"

    def test_supply_chain_required_keys(self, client):
        """Each relationship must have the expected keys."""
        resp = client.get("/api/data/NVDA/supply-chain", headers={"X-API-Key": "test-key"})
        data = resp.get_json()
        required = {"source", "target", "type", "strength", "target_geo", "investability_score"}
        for rel in data["relationships"]:
            missing = required - set(rel.keys())
            assert not missing, f"relationship missing keys: {missing}"
