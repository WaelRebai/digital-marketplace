# 🚀 Deployment Guide

This document outlines the steps and best practices for deploying the Digital Marketplace platform to a production environment.

---

## 1. 🛡️ Production Considerations

Before deploying, ensure the following security and configuration measures are in place:

### Security Hardening
- **JWT Secret**: Generate a cryptographically strong random string (e.g., `openssl rand -hex 32`) for `JWT_SECRET`. Never use default values in production.
- **Environment Variables**: Do not hardcode secrets. Use a `.env` file or your cloud provider's secret manager.
- **MongoDB Auth**: Ensure MongoDB runs with authentication enabled (already configured) and use a complex password for the `admin` user.
- **CORS**: In `api-gateway/app/main.py`, restrict `allow_origins` to your specific frontend domains instead of `["*"]`.
- **Non-Root Users**: Ensure all Dockerfiles run as non-root users (already implemented).

### Rate Limiting & Logging
- **Rate Limiting**: Adjust `slowapi` limits in API Gateway based on expected traffic (currently 100/min).
- **Logging**: Configure services to output structured JSON logs for easier parsing by monitoring tools.

---

## 2. 🐳 Docker Compose for Production

For production, use a `docker-compose.prod.yml` that overrides the base configuration:

```yaml
version: '3.8'

services:
  # Hide backend services from the host network
  auth-service:
    ports: [] # Do not expose 8001 to host
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
    restart: always

  products-service:
    ports: []
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
    restart: always

  orders-service:
    ports: []
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
    restart: always

  payments-service:
    ports: []
    deploy:
      resources:
        limits:
          cpus: '0.50'
          memory: 512M
    restart: always

  # Only expose the API Gateway
  api-gateway:
    ports:
      - "80:8000" # Map host port 80 to container 8000
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
    restart: always
```

**Run with:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## 3. ☁️ Cloud Deployment Options

### AWS (ECS/Fargate)
1.  Push images to **Amazon ECR**.
2.  Create **Task Definitions** for each service.
3.  Use **ECS Fargate** for serverless container execution.
4.  Configure **Application Load Balancer (ALB)** to route traffic to the API Gateway.
5.  Use **DocumentDB** or a managed **MongoDB Atlas** cluster instead of a self-hosted container.

### Google Cloud Run
1.  Push images to **Google Container Registry (GCR)**.
2.  Deploy each service (Auth, Products, etc.) as a Cloud Run service.
3.  **Important**: Cloud Run services are publicly accessible by default. Configure **IAM** to only allow the API Gateway to invoke backend services, or use a VPC Connector.
4.  Use **MongoDB Atlas** for data.

### Azure Container Instances (ACI)
1.  Push images to **Azure Container Registry (ACR)**.
2.  Deploy a **Container Group** containing all services (suitable for lower traffic) or use **AKS (Azure Kubernetes Service)** for scale.

---

## 4. 📊 Monitoring & Observability

### Health Checks
All services implement a `/health` endpoint. Configure your load balancer or orchestration tool (K8s/Swarm) to poll these endpoints every 30 seconds.

### Centralized Logging
- Use **ELK Stack** (Elasticsearch, Logstash, Kibana) or **Grafana Loki**.
- Configure Docker log driver to send logs to the central collector:
  ```yaml
  logging:
    driver: "json-file"
    options:
      max-size: "10m"
      max-file: "3"
  ```

### Metrics
- Integrate **Prometheus** client in FastAPI applications to export metrics (request count, latency).
- Use **Grafana** to visualize these metrics.

---

## 5. 💾 Backup Strategy

### MongoDB Backup
1.  **Automated Daily Backups**:
    Use a cron job to run `mongodump`:
    ```bash
    docker exec mongodb mongodump --uri="mongodb://admin:password123@localhost:27017" --archive | gzip > backup_$(date +%F).gz
    ```
2.  **Offsite Storage**: Upload the `.gz` file to AWS S3 or Google Cloud Storage immediately.

### Disaster Recovery
- Test restoration procedures monthly using `mongorestore`.
- Keep backup credentials secure and separate from production keys.

---

## 6. 🔄 CI/CD Pipeline

Example **GitHub Actions** Workflow (`.github/workflows/deploy.yml`):

```yaml
name: CI/CD

on:
  push:
    branches: [ main ]

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install Dependencies
        run: |
          pip install -r services/auth-service/requirements.txt
          # Install other services requirements...
          
      - name: Run Tests
        run: |
          # run pytest commands here
          echo "Tests passed"

  deploy:
    needs: build-and-test
    runs-on: ubuntu-latest
    steps:
      - name: Build and Push Docker Images
        run: |
          docker build -t myregistry/auth-service ./services/auth-service
          docker push myregistry/auth-service
          # Repeat for all services...
          
      - name: Deploy to Server
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.HOST }}
          username: ${{ secrets.USERNAME }}
          key: ${{ secrets.KEY }}
          script: |
            cd /app/digital-marketplace
            git pull
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## 7. 📈 Scaling Considerations

- **Horizontal Scaling**: The microservices are stateless. You can run multiple replicas of `products-service` or `orders-service` behind the API Gateway (or an internal load balancer) to handle increased load.
- **Database**: Use **MongoDB Replica Sets** for high availability and read scaling.
- **Caching**: Implement **Redis** for the Products Service to cache frequent queries (e.g., `GET /products`).
- **CDN**: Serve static assets (product images) via a CDN (Cloudflare, AWS CloudFront) to reduce server load.
