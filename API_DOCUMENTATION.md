# 📚 API Documentation

Base URL: `http://localhost:8000`

This document provides a comprehensive reference for the Digital Marketplace API. All requests should be made to the API Gateway on port **8000**.

## 🛡️ Authentication Flow

1.  **Register** a new user via `POST /api/auth/register`.
2.  **Login** via `POST /api/auth/login` to receive an `access_token` (JWT).
3.  **Use Token**: Include the token in the `Authorization` header for all protected endpoints.
    ```http
    Authorization: Bearer <access_token>
    ```
4.  **Expiration**: Tokens are valid for 30 minutes. Re-login to get a new token.

---

## 🏗️ Common Error Responses

| Status Code | Description | Body Structure |
|-------------|-------------|----------------|
| `400` | Bad Request | `{"detail": "Error message"}` |
| `401` | Unauthorized | `{"detail": "Not authenticated"}` or `{"detail": "Invalid token"}` |
| `404` | Not Found | `{"detail": "Resource not found"}` |
| `500` | Internal Error | `{"detail": "Internal server error"}` |

---

## 1. Auth Service

**Prefix**: `/api/auth`

### Register User
Create a new user account.
- **POST** `/api/auth/register`
- **Auth**: No
- **Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "strongpassword",
    "full_name": "John Doe",
    "role": "user" 
  }
  ```
- **Response** `201 Created`:
  ```json
  {
    "success": true,
    "data": { "id": "uuid...", "email": "...", "role": "user", ... }
  }
  ```

### Login
Authenticate user and get JWT.
- **POST** `/api/auth/login`
- **Auth**: No
- **Content-Type**: `application/x-www-form-urlencoded`
- **Body**:
  - `username`: Email address
  - `password`: Password
- **Response** `200 OK`:
  ```json
  {
    "access_token": "eyJhbG...",
    "token_type": "bearer"
  }
  ```

### Get Current User profile
- **GET** `/api/auth/users/me`
- **Auth**: Yes
- **Response** `200 OK`: User profile object.

---

## 2. Products Service

**Prefix**: `/api/products`

### List Products
Get a list of all active products with pagination and filtering.
- **GET** `/api/products`
- **Auth**: No
- **Query Params**:
  - `page` (int, default 1)
  - `limit` (int, default 10)
  - `category` (string, optional)
  - `min_price` (decimal, optional)
  - `max_price` (decimal, optional)
  - `search` (string, optional)
- **Response** `200 OK`:
  ```json
  {
    "success": true,
    "data": {
      "products": [ { "id": "...", "name": "Product A", "price": 99.99, ... } ],
      "total": 50,
      "page": 1,
      "limit": 10
    }
  }
  ```

### Get Product
- **GET** `/api/products/{id}`
- **Auth**: No
- **Response** `200 OK`: Single product details.

### Create Product (Vendor)
- **POST** `/api/products`
- **Auth**: Yes (Role: `vendor`)
- **Body**:
  ```json
  {
    "name": "New Product",
    "description": "Awesome item",
    "price": 29.99,
    "category": "electronics",
    "stock": 100,
    "image_url": "http://..."
  }
  ```

---

## 3. Orders Service

**Prefix**: `/api` (See specific routes below)

### Get Cart
- **GET** `/api/cart`
- **Auth**: Yes
- **Response** `200 OK`:
  ```json
  {
    "success": true,
    "data": {
      "user_id": "...",
      "items": [
        { "product_id": "...", "quantity": 2, "price": 10.00, "name": "Item" }
      ],
      "total": 20.00
    }
  }
  ```

### Add Item to Cart
- **POST** `/api/cart/items`
- **Auth**: Yes
- **Body**:
  ```json
  { "product_id": "product_uid", "quantity": 1 }
  ```

### Create Order
Convert current cart into an order.
- **POST** `/api/orders`
- **Auth**: Yes
- **Body**: Empty (uses cart)
- **Response** `200 OK`:
  ```json
  {
    "success": true,
    "data": {
      "id": "order_uid",
      "status": "pending",
      "total_amount": 20.00,
      "items": [...]
    }
  }
  ```

### List Orders
- **GET** `/api/orders`
- **Auth**: Yes
- **Response** `200 OK`: List of user orders.

### Cancel Order
- **PUT** `/api/orders/{id}/cancel`
- **Auth**: Yes
- **Description**: Can only cancel `pending` orders.

---

## 4. Payments Service

**Prefix**: `/api/payments`

### Process Payment
Simulate a payment for an order.
- **POST** `/api/payments/process`
- **Auth**: Yes
- **Body**:
  ```json
  {
    "order_id": "order_uid",
    "payment_method": "credit_card",
    "card_details": { "number": "1234..." } 
  }
  ```
- **Response** `200 OK`:
  ```json
  {
    "success": true,
    "data": {
      "id": "payment_uid",
      "status": "completed",
      "transaction_id": "uuid...",
      ...
    }
  }
  ```
  *(Note: 10% chance of failure "failed" status)*

### Get Payment by Order
- **GET** `/api/payments/order/{order_id}`
- **Auth**: Yes

---

## 📦 Data Schema (Simplified)

### User
```json
{
  "id": "string (object_id)",
  "email": "string",
  "role": "user | vendor | admin"
}
```

### Product
```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "price": "decimal",
  "category": "string",
  "stock": "integer",
  "is_active": "boolean"
}
```

### Order
```json
{
  "id": "string",
  "user_id": "string",
  "items": [ { "product_id": "", "quantity": 1, "price": 0 } ],
  "total_amount": "decimal",
  "status": "pending | completed | cancelled",
  "payment_id": "string (optional)",
  "created_at": "datetime"
}
```
