"""API tests covering the BudgetService read-path endpoints."""

from fastapi.testclient import TestClient

_TRANSACTION_KEYS = {"date", "category", "subcategory", "amount", "source", "description"}


class TestHealth:
    def test_health_returns_ok(self, client: TestClient) -> None:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestTransactions:
    def test_list_all_returns_json_list(self, client: TestClient) -> None:
        response = client.get("/api/transactions")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 4
        assert set(body[0]) == _TRANSACTION_KEYS

    def test_filter_by_source(self, client: TestClient) -> None:
        response = client.get("/api/transactions", params={"source": "bank_b"})
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["source"] == "bank_b"

    def test_filter_by_category(self, client: TestClient) -> None:
        response = client.get("/api/transactions", params={"category": "Food & Drinks"})
        assert response.status_code == 200
        assert {t["category"] for t in response.json()} == {"Food & Drinks"}
        assert len(response.json()) == 2

    def test_filter_by_subcategory(self, client: TestClient) -> None:
        response = client.get("/api/transactions", params={"subcategory": "Groceries"})
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["subcategory"] == "Groceries"

    def test_filter_by_date_range(self, client: TestClient) -> None:
        response = client.get(
            "/api/transactions",
            params={"from_date": "2024-01-01", "to_date": "2024-01-31"},
        )
        assert response.status_code == 200
        body = response.json()
        # Three January transactions; the February one is excluded.
        assert len(body) == 3
        assert all("2024-01" in t["date"] for t in body)

    def test_filter_by_keyword(self, client: TestClient) -> None:
        response = client.get("/api/transactions", params={"keyword": "restaurant"})
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert "RESTAURANT" in (body[0]["description"] or "")


class TestTransactionCount:
    def test_count_returns_integer(self, client: TestClient) -> None:
        response = client.get("/api/transactions/count")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, int)
        assert body == 4


class TestAnalytics:
    def test_analytics_returns_result_shape(self, client: TestClient) -> None:
        response = client.get(
            "/api/analytics",
            params={"from_date": "2024-01-01", "to_date": "2024-12-31"},
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body) >= {"summary", "category_data", "monthly_data", "source_data", "period"}
        assert isinstance(body["category_data"], list)
        assert isinstance(body["monthly_data"], list)
        assert isinstance(body["source_data"], list)

    def test_analytics_summary_fields(self, client: TestClient) -> None:
        response = client.get("/api/analytics")
        assert response.status_code == 200
        summary = response.json()["summary"]
        assert set(summary) >= {
            "total_transactions",
            "total_income",
            "total_expenses",
            "net",
            "avg_transaction",
            "period",
        }
        assert summary["total_transactions"] == 4

    def test_analytics_respects_filters(self, client: TestClient) -> None:
        response = client.get("/api/analytics", params={"source": "bank_b"})
        assert response.status_code == 200
        assert response.json()["summary"]["total_transactions"] == 1


class TestFilters:
    def test_sources(self, client: TestClient) -> None:
        response = client.get("/api/filters/sources")
        assert response.status_code == 200
        assert response.json() == ["bank_a", "bank_b"]

    def test_categories(self, client: TestClient) -> None:
        response = client.get("/api/filters/categories")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert "Food & Drinks" in body
        assert "Transportation" in body

    def test_subcategories(self, client: TestClient) -> None:
        response = client.get("/api/filters/categories/Food & Drinks/subcategories")
        assert response.status_code == 200
        assert sorted(response.json()) == ["Groceries", "Restaurants"]
