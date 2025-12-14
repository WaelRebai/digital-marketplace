# 🧪 Manual Testing Guide

Ensure all services are running before starting:
```bash
docker-compose up -d
```
**Tools:**
- `curl` (Command line)
- `jq` (Optional, for formatting JSON output)

---

## 🏗️ Scenarios & Commands

### 1. User Registration & Auth

**Register a User**
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "password": "securepass123",
    "full_name": "Alice Wonderland",
    "role": "user"
  }'
```

**Login (Get Token)**
```bash
# Save this token for subsequent requests!
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -d "username=alice@example.com&password=securepass123" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
echo "Token: $TOKEN"
```

**Register a Vendor (For Creating Products)**
```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "vendor@shop.com",
    "password": "vendorpass123",
    "full_name": "Vendor Bob",
    "role": "vendor"
  }'

VENDOR_TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -d "username=vendor@shop.com&password=vendorpass123" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
echo "Vendor Token: $VENDOR_TOKEN"
```

---

### 2. Product Management

**Create a Product (As Vendor)**
```bash
curl -X POST http://localhost:8000/api/products \
  -H "Authorization: Bearer $VENDOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Gaming Laptop",
    "description": "High performance",
    "price": 1500.00,
    "category": "electronics",
    "stock": 10
  }'
```

**List Products**
```bash
curl "http://localhost:8000/api/products?limit=5"
```
*Note the `id` of the created product for next steps.*

**Search Products**
```bash
curl "http://localhost:8000/api/products?search=Laptop"
```

---

### 3. Shopping Cart

**Add to Cart**
*Replace `PRODUCT_ID` with the ID from previous step.*
```bash
PRODUCT_ID="<REPLACE_WITH_PRODUCT_ID>"

curl -X POST http://localhost:8000/api/cart/items \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"product_id\": \"$PRODUCT_ID\", \"quantity\": 1}"
```

**View Cart**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/cart
```

---

### 4. Order Creation

**Checkout (Create Order)**
```bash
curl -X POST http://localhost:8000/api/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Length: 0"
```
*Note the `id` from the response.*

**List Orders**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/orders
```

---

### 5. Payment Processing

**Process Payment**
*Replace `ORDER_ID` with the ID from previous step.*
```bash
ORDER_ID="<REPLACE_WITH_ORDER_ID>"

curl -X POST http://localhost:8000/api/payments/process \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"order_id\": \"$ORDER_ID\",
    \"payment_method\": \"credit_card\",
    \"card_details\": {\"number\": \"4242424242424242\"}
  }"
```

**Verify Order Status**
```bash
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/orders/$ORDER_ID"
```
*Status should be `completed` (90% chance) or `cancelled`.*

---

## 🤖 Automated Testing Script

Save the following as `test_e2e.py` and run with `python test_e2e.py`.
Requires `requests`: `pip install requests`.

```python
import requests
import sys

BASE_URL = "http://localhost:8000"

def log(msg):
    print(f"[TEST] {msg}")

def check(response, code=200):
    if response.status_code != code:
        print(f"FAILED: Expected {code}, got {response.status_code}")
        print(response.text)
        sys.exit(1)
    return response.json()

# 1. Register User
log("Registering User...")
email = "auto_user_5@example.com"
r = requests.post(f"{BASE_URL}/api/auth/register", json={
    "email": email, "password": "pass", "full_name": "Auto", "role": "user"
})
if r.status_code == 400: # Assuming duplicate
    log("User exists, logging in...")
else:
    check(r, 201)

# 2. Login
log("Logging in...")
r = requests.post(f"{BASE_URL}/api/auth/login", data={"username": email, "password": "pass"})
token = check(r)["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 3. Register Vendor
log("Registering Vendor...")
vendor_email = "auto_vendor_5@example.com"
requests.post(f"{BASE_URL}/api/auth/register", json={
    "email": vendor_email, "password": "pass", "full_name": "Vendor", "role": "vendor"
})
r = requests.post(f"{BASE_URL}/api/auth/login", data={"username": vendor_email, "password": "pass"})
vendor_token = check(r)["access_token"]
v_headers = {"Authorization": f"Bearer {vendor_token}"}

# 4. Create Product
log("Creating Product...")
r = requests.post(f"{BASE_URL}/api/products", headers=v_headers, json={
    "name": "Auto Product", "description": "Test", "price": 100.0, "category": "test", "stock": 50
})
product_id = check(r)["data"]["id"]

# 5. Add to Cart
log("Adding to Cart...")
check(requests.post(f"{BASE_URL}/api/cart/items", headers=headers, json={
    "product_id": product_id, "quantity": 2
}))

# 6. Create Order
log("Creating Order...")
order_data = check(requests.post(f"{BASE_URL}/api/orders", headers=headers))["data"]
order_id = order_data["id"]
log(f"Order Created: {order_id}")

# 7. Process Payment
log("Processing Payment...")
pay_res = check(requests.post(f"{BASE_URL}/api/payments/process", headers=headers, json={
    "order_id": order_id, "payment_method": "credit_card", "card_details": {}
}))
log(f"Payment Status: {pay_res['data']['status']}")

log("✅ E2E Test Completed Successfully!")
```
