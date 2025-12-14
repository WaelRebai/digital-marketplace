# 🧠 Learning Guide

Welcome to the **Digital Marketplace Learning Guide**! This document explains the core concepts, technologies, and patterns used in this project. It is designed to help you understand *why* things were built this way and *how* they work under the hood.

---

## 1. 🔑 Key Concepts Explained

### 🏗️ Service-Oriented Architecture (SOA) & Microservices
Instead of building one giant application (Monolith) where all logic sits together, we split the application into small, independent services.
- **Microservices**: Each service (Auth, Products, Orders) runs in its own process (container) and manages its own database.
- **Independence**: If the *Orders Service* crashes, users can still browse products.
- **Scalability**: If traffic spikes, we can run 5 copies of the *Products Service* while keeping only 1 *Auth Service*.

### 🌐 API Gateway Pattern
The **API Gateway** (running on port 8000) acts as the "front door".
- **Without Gateway**: Frontend needs to know `auth:8001`, `products:8002`, `orders:8003`.
- **With Gateway**: Frontend only knows `localhost:8000`. The Gateway routes `/api/auth` to port 8001, `/api/products` to 8002, etc. It also handles **security** (verifying tokens) and **rate limiting**.

### 🔐 JWT Authentication Flow
1. **Login**: User sends credentials to Auth Service.
2. **Issue**: Auth Service validates and signs a JSON Web Token (JWT) with a secret key.
3. **Carry**: The user keeps this token and sends it in the header (`Authorization: Bearer <token>`) for every request.
4. **Verify**: The API Gateway (or other services) checks the signature. If valid, they know who the user is without asking the database every time.

---

## 2. 🛠️ Technology Deep Dive

### ⚡ FastAPI
A modern, high-performance web framework for Python.
- **Async/Await**: Built on `Starlette`, it handles many requests at once using non-blocking I/O.
- **Pydantic**: Uses Python type hints for data validation. If you send a string where an integer is expected, FastAPI rejects it automatically.

### 🍃 MongoDB (NoSQL)
A document database that stores data as JSON-like documents.
- **Flexibility**: We don't need to define strict tables like SQL. A `Product` document can have different fields than an `Order`.
- **Scalability**: Excellent for high-volume read/write operations common in e-commerce.

### 🐳 Docker & Networking
- **Containerization**: Packages the app and all its libraries into an "Image". It runs exactly the same on your laptop and the server.
- **Networking**: In `docker-compose.yml`, we define a `marketplace-network`. Services refer to each other by name (e.g., `http://auth-service:8001`). Docker's internal DNS handles the routing.

---

## 3. 🔍 Code Walkthrough

### Auth Service (`services/auth-service`)
- **`schemas.py`**: Defines what data we expect (e.g., `UserRegister`).
- **`models.py`**: Defines how data looks in MongoDB.
- **`main.py` -> `create_access_token`**: Uses `python-jose` to create the JWT. It encodes the `user_id` and an expiration time.

### Inter-Service Communication
When **Orders Service** creates an order, it needs product prices. It cannot read the Products DB directly (that breaks microservice rules!).
- **How**: It uses `httpx` (an HTTP client) to call `GET http://products-service:8002/products/{id}`.
- **Why**: This ensures the Products Service is the *only* source of truth for product data.

### Database Connection (`shared/utils.py`)
We use a singleton pattern for the `AsyncIOMotorClient`.
- **Startup**: Connection opens when the app starts (`@app.on_event("startup")`).
- **Shutdown**: Connection closes when the app stops.
- **Shared logic**: We placed this in `shared/` to reuse code across all 5 services, avoiding duplication.

---

## 4. ✅ Best Practices Implemented

- **Error Standardization**: All errors return `{"detail": "Message"}`. This makes it easy for the frontend to handle errors consistently.
- **Dependency Injection**: FastAPI's `Depends` allows us to inject logic (like `get_current_user`) into endpoints cleanly.
- **Environment Variables**: Configuration (DB URLs, Secrets) is read from `os.getenv`, allowing different configs for Dev vs Prod.
- **Health Checks**: Every Docker service has a `HEALTHCHECK` command. The Gateway waits for services to be "healthy" before starting.

---

## 5. 🔧 Troubleshooting Guide

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| **Connection Refused** | Service didn't start yet. | Check `docker-compose logs <service>`. Wait for health checks. |
| **401 Unauthorized** | Token expired or invalid. | Login again to get a fresh token. Check if `JWT_SECRET` matches across services. |
| **Product Not Found** | ID mismatch. | Use `curl http://localhost:8000/api/products` to copy a real ID. |
| **Docker Networking** | Services can't see each other. | Ensure all are on the same `networks` in `docker-compose.yml`. |

**Debugging Tip**: Use `docker-compose logs -f api-gateway` to watch requests flow in real-time.

---

## 6. 💡 Extension Ideas

Ready to level up? Try building these:

1.  **📧 Notification Service**: Listen for "Order Created" events (using RabbitMQ/Kafka) and send an email.
2.  **⭐ Review System**: Add a new service allowing users to rate products.
3.  **⚡ Redis Caching**: Cache the `GET /products` response in Redis for 1 minute to reduce DB load.
4.  **📉 Analytics**: Track mostly viewed products and sales trends.

---

## 7. 📚 Resources

- **FastAPI**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com/)
- **MongoDB**: [university.mongodb.com](https://university.mongodb.com/)
- **Docker**: [docs.docker.com/get-started/](https://docs.docker.com/get-started/)
- **Microservices Patterns**: [microservices.io](https://microservices.io/)
- **12-Factor App**: [12factor.net](https://12factor.net/) (Guide for building cloud-native apps)
