# Digital Marketplace E-Commerce Platform

This is a microservices-based e-commerce platform built with Python (FastAPI) and MongoDB.

## Architecture

The project consists of 5 microservices:
- **Auth Service**: User authentication and management.
- **Products Service**: Product catalog and management.
- **Orders Service**: Order processing and management.
- **Payments Service**: Payment processing.
- **API Gateway**: Entry point for the frontend, routing requests to services.

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development without Docker)

## Getting Started

1. Clone the repository.
2. Build and start the services using Docker Compose:

   ```bash
   docker-compose up --build
   ```

3. The services will be available at:
   - API Gateway: http://localhost:8000
   - Auth Service: http://localhost:8001
   - Products Service: http://localhost:8002
   - Orders Service: http://localhost:8003
   - Payments Service: http://localhost:8004

## Project Structure

```
digital-marketplace/
├── services/
│   ├── auth-service/
│   ├── products-service/
│   ├── orders-service/
│   ├── payments-service/
│   └── api-gateway/
├── shared/
├── docker-compose.yml
└── README.md
```
