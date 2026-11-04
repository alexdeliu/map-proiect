import base64
import io
import json
import pytest

from src.app import APP_NAME, app, store


@pytest.fixture(autouse=True)
def reset_state():
    store.reset()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client


def _basic_auth_header(username: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


# --- Template tests (Common Contract) ---

def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert "uptime_seconds" in body


def test_version_reads_environment(client, monkeypatch):
    monkeypatch.setenv("APP_COMMIT", "abc1234")
    body = client.get("/version").get_json()
    assert body["commit"] == "abc1234"
    assert body["app"] == APP_NAME
    assert body["version"]
    assert body["built_at"]


def test_reset_returns_no_content(client):
    assert client.post("/reset").status_code == 204


def test_reset_rejects_get(client):
    assert client.get("/reset").status_code == 405


def test_reset_clears_store(client):
    store.next_id = 42
    client.post("/reset")
    assert store.next_id == 1


def test_home_returns_html(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.content_type.startswith("text/html")


def test_unknown_route_returns_not_found(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.get_json()["error"] == "not_found"


# --- Custom tests for Theme 4 (Inventory Management) ---

def test_create_product_uses_default_threshold_p15(client):
    response = client.post(
        "/products",
        json={"code": "CIOC-01", "name": "Ciocan", "initial_stock": 15},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["id"] == 1
    assert body["code"] == "CIOC-01"
    assert body["min_threshold"] == 15
    assert body["current_stock"] == 15


def test_list_products_ordered_by_code(client):
    client.post("/products", json={"code": "B-02", "name": "Surubelnita", "initial_stock": 10})
    client.post("/products", json={"code": "A-01", "name": "Patent", "initial_stock": 20})

    response = client.get("/products")
    assert response.status_code == 200
    items = response.get_json()
    assert [item["code"] for item in items] == ["A-01", "B-02"]


def test_below_threshold_boundary_strict_less(client):
    # Product with stock == min_threshold (15 == 15) is NOT below threshold
    client.post("/products", json={"code": "CIOC-01", "name": "Ciocan", "initial_stock": 15})
    assert client.get("/products?below_threshold=true").get_json() == []

    # After 'out' movement of 1, stock becomes 14 (< 15), so it appears in the list
    move_res = client.post("/movements", json={"product_id": 1, "type": "out", "quantity": 1})
    assert move_res.status_code == 201

    below_list = client.get("/products?below_threshold=true").get_json()
    assert len(below_list) == 1
    assert below_list[0]["current_stock"] == 14


def test_get_product_by_id_and_not_found(client):
    client.post("/products", json={"code": "P-01", "name": "Piulita", "initial_stock": 50})

    ok_res = client.get("/products/1")
    assert ok_res.status_code == 200
    assert ok_res.get_json()["current_stock"] == 50

    missing_res = client.get("/products/999")
    assert missing_res.status_code == 404
    assert missing_res.get_json()["error"] == "not_found"


def test_stock_calculation_with_in_and_out_movements(client):
    client.post("/products", json={"code": "CAB-01", "name": "Cablu", "initial_stock": 10})
    client.post("/movements", json={"product_id": 1, "type": "in", "quantity": 25})
    client.post("/movements", json={"product_id": 1, "type": "out", "quantity": 12})

    product = client.get("/products/1").get_json()
    assert product["current_stock"] == 23


def test_stats_computes_totals_correctly(client):
    client.post(
        "/products",
        json={"code": "P1", "name": "Produs 1", "initial_stock": 10, "min_threshold": 15},
    )
    client.post(
        "/products",
        json={"code": "P2", "name": "Produs 2", "initial_stock": 20, "min_threshold": 15},
    )

    stats = client.get("/stats").get_json()
    assert stats == {
        "total_products": 2,
        "below_threshold": 1,
        "total_stock": 30,
    }


# --- Validation and Conflict Error Tests (Minimum 3 required) ---

def test_rejects_duplicate_product_code_with_409(client):
    client.post("/products", json={"code": "DUP-01", "name": "Produs A", "initial_stock": 5})
    dup_res = client.post("/products", json={"code": "DUP-01", "name": "Produs B", "initial_stock": 8})

    assert dup_res.status_code == 409
    assert dup_res.get_json()["error"] == "conflict"


def test_rejects_invalid_product_code_length_with_400(client):
    too_long_code = "X" * 21
    res = client.post("/products", json={"code": too_long_code, "name": "Test", "initial_stock": 5})

    assert res.status_code == 400
    assert res.get_json()["error"] == "validation"


def test_rejects_negative_initial_stock_with_400(client):
    res = client.post("/products", json={"code": "NEG-01", "name": "Test", "initial_stock": -1})

    assert res.status_code == 400
    assert res.get_json()["error"] == "validation"


def test_rejects_out_movement_exceeding_stock_with_409(client):
    client.post("/products", json={"code": "LIM-01", "name": "Lampa", "initial_stock": 10})
    res = client.post("/movements", json={"product_id": 1, "type": "out", "quantity": 99})

    assert res.status_code == 409
    assert res.get_json()["error"] == "conflict"


def test_rejects_non_positive_or_invalid_movement_with_400(client):
    client.post("/products", json={"code": "MOV-01", "name": "Motor", "initial_stock": 10})

    zero_qty = client.post("/movements", json={"product_id": 1, "type": "in", "quantity": 0})
    assert zero_qty.status_code == 400
    assert zero_qty.get_json()["error"] == "validation"

    bad_type = client.post("/movements", json={"product_id": 1, "type": "transfer", "quantity": 5})
    assert bad_type.status_code == 400
    assert bad_type.get_json()["error"] == "validation"


def test_rejects_movement_for_nonexistent_product_with_404(client):
    res = client.post("/movements", json={"product_id": 999, "type": "in", "quantity": 5})

    assert res.status_code == 404
    assert res.get_json()["error"] == "not_found"


# --- Tests for Optional Extensions (/admin/stats and S3/R2 Persistence) ---

def test_admin_stats_rejects_missing_or_wrong_credentials_with_401(client, monkeypatch):
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret123")

    no_auth = client.get("/admin/stats")
    assert no_auth.status_code == 401
    assert no_auth.get_json()["error"] == "unauthorized"

    wrong_auth = client.get("/admin/stats", headers=_basic_auth_header("admin", "wrong"))
    assert wrong_auth.status_code == 401
    assert wrong_auth.get_json()["error"] == "unauthorized"


def test_admin_stats_rejects_when_env_not_configured(client, monkeypatch):
    monkeypatch.delenv("ADMIN_USER", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    res = client.get("/admin/stats", headers=_basic_auth_header("admin", "secret123"))
    assert res.status_code == 401
    assert res.get_json()["error"] == "unauthorized"


def test_admin_stats_returns_stats_with_valid_credentials(client, monkeypatch):
    monkeypatch.setenv("ADMIN_USER", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret123")

    client.post("/products", json={"code": "ADM-01", "name": "Produs Admin", "initial_stock": 10})
    res = client.get("/admin/stats", headers=_basic_auth_header("admin", "secret123"))

    assert res.status_code == 200
    assert res.get_json() == {
        "total_products": 1,
        "below_threshold": 1,
        "total_stock": 10,
    }


def test_s3_persistence_save_and_load_roundtrip(client, monkeypatch):
    saved_objects = {}

    class DummyS3Client:
        def put_object(self, Bucket, Key, Body, ContentType):
            saved_objects[(Bucket, Key)] = Body

        def get_object(self, Bucket, Key):
            return {"Body": io.BytesIO(saved_objects[(Bucket, Key)])}

    monkeypatch.setenv("S3_ENDPOINT", "https://example.r2.cloudflarestorage.com")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("S3_ACCESS_KEY", "test-key")
    monkeypatch.setenv("S3_SECRET_KEY", "test-secret")
    monkeypatch.setattr(store, "_create_s3_client", lambda cfg: DummyS3Client())

    client.post("/products", json={"code": "R2-01", "name": "Produs R2", "initial_stock": 20})
    client.post("/movements", json={"product_id": 1, "type": "out", "quantity": 6})

    # Simulate container restart by clearing memory and reloading from S3
    store._init_memory()
    assert store.products == {}

    store.load_from_s3()
    reloaded = client.get("/products/1")
    assert reloaded.status_code == 200
    assert reloaded.get_json()["current_stock"] == 14