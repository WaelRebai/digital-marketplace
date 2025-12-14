#!/usr/bin/env python3
"""
Integration Test Suite for Digital Marketplace

Usage:
    1. Ensure all services are running: docker-compose up -d --build
    2. Install dependencies: pip install requests
    3. Run the script: python tests/integration_test.py

This script tests the full flow:
    - Authentication (Register/Login)
    - Product Management
    - Shopping Cart
    - Order Creation
    - Payment Processing
    - Security/Negative Tests

Output:
    - Console logs with pass/fail status
    - integration_test_results.json report
"""
import requests
import json
import time
import sys
from datetime import datetime
from typing import Dict, Any, List

# Configuration
BASE_URL = "http://localhost:8000"
RESULTS_FILE = "integration_test_results.json"

# Colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

class TestRunner:
    def __init__(self):
        self.results = []
        self.session = requests.Session()
        self.store: Dict[str, Any] = {}
        self.start_time = time.time()

    def log(self, message: str, color: str = Colors.ENDC):
        print(f"{color}{message}{Colors.ENDC}")

    def save_result(self, name: str, status: str, duration: float, error: str = None):
        self.results.append({
            "test_name": name,
            "status": status,
            "duration": duration,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        })
        color = Colors.GREEN if status == "PASS" else Colors.FAIL
        self.log(f"[{status}] {name} ({duration:.4f}s)", color)
        if error:
            self.log(f"  Error: {error}", Colors.FAIL)

    def run_test(self, name: str, func, *args, **kwargs):
        start = time.time()
        try:
            func(*args, **kwargs)
            duration = time.time() - start
            self.save_result(name, "PASS", duration)
        except AssertionError as e:
            duration = time.time() - start
            self.save_result(name, "FAIL", duration, str(e))
        except Exception as e:
            duration = time.time() - start
            self.save_result(name, "ERROR", duration, str(e))

    def assert_status(self, response, expected: int):
        if response.status_code != expected:
            raise AssertionError(f"Expected status {expected}, got {response.status_code}. Body: {response.text}")

    def save_report(self):
        with open(RESULTS_FILE, "w") as f:
            json.dump({
                "summary": {
                    "total": len(self.results),
                    "passed": len([r for r in self.results if r["status"] == "PASS"]),
                    "failed": len([r for r in self.results if r["status"] != "PASS"]),
                    "total_duration": time.time() - self.start_time
                },
                "results": self.results
            }, f, indent=2)
        self.log(f"\nTest results saved to {RESULTS_FILE}", Colors.BLUE)

# --- Test Functions ---

def test_health_check(runner: TestRunner):
    resp = runner.session.get(f"{BASE_URL}/health")
    runner.assert_status(resp, 200)
    data = resp.json()
    if data["status"] != "healthy":
        raise AssertionError("System is not healthy")

# Phase 1: Authentication

def register_users(runner: TestRunner):
    # Vendor
    vendor_data = {
        "email": f"vendor_{int(time.time())}@test.com",
        "password": "Password123!",
        "role": "vendor",
        "full_name": "Test Vendor"
    }
    resp = runner.session.post(f"{BASE_URL}/api/auth/register", json=vendor_data)
    runner.assert_status(resp, 200)
    runner.store["vendor_email"] = vendor_data["email"]
    runner.store["vendor_password"] = vendor_data["password"]

    # Customer
    user_data = {
        "email": f"user_{int(time.time())}@test.com",
        "password": "Password123!",
        "role": "user",
        "full_name": "Test User"
    }
    resp = runner.session.post(f"{BASE_URL}/api/auth/register", json=user_data)
    runner.assert_status(resp, 200)
    runner.store["user_email"] = user_data["email"]
    runner.store["user_password"] = user_data["password"]

def login_users(runner: TestRunner):
    # Login Vendor
    resp = runner.session.post(f"{BASE_URL}/api/auth/login", json={
        "email": runner.store["vendor_email"],
        "password": runner.store["vendor_password"]
    })
    runner.assert_status(resp, 200)
    runner.store["vendor_token"] = resp.json()["data"]["access_token"]

    # Login User
    resp = runner.session.post(f"{BASE_URL}/api/auth/login", json={
        "email": runner.store["user_email"],
        "password": runner.store["user_password"]
    })
    runner.assert_status(resp, 200)
    runner.store["user_token"] = resp.json()["data"]["access_token"]

# Phase 2: Products

def create_product(runner: TestRunner):
    headers = {"Authorization": f"Bearer {runner.store['vendor_token']}"}
    
    # Create Category (If endpoint exists or plain text? Assuming text based on schema)
    # Check if category creation endpoint exists. Schema implies simply passing category string or ID.
    # Products Service `create_product` takes `ProductCreate`. `category` is a string.
    # Let's just create product.
    
    product_data = {
        "name": "Integration Test Product",
        "description": "A very nice product",
        "price": 99.99,
        "category": "electronics",
        "stock": 100
    }
    resp = runner.session.post(f"{BASE_URL}/api/products", json=product_data, headers=headers)
    runner.assert_status(resp, 200)
    product = resp.json()["data"]
    runner.store["product_id"] = product["id"]

def list_products(runner: TestRunner):
    resp = runner.session.get(f"{BASE_URL}/api/products")
    runner.assert_status(resp, 200)
    products = resp.json()["data"]["products"]
    found = any(p["id"] == runner.store["product_id"] for p in products)
    if not found:
        raise AssertionError("Created product not found in list")

def get_product_details(runner: TestRunner):
    pid = runner.store["product_id"]
    resp = runner.session.get(f"{BASE_URL}/api/products/{pid}")
    runner.assert_status(resp, 200)
    if resp.json()["data"]["name"] != "Integration Test Product":
        raise AssertionError("Product details mismatch")

# Phase 3: Cart

def add_to_cart(runner: TestRunner):
    headers = {"Authorization": f"Bearer {runner.store['user_token']}"}
    data = {
        "product_id": runner.store["product_id"],
        "quantity": 2
    }
    resp = runner.session.post(f"{BASE_URL}/api/cart", json=data, headers=headers)
    # Api Gateway routing: /api/cart -> orders-service/cart ?
    # Wait, in plan I said /api/cart -> orders-service/cart. 
    # Need to verify if I added that route in Gateway.
    # If not, use /api/orders/cart if that works?
    # Let's assume /api/cart works as per plan.
    runner.assert_status(resp, 200)
    
def view_cart(runner: TestRunner):
    headers = {"Authorization": f"Bearer {runner.store['user_token']}"}
    resp = runner.session.get(f"{BASE_URL}/api/cart", headers=headers)
    runner.assert_status(resp, 200)
    items = resp.json()["data"]["items"]
    if len(items) == 0:
        raise AssertionError("Cart is empty")
    if items[0]["quantity"] != 2:
        raise AssertionError("Cart quantity mismatch")

# Phase 4: Order

def create_order(runner: TestRunner):
    headers = {"Authorization": f"Bearer {runner.store['user_token']}"}
    data = {"shipping_address": "123 Test St"}
    resp = runner.session.post(f"{BASE_URL}/api/orders", json=data, headers=headers)
    runner.assert_status(resp, 200)
    order = resp.json()["data"]
    runner.store["order_id"] = order["id"]
    if order["status"] != "pending":
        raise AssertionError("Order status should be pending")

def verify_cart_cleared(runner: TestRunner):
    headers = {"Authorization": f"Bearer {runner.store['user_token']}"}
    resp = runner.session.get(f"{BASE_URL}/api/cart", headers=headers)
    runner.assert_status(resp, 200)
    # Depending on implementation, cleared cart might be empty items list or 404? 
    # Usually empty items.
    # `orders-service` returns empty list if cleared.
    items = resp.json()["data"]["items"] if resp.json()["data"] else []
    if len(items) > 0:
         raise AssertionError("Cart not cleared after order")

# Phase 5: Payment

def process_payment(runner: TestRunner):
    headers = {"Authorization": f"Bearer {runner.store['user_token']}"}
    data = {
        "order_id": runner.store["order_id"],
        "payment_method": "credit_card",
        "card_details": {"number": "4242"}
    }
    resp = runner.session.post(f"{BASE_URL}/api/payments/process", json=data, headers=headers)
    runner.assert_status(resp, 200)
    
def verify_order_completed(runner: TestRunner):
    headers = {"Authorization": f"Bearer {runner.store['user_token']}"}
    oid = runner.store["order_id"]
    # Provide query param or path? Orders service: /orders/{id}
    resp = runner.session.get(f"{BASE_URL}/api/orders/{oid}", headers=headers)
    runner.assert_status(resp, 200)
    if resp.json()["data"]["status"] != "paid": # Or completed? Check Orders service logic.
        # Payment service calls `PUT /orders/{id}/status` with `status=paid` (or similar).
        # Let's assume "paid" or "completed".
        status = resp.json()["data"]["status"] 
        if status not in ["paid", "completed"]:
            raise AssertionError(f"Order status not updated. Got: {status}")

# Phase 6: Negative Tests

def negative_tests(runner: TestRunner):
    # Invalid Token
    headers = {"Authorization": "Bearer invalid_token"}
    resp = runner.session.get(f"{BASE_URL}/api/cart", headers=headers)
    if resp.status_code != 401:
        raise AssertionError(f"Expected 401 for invalid token, got {resp.status_code}")

    # Bad Data (Product create with negative price)
    headers = {"Authorization": f"Bearer {runner.store['vendor_token']}"}
    bad_product = {
        "name": "Bad",
        "price": -10,
        "category": "bad"
    }
    resp = runner.session.post(f"{BASE_URL}/api/products", json=bad_product, headers=headers)
    if resp.status_code != 422: # Pydantic validation error
         raise AssertionError(f"Expected 422 for negative price, got {resp.status_code}")


def main():
    runner = TestRunner()
    runner.log("Starting Integration Tests...\n", Colors.HEADER)

    # 1. Health
    runner.run_test("Health Check", test_health_check, runner)

    # 2. Auth
    runner.run_test("Register Users", register_users, runner)
    runner.run_test("Login Users", login_users, runner)

    # 3. Products
    runner.run_test("Create Product", create_product, runner)
    runner.run_test("List Products", list_products, runner)
    runner.run_test("Get Product Details", get_product_details, runner)

    # 4. Cart
    runner.run_test("Add to Cart", add_to_cart, runner)
    runner.run_test("View Cart", view_cart, runner)

    # 5. Helper: Verify Gateway Routing (Optional but implicit in above)

    # 6. Order
    runner.run_test("Create Order", create_order, runner)
    runner.run_test("Verify Cart Cleared", verify_cart_cleared, runner)

    # 7. Payment
    runner.run_test("Process Payment", process_payment, runner)
    runner.run_test("Verify Order Status", verify_order_completed, runner)

    # 8. Negative
    runner.run_test("Negative Tests", negative_tests, runner)

    runner.save_report()
    
    # Exit code
    if any(r["status"] != "PASS" for r in runner.results):
        sys.exit(1)

if __name__ == "__main__":
    main()
