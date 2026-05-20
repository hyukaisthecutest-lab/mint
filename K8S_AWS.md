# Moving Mint to Kubernetes on AWS

## Current stack → what replaces it

| What you run now (Docker Compose) | AWS service on K8s |
|---|---|
| PostgreSQL container | RDS PostgreSQL |
| Redis container | ElastiCache Redis |
| nginx + FastAPI containers | EKS + ALB Ingress |
| Celery worker container | EKS Deployment (separate pod) |
| S3 (already using) | S3 (keep as-is) |
| Local logs | CloudWatch Logs |
| GitHub secrets | Secrets Manager |

---

## Services you need and why

### 1. EKS — Elastic Kubernetes Service
**What:** AWS-managed Kubernetes control plane.  
**Why:** Runs your pods (backend, celery, frontend). AWS handles the master node, upgrades, and etcd. You only manage worker nodes (or go serverless with Fargate).  
**Your pods:** `backend`, `celery-worker`, `celery-beat`, `frontend`

---

### 2. ECR — Elastic Container Registry
**What:** Private Docker image registry inside AWS.  
**Why:** EKS pulls images from ECR without credentials — they share IAM. Faster pulls than Docker Hub (same AWS region = no internet). Replace your current `--build` in docker compose with CI pushing to ECR.  
**Your images:** `mint-backend`, `mint-frontend`

---

### 3. RDS — Relational Database Service (PostgreSQL)
**What:** Managed PostgreSQL.  
**Why:** Your PostgreSQL is currently a container — if that pod restarts, data is gone unless you set up persistent volumes carefully. RDS handles backups, failover, patching, and point-in-time recovery automatically. Never run a database in a pod in production.  
**Replace:** `postgres` container in docker-compose  
**Size to start:** `db.t3.micro` (free tier) → scale to `db.t3.medium` when needed

---

### 4. ElastiCache — Redis
**What:** Managed Redis cluster.  
**Why:** Redis is used for 3 things in your app — Celery task queue, Celery result backend, and chat session storage. Running Redis in a pod risks losing all queued jobs and sessions on restart. ElastiCache gives you persistence, replication, and automatic failover.  
**Replace:** `redis` container in docker-compose  
**Size to start:** `cache.t3.micro`

---

### 5. S3 — Simple Storage Service
**What:** Object storage.  
**Why:** Already using it for receipt images. On K8s, pods are ephemeral — anything written to disk is lost when a pod restarts. S3 is the right place for all uploaded files.  
**Your usage:** Receipt images (uploaded → scanned → deleted), future: user profile images, exports

---

### 6. ALB — Application Load Balancer (via AWS Load Balancer Controller)
**What:** HTTP/HTTPS load balancer managed by K8s Ingress.  
**Why:** Replaces nginx on EC2 as your public entry point. Routes `/api/` to the backend pods and `/` to the frontend pods. Handles SSL termination, health checks, and distributes traffic across multiple pod replicas automatically.  
**Install:** `aws-load-balancer-controller` Helm chart in your cluster

---

### 7. ACM — AWS Certificate Manager
**What:** Free SSL/TLS certificates.  
**Why:** You need HTTPS to fix the `crypto.randomUUID` and `getUserMedia` issues that only work in secure contexts. ACM issues and auto-renews the certificate, ALB attaches it — zero manual cert management.  
**Action:** Request a certificate for your domain, attach to ALB Ingress annotation

---

### 8. Secrets Manager
**What:** Encrypted secret storage with IAM-controlled access.  
**Why:** Currently secrets are GitHub Actions secrets injected as environment variables. On K8s you need secrets available inside pods. Secrets Manager + the `external-secrets` operator syncs them into Kubernetes Secrets automatically. Secrets rotate without redeploying.  
**Your secrets:** `OPENAI_API_KEY`, `SECRET_KEY`, `AWS_*`, `SMTP_*`, `DATABASE_URL`

---

### 9. IAM IRSA — IAM Roles for Service Accounts
**What:** Pod-level AWS permissions without hardcoded credentials.  
**Why:** Instead of putting `AWS_ACCESS_KEY_ID` in environment variables, you attach an IAM role directly to the Kubernetes service account. Pods automatically get temporary credentials. Follows least-privilege — your backend pod only gets S3 access, not admin.  
**Replace:** `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` env vars in containers

---

### 10. CloudWatch Logs
**What:** Centralized log storage and search.  
**Why:** On EC2 you run `docker logs`. On K8s with multiple pods across multiple nodes that can restart anytime, you need logs shipped somewhere persistent. The `aws-for-fluent-bit` DaemonSet runs on every node and ships all pod logs to CloudWatch automatically.  
**Your logs:** JSON structured logs from `mint.chat`, `mint.agent`, `mint.transactions`

---

### 11. Route 53
**What:** DNS management.  
**Why:** Point your domain to the ALB. When you scale or replace the ALB, Route 53 updates automatically via ExternalDNS controller. Also handles health-check-based failover if you ever go multi-region.

---

## Architecture diagram

```
Internet
    │
    ▼
Route 53 (DNS)
    │
    ▼
ALB (HTTPS, ACM cert)
    │
    ├──► /api/*  ──► backend pods (FastAPI)  ──► RDS PostgreSQL
    │                      │                 └──► ElastiCache Redis
    │                      └──► S3 (receipts)
    │
    ├──► /*      ──► frontend pods (nginx/React)
    │
    └──► /ws/*   ──► backend pods (WebSocket)

Celery worker pods ──► ElastiCache Redis (queue)
                   └──► RDS PostgreSQL
                   └──► S3 (download receipts)

Celery beat pod ──► ElastiCache Redis

All pods ──► CloudWatch Logs (via Fluent Bit DaemonSet)
All pods ──► Secrets Manager (via External Secrets Operator)
EKS nodes ──► ECR (pull images)
```

---

## Migration order (safest path)

1. **RDS + ElastiCache first** — migrate data out of containers before anything else
2. **ECR** — push your images, update CI to push on merge
3. **EKS cluster** — start with 2 nodes, deploy all workloads
4. **ALB + ACM** — cut DNS over, get HTTPS working
5. **Secrets Manager** — move secrets out of env vars
6. **CloudWatch** — set up log shipping and alarms
7. **IRSA** — remove hardcoded AWS credentials last

---

## What you keep from current setup

- **Alembic** — migrations still run as a Kubernetes Job before deployment
- **S3** — already in use, no change
- **Celery** — same code, just runs in separate pods
- **Prometheus `/metrics`** — add a `ServiceMonitor` and deploy Prometheus Operator
- **Jaeger** — deploy as a K8s Deployment, same OTLP config
