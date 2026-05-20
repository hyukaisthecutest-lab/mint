# Mint — Personal Finance App

A Mint.com-inspired personal finance tracker with React frontend, Python (FastAPI) backend, PostgreSQL, Redis/Celery job queue, and AWS deployment via GitHub Actions CI/CD.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  CloudFront CDN                                      │
│  ┌──────────────────┐  /api/*  ┌──────────────────┐ │
│  │  S3 (React SPA)  │ ───────► │  ALB → ECS/API   │ │
│  └──────────────────┘          └────────┬─────────┘ │
│                                         │           │
│                               ┌─────────┴────────┐  │
│                               │  ECS Celery Worker│  │
│                               └─────────┬────────┘  │
│                        ┌────────────────┴─────────┐ │
│                        │  RDS PostgreSQL           │ │
│                        │  ElastiCache Redis        │ │
│                        └──────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

## Stack

| Layer | Tech |
|-------|------|
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Backend | FastAPI + SQLAlchemy 2 + Alembic |
| Queue | Celery + Redis |
| Database | PostgreSQL 16 |
| Infrastructure | AWS CDK (Python) |
| CI/CD | GitHub Actions |

## Local Development

### Prerequisites
- Docker & Docker Compose
- Node.js 20+ (for frontend outside Docker)
- Python 3.12+ (for backend outside Docker)

### Start everything with Docker Compose

```bash
cd mint
cp .env.example .env
docker compose up --build
```

Services:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- PostgreSQL: localhost:5432
- Redis: localhost:6379

### Run migrations

```bash
docker compose exec backend alembic upgrade head
```

### Run tests

```bash
docker compose exec backend pytest tests/ -v
```

## Project Structure

```
mint/
├── backend/                  # FastAPI app
│   ├── app/
│   │   ├── api/routes/       # auth, accounts, transactions, dashboard
│   │   ├── core/             # config, database, security, celery
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # fake_bank (third-party simulator)
│   │   └── tasks/            # Celery sync tasks
│   └── alembic/              # DB migrations
├── frontend/                 # React SPA
│   └── src/
│       ├── api/              # Axios API clients
│       ├── pages/            # Dashboard, Accounts, Transactions, Login, Register
│       ├── components/       # Layout, shared components
│       └── store/            # Zustand auth store
├── infrastructure/           # AWS CDK (Python)
│   └── stacks/mint_stack.py  # VPC, RDS, ElastiCache, ECS, S3, CloudFront
└── .github/workflows/        # CI and deploy pipelines
```

## How the Fake Bank Integration Works

1. User links an account (POST `/api/v1/accounts`)
2. Backend generates a unique `external_account_id` and seeds `third_party_transactions` table with ~45 realistic fake transactions (90 days of history)
3. User clicks "Sync" — this fires a Celery task (`sync_account_transactions`)
4. Worker reads unsynced rows from `third_party_transactions`, creates `Transaction` records, updates account balance, marks rows as synced

## API Endpoints

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
GET    /api/v1/auth/me

GET    /api/v1/accounts
POST   /api/v1/accounts
DELETE /api/v1/accounts/{id}
POST   /api/v1/accounts/{id}/sync
POST   /api/v1/accounts/sync-all

GET    /api/v1/transactions?page=1&category=Food+%26+Drink&account_id=...

GET    /api/v1/dashboard
```

## AWS Deployment

### Prerequisites
- AWS account with sufficient permissions
- AWS CDK CLI: `npm i -g aws-cdk`
- GitHub repository with the following secrets set:

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM user access key |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key |
| `ECR_REGISTRY` | ECR registry URL (e.g. `123456789012.dkr.ecr.us-east-1.amazonaws.com`) |
| `FRONTEND_S3_BUCKET` | S3 bucket name for frontend |
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront distribution ID |
| `PRIVATE_SUBNET_IDS` | Comma-separated private subnet IDs |
| `ECS_SECURITY_GROUP` | ECS task security group ID |
| `VITE_API_URL` | Backend API URL |

### Bootstrap & Deploy Infrastructure

```bash
cd infrastructure
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cdk bootstrap aws://ACCOUNT_ID/us-east-1
cdk deploy
```

### CI/CD Flow

- **On any push/PR**: lint, type-check, test, Docker build (no deploy)
- **On push to `main`**:
  1. Build backend Docker image → push to ECR
  2. Run `alembic upgrade head` via ECS one-off task
  3. Deploy new backend image to ECS Fargate (rolling update)
  4. Build frontend → upload to S3 → CloudFront cache invalidation
