# 🛒 Digital Marketplace E-Commerce Platform

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.0-009688.svg)
![MongoDB](https://img.shields.io/badge/MongoDB-7.0-47A248.svg)
![Docker](https://img.shields.io/badge/Docker-24.0+-2496ED.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

A scalable, microservices-based e-commerce platform built with modern technologies. This project demonstrates a clean Server-Oriented Architecture (SOA) using **FastAPI** for high-performance services, **MongoDB** for flexible data storage, and **Docker** for containerization and orchestration.

## 🏗️ Architecture Overview

The platform is composed of 5 microservices, orchestrated via an API Gateway. Each service handles a specific domain logic and communicates via REST APIs.

### Service Breakdown
| Service | Port | Description |
|---------|------|-------------|
| **API Gateway** | `8000` | Unified entry point, routing, logging, rate limiting, and auth header injection. |
| **Auth Service** | `8001` | User registration, authentication (JWT), and profile management. |
| **Products Service** | `8002` | Product catalog, categories, inventory management, and search. |
| **Orders Service** | `8003` | Shopping cart management and order lifecycle processing. |
| **Payments Service** | `8004` | Payment processing simulation and status updates. |

### Communication Flow
1. **Client** sends request to **API Gateway**.
2. **Gateway** verifies JWT token with **Auth Service**.
3. **Gateway** logs request and routes to target (e.g., **Orders Service**).
4. **Orders Service** may call **Products Service** (synchronous HTTP via `httpx`) to validate stock.
5. Response flows back through Gateway to Client.

---

## ✨ Features

- **🔐 Authentication & Authorization**: Secure user registration and login using JWT (JSON Web Tokens). Role-based access (User/Vendor/Admin).
- **📦 Product Management**: Create, update, view, and search products. Stock tracking and categorization.
- **🛒 Shopping Cart**: Persistent shopping cart for users. Add/remove items with real-time price snapshots.
- **📦 Order Processing**: Convert cart to orders. Validation of stock and product availability.
- **💳 Payment Simulation**: Realistic payment processing with random success/failure scenarios (90% success rate) and transaction logging.
- **🛡️ API Gateway**: Centralized routing, rate limiting (100 req/min), and health checks.

---

## 🛠️ Prerequisites

- **Docker** and **Docker Compose** installed.
- **Git** for version control.
- (Optional) **MongoDB Compass** for database inspection.
- (Optional) **Postman** or **curl** for API testing.

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/digital-marketplace.git
cd digital-marketplace
```

### 2. Environment Setup
The project works out-of-the-box with Docker. No manual `.env` file creation is needed for the default setup (environment variables are defined in `docker-compose.yml`).


### 3. Start the Platform
**Option A: Automated Script (Recommended)**
Use the included Python script to handle port conflicts, cleanup, and verification automatically:
```bash
python kill_ports_and_start.py
```

**Option B: Manual Docker Compose**
Build and start all services in detached mode:
```bash
docker-compose up -d --build
```

### 4. Access Services
- **API Gateway (Main Entry)**: [http://localhost:8000](http://localhost:8000)
- **API Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)

Service-specific Swagger UIs (for debugging):
- Auth: [http://localhost:8001/docs](http://localhost:8001/docs)
- Products: [http://localhost:8002/docs](http://localhost:8002/docs)
- Orders: [http://localhost:8003/docs](http://localhost:8003/docs)
- Payments: [http://localhost:8004/docs](http://localhost:8004/docs)

---

## 📂 Project Structure

```text
digital-marketplace/
├── services/
│   ├── api-gateway/       # FastAPI Gateway Application
│   ├── auth-service/      # User & Auth Logic
│   ├── products-service/  # Catalog & Inventory
│   ├── orders-service/    # Cart & Order Management
│   └── payments-service/  # Payment Simulation
├── shared/                # Shared Utilities (JWT, Config, Models)
├── docker-compose.yml     # Container Orchestration
└── README.md              # Project Documentation
```

---

## 📖 API Documentation

Here are the key endpoints exposed via the API Gateway (`http://localhost:8000`):

### Auth Service
- `POST /api/auth/register`: Register a new user.
- `POST /api/auth/login`: Login and receive access token.
- `GET /api/auth/users/me`: Get current user profile (Protected).

### Products Service
- `GET /api/products`: List products (pagination, filtering, search).
- `GET /api/products/{id}`: Get product details.
- `POST /api/products`: Create a product (Vendor only).

### Orders Service
- `GET /api/cart`: Get current user's cart.
- `POST /api/cart/items`: Add item to cart.
- `POST /api/orders`: Create an order from current cart.
- `GET /api/orders`: List user orders.

### Payments Service
- `POST /api/payments/process`: Process payment for an order.
- `GET /api/payments/user`: Get user payment history.

---

## 🧪 Testing Flow (Step-by-Step)

Follow this journey to test the full system:

1.  **Register User**:
    ```bash
    curl -X POST http://localhost:8000/api/auth/register \
      -H "Content-Type: application/json" \
      -d '{"email": "test@example.com", "password": "password123", "full_name": "Test User", "role": "user"}'
    ```

2.  **Login**:
    ```bash
    curl -X POST http://localhost:8000/api/auth/login \
      -H "Content-Type: application/x-www-form-urlencoded" \
      -d "username=test@example.com&password=password123"
    ```
    *Copy the `access_token` from the response.*

3.  **Browse Products** (Assuming products exist):
    ```bash
    curl http://localhost:8000/api/products
    ```

4.  **Add to Cart**:
    ```bash
    curl -X POST http://localhost:8000/api/cart/items \
      -H "Authorization: Bearer <YOUR_TOKEN>" \
      -H "Content-Type: application/json" \
      -d '{"product_id": "<PRODUCT_ID>", "quantity": 1}'
    ```

5.  **Create Order**:
    ```bash
    curl -X POST http://localhost:8000/api/orders \
      -H "Authorization: Bearer <YOUR_TOKEN>" \
      -H "Content-Length: 0"
    ```

6.  **Process Payment**:
    ```bash
    curl -X POST http://localhost:8000/api/payments/process \
      -H "Authorization: Bearer <YOUR_TOKEN>" \
      -H "Content-Type: application/json" \
      -d '{"order_id": "<ORDER_ID>", "payment_method": "credit_card", "card_details": {}}'
    ```

---

## 💻 Environment Variables

Services are configured via `docker-compose.yml`. Key variables:

| Variable | Service(s) | Description |
|----------|------------|-------------|
| `MONGO_URL` | All Services | Connection string for MongoDB. |
| `JWT_SECRET` | Auth | Secret key for signing tokens. **Change in Prod!** |
| `AUTH_SERVICE_URL` | Products, Orders, Payments, Gateway | Internal URL for Auth Service. |
| `PRODUCTS_SERVICE_URL` | Orders, Gateway | Internal URL for Products Service. |
| `ORDERS_SERVICE_URL` | Payments, Gateway | Internal URL for Orders Service. |
| `PAYMENTS_SERVICE_URL` | Gateway | Internal URL for Payments Service. |

---

## 🔧 Troubleshooting

- **Port Conflicts**: Ensure ports `8000`-`8004` and `27017` are free. If not, modify `docker-compose.yml`.
- **Database Connection**: Use `docker-compose logs mongodb` to check if Mongo is healthy.
- **Service Unavailable (503)**: Check if downstream services are running: `docker ps -a`.
- **Permission Errors**: Ensure you are running Docker with appropriate permissions.

### Stopping Services
To stop all services cleanly:
```bash
python stop_marketplace.py
# Or manually:
docker-compose down
```

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
