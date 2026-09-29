# Deploying Backend to Render: Complete Guide

This guide walks you through deploying the Enterprise RAG & Operations Intelligence backend to [Render](https://render.com) and running the operational database seed script.

---

## 1. 100% Free Tier Architecture ($0 / No Credit Card Required)

Render charges for "Starter" plans and background worker services. To ensure your deployment is **100% Free**:

1. **Free Web Service** (`plan: free`):
   - Runs the FastAPI application with dynamic `$PORT` binding and `/health` probe.
   - **Embedded Ingestion Worker**: The background document ingestion worker is embedded directly inside FastAPI's async lifespan, so you don't need a separate paid worker service!
2. **Free Managed PostgreSQL** (`plan: free`):
   - Render provisions a free PostgreSQL 16 database with `pgvector` support.

---

## 2. Automatic Optimizations Already in Place

The codebase is already configured for Render:
- **Database Driver Adapter**: Render provides `DATABASE_URL` as `postgres://...` or `postgresql://...`. In `src/core/config.py`, an automatic validator transforms this into `postgresql+asyncpg://` so SQLAlchemy works out-of-the-box.
- **Automatic `pgvector` Activation**: In `src/main.py`, the application automatically executes `CREATE EXTENSION IF NOT EXISTS vector;` upon startup.
- **Dynamic Port Binding**: The `Dockerfile` binds to Render's dynamic `${PORT}` variable (`CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]`).
- **Administrative Scripts**: The `scripts/` directory is copied into the Docker image, allowing you to run seeding directly inside Render.

---

## 3. Deployment Method A: Using Render Blueprints (Recommended - 1 Click)

A [render.yaml](file:///mnt/d/Work/AIML%20Projects/enterprise-rag-intelligence/render.yaml) file is included in the project root.

### Steps:
1. Push your code to your GitHub/GitLab repository:
   ```bash
   git add .
   git commit -m "Configure Render deployment and database seeding"
   git push origin main
   ```
2. Open your [Render Dashboard](https://dashboard.render.com).
3. Click **New +** in the top navigation and select **Blueprint**.
4. Connect your Git repository.
5. Render will detect `render.yaml` and display the three resources to be created:
   - `enterprise-rag-db` (PostgreSQL Database)
   - `enterprise-rag-api` (Web Service)
   - `enterprise-rag-worker` (Background Worker)
6. Under **Environment Variables**, provide your `GEMINI_API_KEY`:
   - Value: `your-google-gemini-api-key`
7. Click **Apply**. Render will automatically build the Docker images, provision the database, link the connection strings, and start both services.

---

## 4. Deployment Method B: Manual Setup via Render Dashboard

If you prefer to configure services manually via the UI:

### Step 1: Create the PostgreSQL Database
1. Go to **New +** → **PostgreSQL**.
2. Name: `enterprise-rag-db`
3. Database Name: `enterprise_rag`
4. User: `enterprise_user`
5. Version: `16`
6. Click **Create Database**.
7. Once created, note the **Internal Database URL** (e.g., `postgresql://...`) and the **External Database URL**.

### Step 2: Create the Web Service (FastAPI)
1. Go to **New +** → **Web Service**.
2. Select your repository.
3. Configuration:
   - **Name**: `enterprise-rag-api`
   - **Runtime**: `Docker`
   - **Dockerfile Path**: `./Dockerfile`
   - **Health Check Path**: `/health`
4. Under **Environment Variables**, add:
   - `DATABASE_URL`: Paste the **Internal Database URL** from Step 1.
   - `ENVIRONMENT`: `production`
   - `DEBUG`: `false`
   - `GEMINI_API_KEY`: `<your_gemini_api_key>`
   - `ACTIVE_EMBEDDING_MODEL`: `gemini-embedding-001`
   - `EMBEDDING_DIMENSION`: `768`
   - `ACTIVE_LLM_MODEL`: `gemini-3.5-flash-lite`
   - `JWT_SECRET_KEY`: `<generate_random_32_char_secret>`
5. Click **Create Web Service**.

### Step 3: Create the Background Worker
1. Go to **New +** → **Background Worker**.
2. Select your repository.
3. Configuration:
   - **Name**: `enterprise-rag-worker`
   - **Runtime**: `Docker`
   - **Dockerfile Path**: `./Dockerfile`
   - **Docker Command**: `python3 -m src.workers.ingestion_worker`
4. Under **Environment Variables**, add:
   - `DATABASE_URL`: Paste the **Internal Database URL** from Step 1.
   - `ENVIRONMENT`: `production`
   - `DEBUG`: `false`
   - `GEMINI_API_KEY`: `<your_gemini_api_key>`
   - `ACTIVE_EMBEDDING_MODEL`: `gemini-embedding-001`
   - `EMBEDDING_DIMENSION`: `768`
5. Click **Create Background Worker**.

---

## 5. How to Run Database Seeding on Render

Once your database and backend are deployed, you have two simple ways to run the operational data seed:

### Method 1: Using the Render Web Shell (Easiest)
1. In the Render Dashboard, click on your **`enterprise-rag-api`** Web Service.
2. In the left sidebar, click the **Shell** tab.
3. Click **Connect**.
4. In the web terminal that opens, run:
   ```bash
   python3 scripts/seed_operational_data.py
   ```
5. *(Optional)* If you want to customize the admin email and password:
   ```bash
   SEED_ADMIN_EMAIL="admin@yourcompany.com" SEED_ADMIN_PASSWORD="YourStrongPassword!" python3 scripts/seed_operational_data.py
   ```
6. The terminal will log confirmation of all seeded records:
   ```text
   [INFO] Seeding completed successfully! ✅
   Admin Credentials:
     Email:    admin@gmail.com
     Password: Admin@12345
     Role:     ADMIN
   Operational Entities Seeded:
     - Departments: 5 records
     - Employees: 11 records
     - Vendors: 6 records
     - Contracts: 5 records
     - Invoices: 11 records
     - Operational_expenses: 19 records
   ```

---

### Method 2: Running from Your Local Machine Against Render Database
If you prefer not to open the web shell, you can run the seed script from your local machine targeting Render's **External Database URL**:

1. In Render, go to your **`enterprise-rag-db`** page.
2. Under **Connections**, copy the **External Database URL**.
3. In your local terminal, run:
   ```bash
   DATABASE_URL="<PASTE_EXTERNAL_DATABASE_URL>" .venv/bin/python scripts/seed_operational_data.py
   ```
   *(Note: The script automatically handles converting `postgres://` or `postgresql://` to `postgresql+asyncpg://`).*

---

## 6. Verifying Your Render Deployment

1. **Test Health Endpoint**:
   ```bash
   curl https://enterprise-rag-api.onrender.com/health
   # Expected: {"status": "healthy"}
   ```

2. **Test Admin Login**:
   ```bash
   curl -s -X POST https://enterprise-rag-api.onrender.com/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@gmail.com","password":"Admin@12345"}'
   ```

3. **Test SQL Natural Language Query**:
   ```bash
   TOKEN="<JWT_TOKEN_FROM_STEP_2>"
   curl -s -X POST https://enterprise-rag-api.onrender.com/api/v1/agent/query \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"prompt":"What is the total operational expense per department?"}'
   ```
