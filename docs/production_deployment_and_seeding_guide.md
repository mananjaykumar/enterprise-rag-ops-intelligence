# Enterprise RAG & Operations Intelligence Platform
## Production Deployment & Database Seeding Guide

This guide provides end-to-end instructions for deploying the platform into production and executing operational database seeding across various deployment models (Docker Compose on a VPS, Cloud Containers on AWS/GCP, Kubernetes, or PaaS).

---

## 1. System Architecture in Production

A complete production deployment consists of four components:

| Component | Technology | Description | Ports / Healthcheck |
|---|---|---|---|
| **Database** | PostgreSQL 16 + `pgvector` | Stores relational entities, users, audit logs, and 768-dim embeddings | Port `5432` / `pg_isready` |
| **API Server** | FastAPI + Uvicorn | Dispatches queries, handles Text-to-SQL, hybrid search, and LangGraph orchestration | Port `8000` / `/health` |
| **Ingestion Worker** | Python async worker | Consumes document processing pipeline, chunking, and embedding generation | Background daemon |
| **Web Frontend** | Next.js 16 + React 19 | Responsive dashboard for chat, query routing visualization, and document upload | Port `3000` |

---

## 2. Production Environment Configuration

Create a `.env.production` file on your production host with the required variables:

```bash
# =========================================================================
# 1. Platform Settings
# =========================================================================
ENVIRONMENT=production
DEBUG=false
PROJECT_NAME="Enterprise RAG & Operations Intelligence Platform"

# =========================================================================
# 2. Database (PostgreSQL 16 + pgvector)
# Note: Driver must be postgresql+asyncpg for SQLAlchemy async engine
# =========================================================================
POSTGRES_USER=postgres_admin
POSTGRES_PASSWORD=UseAStrongRandomPassword123!
POSTGRES_DB=enterprise_rag_prod
DATABASE_URL=postgresql+asyncpg://postgres_admin:UseAStrongRandomPassword123!@postgres:5432/enterprise_rag_prod

# =========================================================================
# 3. Model Provider (Google Gemini)
# =========================================================================
GEMINI_API_KEY=your_production_gemini_api_key_here
ACTIVE_EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSION=768

# =========================================================================
# 4. Optional Production Observability (Langfuse)
# =========================================================================
LANGFUSE_ENABLED=false
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com

# =========================================================================
# 5. Production Seeding Configuration (Overridable)
# =========================================================================
SEED_TENANT_ID=default_tenant
SEED_ADMIN_EMAIL=admin@yourcompany.com
SEED_ADMIN_PASSWORD=YourStrongAdminPassword2026!

# =========================================================================
# 6. Frontend
# =========================================================================
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

---

## 3. Deployment Method A: Docker Compose (VPS / Single Host)

This is the recommended approach for dedicated virtual servers (AWS EC2, GCP Compute Engine, DigitalOcean Droplet, Hetzner, etc.).

### Step 1: Clone Repository & Configure Environment
```bash
git clone <your-repo-url> /opt/enterprise-rag
cd /opt/enterprise-rag

# Configure your production environment secrets
cp .env.example .env.production
nano .env.production
```

### Step 2: Build and Start Core Services
```bash
# Build images and start Postgres, Backend, Worker, and Frontend
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Verify that all containers are healthy:
```bash
docker compose -f docker-compose.prod.yml ps
```

### Step 3: Run Database Seeding in Production
You can seed or reset the database at any time using one of two methods:

#### Method 1: Using the Dedicated One-off Seeder Service (Recommended)
```bash
docker compose --env-file .env.production -f docker-compose.prod.yml run --rm seed
```

#### Method 2: Executing Inside the Running Backend Container
```bash
docker compose -f docker-compose.prod.yml exec \
  -e SEED_ADMIN_EMAIL="admin@yourcompany.com" \
  -e SEED_ADMIN_PASSWORD="YourStrongAdminPassword2026!" \
  backend python3 scripts/seed_operational_data.py
```

### Step 4: Verify Seeding Output
The output will confirm successful execution:
```text
[INFO] Starting Enterprise DB Seeding for Text-to-SQL...
[INFO] Created new Admin user: admin@yourcompany.com
[INFO] Cleaning up old operational demo records for tenant default_tenant...
[INFO] Seeding completed successfully! ✅
--------------------------------------------------
Admin Credentials:
  Email:    admin@yourcompany.com
  Password: YourStrongAdminPassword2026!
  Role:     ADMIN
  Tenant:   default_tenant
--------------------------------------------------
Operational Entities Seeded:
  - Departments: 5 records
  - Employees: 11 records
  - Vendors: 6 records
  - Contracts: 5 records
  - Invoices: 11 records
  - Operational_expenses: 19 records
==================================================
```

---

## 4. Deployment Method B: Cloud Containers (AWS ECS / GCP Cloud Run / Kubernetes)

In enterprise cloud environments, each service is decoupled:

### 1. Database (AWS RDS / GCP Cloud SQL / Neon / Supabase)
Ensure the `vector` extension is active:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. Container Images
Build and push images to your container registry (Amazon ECR / Google Artifact Registry / Docker Hub):

```bash
# Backend Image (Used for API, Ingestion Worker, and Seeding Tasks)
docker build -t your-registry/enterprise-rag-backend:latest -f Dockerfile .
docker push your-registry/enterprise-rag-backend:latest

# Frontend Image
docker build -t your-registry/enterprise-rag-frontend:latest -f frontend/Dockerfile ./frontend
docker push your-registry/enterprise-rag-frontend:latest
```

### 3. Deploy Cloud Services
1. **API Service**: Run container with entrypoint `uvicorn src.main:app --host 0.0.0.0 --port 8000`.
2. **Worker Service**: Run container with command `python3 -m src.workers.ingestion_worker`.
3. **Frontend Service**: Run frontend container on port `3000` (or host directly on Vercel).

### 4. Running the Seed Script in Cloud Environments

#### Option 4.1: Kubernetes Job
Apply a one-off Kubernetes Job:
```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: enterprise-rag-db-seeder
spec:
  ttlSecondsAfterFinished: 300
  template:
    spec:
      containers:
      - name: seeder
        image: your-registry/enterprise-rag-backend:latest
        command: ["python3", "scripts/seed_operational_data.py"]
        envFrom:
        - secretRef:
            name: enterprise-rag-secrets
      restartPolicy: Never
  backoffLimit: 2
```
```bash
kubectl apply -f seeder-job.yaml
kubectl logs -f job/enterprise-rag-db-seeder
```

#### Option 4.2: AWS ECS RunTask / GCP Cloud Run Job
- **AWS ECS**: Trigger a one-time task via `aws ecs run-task --cluster prod-cluster --task-definition enterprise-rag-backend --overrides '{"containerOverrides": [{"name": "backend", "command": ["python3", "scripts/seed_operational_data.py"]}]}'`.
- **GCP Cloud Run Job**: Create a job pointing to the backend image with command `python3 scripts/seed_operational_data.py` and run `gcloud run jobs execute enterprise-rag-seeder`.

#### Option 4.3: Secure Bastion / Local Execution Against Production DB
If your cloud database is accessible via VPN or SSH bastion tunnel:
```bash
DATABASE_URL="postgresql+asyncpg://<db_user>:<db_pass>@<db_host>:5432/<db_name>" \
SEED_ADMIN_EMAIL="admin@yourcompany.com" \
SEED_ADMIN_PASSWORD="SecurePassword123!" \
.venv/bin/python scripts/seed_operational_data.py
```

---

## 5. Automated CI/CD Deployment Workflow (GitHub Actions)

In your `.github/workflows/deploy.yml`, you can add a step to run seeding automatically or via `workflow_dispatch`:

```yaml
name: Deploy Production & Run Migrations

on:
  push:
    branches: [main]
  workflow_dispatch:
    inputs:
      run_seed:
        description: "Run database seed script after deployment"
        required: true
        default: false
        type: boolean

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Deploy to Cloud
        run: |
          echo "Deploying application containers..."

      - name: Execute Operational Seed (If requested)
        if: ${{ inputs.run_seed == true }}
        env:
          DATABASE_URL: ${{ secrets.PROD_DATABASE_URL }}
          SEED_ADMIN_EMAIL: ${{ secrets.SEED_ADMIN_EMAIL }}
          SEED_ADMIN_PASSWORD: ${{ secrets.SEED_ADMIN_PASSWORD }}
        run: |
          python -m venv .venv
          .venv/bin/pip install -e .
          .venv/bin/python scripts/seed_operational_data.py
```

---

## 6. Post-Deployment Verification Checklist

1. **Verify Health Endpoint**:
   ```bash
   curl -i https://api.yourdomain.com/health
   # Expected: HTTP/1.1 200 OK {"status": "healthy"}
   ```

2. **Verify Admin Authentication**:
   ```bash
   curl -s -X POST https://api.yourdomain.com/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@yourcompany.com","password":"YourStrongAdminPassword2026!"}'
   ```

3. **Verify SQL Route Execution**:
   ```bash
   TOKEN="<JWT_TOKEN_FROM_STEP_2>"
   curl -s -X POST https://api.yourdomain.com/api/v1/agent/query \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"prompt":"List all active vendors and their risk ratings"}'
   ```

4. **Verify Hybrid Ingestion & Document Processing**:
   Check ingestion worker logs to ensure connection to PostgreSQL and successful document polling:
   ```bash
   docker compose -f docker-compose.prod.yml logs -f worker
   ```
