"""Inventory management web service for the MAP individual project.

Implements the common HTTP contract (/health, /version, /, /reset),
Theme 4 routes (/products, /movements, /stats), and optional extensions
(Cloudflare R2 S3-compatible persistence and protected /admin/stats route).
"""

import json
import os
import secrets
import time
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, jsonify, request

APP_NAME = "map-project"
APP_VERSION = "0.1.0"
STARTED_AT = time.monotonic()

# Theme 4 specific parameter: default minimum stock threshold (P = 15)
DEFAULT_MIN_THRESHOLD = 15
MAX_CODE_LENGTH = 20
S3_STATE_KEY = "inventory_state.json"

app = Flask(__name__)


def is_valid_int(value: Any) -> bool:
    """Check if value is a strict integer (excluding booleans)."""
    return isinstance(value, int) and not isinstance(value, bool)


def error_response(error_code: str, message: str, status_code: int):
    """Build a standard error response matching the common contract."""
    return jsonify(error=error_code, message=message), status_code


class Store:
    """Holds the application data in memory with optional S3/R2 persistence.

    Current stock is never stored directly; it is dynamically calculated
    from initial_stock plus 'in' movements minus 'out' movements.
    """

    def __init__(self) -> None:
        self._init_memory()
        self.load_from_s3()

    def _init_memory(self) -> None:
        self.next_id = 1
        self.next_movement_id = 1
        self.products: dict[int, dict[str, Any]] = {}
        self.movements: list[dict[str, Any]] = []

    def _get_s3_config(self) -> dict[str, str] | None:
        """Read S3 configuration from environment variables if all are present."""
        endpoint = os.getenv("S3_ENDPOINT")
        bucket = os.getenv("S3_BUCKET")
        access_key = os.getenv("S3_ACCESS_KEY")
        secret_key = os.getenv("S3_SECRET_KEY")
        if endpoint and bucket and access_key and secret_key:
            return {
                "endpoint": endpoint,
                "bucket": bucket,
                "access_key": access_key,
                "secret_key": secret_key,
            }
        return None

    def _create_s3_client(self, cfg: dict[str, str]):
        """Create an S3-compatible client configured for Cloudflare R2 / S3."""
        return boto3.client(
            "s3",
            endpoint_url=cfg["endpoint"],
            aws_access_key_id=cfg["access_key"],
            aws_secret_access_key=cfg["secret_key"],
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    def save_to_s3(self) -> None:
        """Persist current state as JSON in the S3/R2 bucket if configured."""
        cfg = self._get_s3_config()
        if not cfg:
            return
        payload = {
            "next_id": self.next_id,
            "next_movement_id": self.next_movement_id,
            "products": self.products,
            "movements": self.movements,
        }
        try:
            client = self._create_s3_client(cfg)
            client.put_object(
                Bucket=cfg["bucket"],
                Key=S3_STATE_KEY,
                Body=json.dumps(payload).encode("utf-8"),
                ContentType="application/json",
            )
        except (BotoCoreError, ClientError, Exception):
            pass

    def load_from_s3(self) -> None:
        """Load persisted state from the S3/R2 bucket on startup if available."""
        cfg = self._get_s3_config()
        if not cfg:
            return
        try:
            client = self._create_s3_client(cfg)
            response = client.get_object(Bucket=cfg["bucket"], Key=S3_STATE_KEY)
            raw_body = response["Body"].read().decode("utf-8")
            data = json.loads(raw_body)
            self.next_id = int(data.get("next_id", 1))
            self.next_movement_id = int(data.get("next_movement_id", 1))
            self.products = {
                int(k): v for k, v in data.get("products", {}).items()
            }
            self.movements = list(data.get("movements", []))
        except (BotoCoreError, ClientError, Exception):
            pass

    def reset(self) -> None:
        """Clear all data in memory and sync empty state to S3 if configured."""
        self._init_memory()
        self.save_to_s3()

    def calculate_current_stock(self, product_id: int) -> int:
        """Compute current stock dynamically from initial stock and movements."""
        product = self.products[product_id]
        stock = product["initial_stock"]
        for movement in self.movements:
            if movement["product_id"] == product_id:
                if movement["type"] == "in":
                    stock += movement["quantity"]
                elif movement["type"] == "out":
                    stock -= movement["quantity"]
        return stock

    def serialize_product(self, product_id: int) -> dict[str, Any]:
        """Return product representation including dynamically computed stock."""
        product = self.products[product_id]
        return {
            "id": product["id"],
            "code": product["code"],
            "name": product["name"],
            "initial_stock": product["initial_stock"],
            "min_threshold": product["min_threshold"],
            "current_stock": self.calculate_current_stock(product_id),
        }

    def compute_stats(self) -> dict[str, int]:
        """Compute global inventory statistics."""
        serialized_products = [self.serialize_product(pid) for pid in self.products]
        total_products = len(serialized_products)
        below_threshold = sum(
            1 for p in serialized_products if p["current_stock"] < p["min_threshold"]
        )
        total_stock = sum(p["current_stock"] for p in serialized_products)
        return {
            "total_products": total_products,
            "below_threshold": below_threshold,
            "total_stock": total_stock,
        }


store = Store()


# --- Common Contract Routes ---

@app.get("/health")
def health():
    return jsonify(
        status="ok",
        uptime_seconds=int(time.monotonic() - STARTED_AT),
    )


@app.get("/version")
def version():
    return jsonify(
        app=APP_NAME,
        version=APP_VERSION,
        commit=os.getenv("APP_COMMIT", "dev"),
        built_at=os.getenv("APP_BUILT_AT", "unknown"),
    )


@app.post("/reset")
def reset():
    store.reset()
    return "", 204


@app.get("/")
def home():
    commit = os.getenv("APP_COMMIT", "dev")
    return f"""<!DOCTYPE html>
<html lang="ro"><head><meta charset="utf-8"><title>{APP_NAME}</title></head>
<body>
<h1>{APP_NAME} - Gestiune de inventar</h1>
<p>Autor: Deliu Alexandru-Darius, grupa 1.1</p>
<p>Tema: 4 - Gestiune de inventar</p>
<p>Versiune: {APP_VERSION}, commit {commit}</p>
</body></html>"""


# --- Theme 4 Routes: Inventory Management ---

@app.post("/products")
def create_product():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("validation", "Request body must be a valid JSON object", 400)

    code = data.get("code")
    name = data.get("name")
    initial_stock = data.get("initial_stock")
    min_threshold = data.get("min_threshold")

    # Validate 'code': required string, between 1 and 20 characters
    if not isinstance(code, str) or not (1 <= len(code) <= MAX_CODE_LENGTH) or not code.strip():
        return error_response(
            "validation",
            f"Field 'code' is required and must be between 1 and {MAX_CODE_LENGTH} characters",
            400,
        )

    # Validate 'name': required non-empty string
    if not isinstance(name, str) or not name.strip():
        return error_response("validation", "Field 'name' is required and cannot be empty", 400)

    # Validate 'initial_stock': required integer >= 0
    if not is_valid_int(initial_stock) or initial_stock < 0:
        return error_response(
            "validation",
            "Field 'initial_stock' is required and must be an integer >= 0",
            400,
        )

    # Validate 'min_threshold': optional, defaults to P = 15
    if min_threshold is None:
        min_threshold = DEFAULT_MIN_THRESHOLD
    elif not is_valid_int(min_threshold) or min_threshold < 0:
        return error_response(
            "validation",
            "Field 'min_threshold' must be a non-negative integer",
            400,
        )

    # Check uniqueness of 'code' -> 409 Conflict
    for existing in store.products.values():
        if existing["code"] == code:
            return error_response("conflict", f"Product with code '{code}' already exists", 409)

    product_id = store.next_id
    store.next_id += 1

    store.products[product_id] = {
        "id": product_id,
        "code": code,
        "name": name,
        "initial_stock": initial_stock,
        "min_threshold": min_threshold,
    }
    store.save_to_s3()

    return jsonify(store.serialize_product(product_id)), 201


@app.get("/products")
def list_products():
    below_threshold_param = request.args.get("below_threshold")

    products_list = [store.serialize_product(pid) for pid in store.products]

    # Filter strictly below threshold: current_stock < min_threshold
    if below_threshold_param is not None and below_threshold_param.lower() == "true":
        products_list = [
            p for p in products_list if p["current_stock"] < p["min_threshold"]
        ]

    # Sort ascending by 'code', tie-break ascending by 'id'
    products_list.sort(key=lambda p: (p["code"], p["id"]))
    return jsonify(products_list), 200


@app.get("/products/<int:product_id>")
def get_product(product_id: int):
    if product_id not in store.products:
        return error_response("not_found", f"Product with id {product_id} was not found", 404)

    return jsonify(store.serialize_product(product_id)), 200


@app.post("/movements")
def create_movement():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("validation", "Request body must be a valid JSON object", 400)

    product_id = data.get("product_id")
    movement_type = data.get("type")
    quantity = data.get("quantity")

    # Validate fields
    if not is_valid_int(product_id):
        return error_response("validation", "Field 'product_id' must be an integer", 400)

    if movement_type not in ("in", "out"):
        return error_response("validation", "Field 'type' must be 'in' or 'out'", 400)

    if not is_valid_int(quantity) or quantity <= 0:
        return error_response(
            "validation",
            "Field 'quantity' must be a strictly positive integer",
            400,
        )

    # Check if target product exists -> 404 Not Found
    if product_id not in store.products:
        return error_response("not_found", f"Product with id {product_id} does not exist", 404)

    # Check stock availability for 'out' movements -> 409 Conflict
    current_stock = store.calculate_current_stock(product_id)
    if movement_type == "out" and quantity > current_stock:
        return error_response(
            "conflict",
            f"Insufficient stock: requested {quantity}, available {current_stock}",
            409,
        )

    movement_id = store.next_movement_id
    store.next_movement_id += 1

    movement = {
        "id": movement_id,
        "product_id": product_id,
        "type": movement_type,
        "quantity": quantity,
    }
    store.movements.append(movement)
    store.save_to_s3()

    return jsonify(movement), 201


@app.get("/stats")
def get_stats():
    return jsonify(store.compute_stats()), 200


# --- Optional Extension: Protected Administrative Route ---

@app.get("/admin/stats")
def admin_stats():
    admin_user = os.getenv("ADMIN_USER")
    admin_password = os.getenv("ADMIN_PASSWORD")

    if not admin_user or not admin_password:
        return error_response("unauthorized", "Admin credentials are not configured", 401)

    auth = request.authorization
    if (
        auth is None
        or auth.type != "basic"
        or not secrets.compare_digest(auth.username or "", admin_user)
        or not secrets.compare_digest(auth.password or "", admin_password)
    ):
        return error_response("unauthorized", "Invalid or missing credentials", 401)

    return jsonify(store.compute_stats()), 200


@app.errorhandler(404)
def not_found(_):
    return error_response("not_found", "route does not exist", 404)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)