# Production Deployment Guide

This guide covers deploying PriceTracker to production with a hardened Docker Compose setup including Traefik SSL termination, PostgreSQL database, and private MinIO object storage.

## Architecture Overview

**Services:**
- **Traefik:** Reverse proxy with automatic Let's Encrypt SSL certificates
- **Web:** Django application (Gunicorn) with 4 workers
- **PostgreSQL:** Production database with automated backups
- **Redis:** Message broker and cache (password-protected)
- **MinIO:** S3-compatible object storage (private, authenticated access)
- **Celery Workers:** 2 workers (default queue + pattern generation queue)
- **Celery Beat:** Periodic task scheduler
- **Flower:** Celery monitoring UI (password-protected)
- **Backup:** Automated PostgreSQL backup service

**Networks:**
- `frontend`: Traefik ↔ Web/MinIO/Flower (external access via SSL)
- `backend`: Internal services only (fully isolated)

**Domains Required:**
- `pricetracker.example.com` - Main application
- `s3.pricetracker.example.com` - MinIO S3 API
- `minio.pricetracker.example.com` - MinIO console
- `flower.pricetracker.example.com` - Celery monitoring

## Prerequisites

### Server Requirements
- **OS:** Ubuntu 20.04+ or Debian 11+
- **RAM:** Minimum 4GB (8GB recommended)
- **Disk:** Minimum 20GB free space
- **CPU:** 2+ cores recommended

### DNS Configuration
Configure DNS A records or CNAMEs for:
```
pricetracker.example.com        → YOUR_SERVER_IP
s3.pricetracker.example.com     → YOUR_SERVER_IP
minio.pricetracker.example.com  → YOUR_SERVER_IP
flower.pricetracker.example.com → YOUR_SERVER_IP
```

Verify DNS propagation:
```bash
dig pricetracker.example.com
dig s3.pricetracker.example.com
dig minio.pricetracker.example.com
dig flower.pricetracker.example.com
```

### Firewall Configuration
Allow only ports 80 and 443:
```bash
# UFW (Ubuntu)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Or iptables
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
```

### Install Docker & Docker Compose
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose V2 (if not included)
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Verify installation
docker compose version
```

## Deployment Steps

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/PriceTracker.git
cd PriceTracker
```

### 2. Generate Secrets
Create strong passwords for all services:

```bash
# Django SECRET_KEY
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# PostgreSQL password
openssl rand -base64 32

# Redis password
openssl rand -base64 32

# MinIO credentials
openssl rand -base64 32 | tr -d '/+=' | head -c 32  # Username
openssl rand -base64 48 | tr -d '/+='              # Password

# Flower password
openssl rand -base64 24
```

### 3. Configure Environment
Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your actual values:
```bash
nano .env
```

**Required variables:**
```env
# Domain
DOMAIN=pricetracker.example.com
ACME_EMAIL=admin@example.com

# Django
SECRET_KEY=<generated-secret-key>
DEBUG=False
ALLOWED_HOSTS=pricetracker.example.com
CSRF_TRUSTED_ORIGINS=https://pricetracker.example.com

# PostgreSQL
POSTGRES_DB=pricetracker
POSTGRES_USER=pricetracker_user
POSTGRES_PASSWORD=<generated-password>

# Redis
REDIS_PASSWORD=<generated-password>

# MinIO
MINIO_ROOT_USER=<generated-username>
MINIO_ROOT_PASSWORD=<generated-password>

# Flower
FLOWER_USER=admin
FLOWER_PASSWORD=<generated-password>

# Backups
BACKUP_RETENTION_DAYS=30
BACKUP_SCHEDULE=0 2 * * *
```

**IMPORTANT:** Never commit `.env` to version control!

### 4. Build Images
Build all production Docker images:
```bash
docker compose -f docker-compose.prod.yml build
```

### 5. Initialize Database
Start PostgreSQL and run migrations:
```bash
# Start PostgreSQL only
docker compose -f docker-compose.prod.yml up -d postgres

# Wait for PostgreSQL to be ready
docker compose -f docker-compose.prod.yml exec postgres pg_isready -U pricetracker_user

# Run migrations
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate

# Create superuser
docker compose -f docker-compose.prod.yml run --rm web python manage.py createsuperuser
```

### 6. Configure MinIO
Start MinIO and create bucket:
```bash
# Start MinIO
docker compose -f docker-compose.prod.yml up -d minio

# Access MinIO console at https://minio.pricetracker.example.com
# Login with MINIO_ROOT_USER and MINIO_ROOT_PASSWORD

# Create bucket 'pricetracker-media'
# Set bucket policy to private (default)
```

See [MINIO_SETUP.md](./MINIO_SETUP.md) for detailed MinIO configuration.

### 7. Start All Services
```bash
docker compose -f docker-compose.prod.yml up -d
```

### 8. Monitor SSL Certificate Acquisition
Watch Traefik logs for Let's Encrypt certificate requests:
```bash
docker compose -f docker-compose.prod.yml logs -f traefik
```

Look for lines like:
```
Certificate obtained for domain pricetracker.example.com
Certificate obtained for domain s3.pricetracker.example.com
Certificate obtained for domain minio.pricetracker.example.com
Certificate obtained for domain flower.pricetracker.example.com
```

### 9. Verify Deployment
Test all endpoints:
```bash
# Main application
curl -I https://pricetracker.example.com

# Health check
curl https://pricetracker.example.com/health/

# MinIO API (should require authentication)
curl -I https://s3.pricetracker.example.com

# MinIO Console
curl -I https://minio.pricetracker.example.com

# Flower (should prompt for auth)
curl -I https://flower.pricetracker.example.com
```

### 10. Test HTTP → HTTPS Redirect
```bash
curl -I http://pricetracker.example.com
# Should see: Location: https://pricetracker.example.com
```

## Post-Deployment

### Check Service Health
```bash
# View all container statuses
docker compose -f docker-compose.prod.yml ps

# Check health status
docker compose -f docker-compose.prod.yml ps | grep healthy
```

### View Logs
```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f celery
docker compose -f docker-compose.prod.yml logs -f postgres
```

### Access Services
- **Web App:** https://pricetracker.example.com
- **Admin Panel:** https://pricetracker.example.com/admin/
- **MinIO Console:** https://minio.pricetracker.example.com
- **Flower Monitoring:** https://flower.pricetracker.example.com

### Verify Backups
Check that PostgreSQL backups are being created:
```bash
# List backups
docker compose -f docker-compose.prod.yml exec postgres-backup ls -lh /backups/

# Manually trigger backup
docker compose -f docker-compose.prod.yml exec postgres-backup /backup.sh
```

## Maintenance

### Update Application
```bash
# Pull latest code
git pull origin main

# Rebuild images
docker compose -f docker-compose.prod.yml build

# Restart services
docker compose -f docker-compose.prod.yml up -d

# Run migrations (if needed)
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

### Database Backup & Restore

**Manual Backup:**
```bash
docker compose -f docker-compose.prod.yml exec postgres-backup /backup.sh
```

**Restore from Backup:**
```bash
# Stop services
docker compose -f docker-compose.prod.yml stop web celery celery-pattern-worker celery-beat

# Restore database
docker compose -f docker-compose.prod.yml exec postgres sh -c \
  "gunzip < /backups/pricetracker_YYYYMMDD_HHMMSS.sql.gz | psql -U \$POSTGRES_USER -d \$POSTGRES_DB"

# Restart services
docker compose -f docker-compose.prod.yml start web celery celery-pattern-worker celery-beat
```

### Scale Workers
Increase Celery workers:
```bash
docker compose -f docker-compose.prod.yml up -d --scale celery=3
```

### Update Environment Variables
```bash
# Edit .env
nano .env

# Restart affected services
docker compose -f docker-compose.prod.yml up -d
```

## Security Checklist

- [ ] All secrets in `.env` are strong (32+ characters)
- [ ] `.env` file has correct permissions (600)
- [ ] `.env` is in `.gitignore`
- [ ] DEBUG=False in production
- [ ] Only ports 80/443 exposed on firewall
- [ ] SSL certificates obtained for all domains
- [ ] HTTPS redirect working
- [ ] Flower authentication enabled
- [ ] MinIO files are private (not public)
- [ ] PostgreSQL backups running
- [ ] Security headers present (check with curl -I)

## Troubleshooting

### SSL Certificates Not Obtained
```bash
# Check Traefik logs
docker compose -f docker-compose.prod.yml logs traefik

# Common issues:
# - DNS not propagated yet
# - Port 80 not accessible from internet
# - Invalid email in ACME_EMAIL
```

### Database Connection Errors
```bash
# Check PostgreSQL health
docker compose -f docker-compose.prod.yml exec postgres pg_isready

# Check credentials in .env
# Verify DATABASE_URL is correct
```

### MinIO Access Issues
```bash
# Check MinIO health
docker compose -f docker-compose.prod.yml exec minio curl http://localhost:9000/minio/health/live

# Verify credentials match between .env and services
```

### Service Won't Start
```bash
# Check specific service logs
docker compose -f docker-compose.prod.yml logs <service-name>

# Common issues:
# - Missing environment variables
# - Database not ready
# - Port conflicts
```

## Rollback Procedure

If deployment fails:
```bash
# 1. Stop production services
docker compose -f docker-compose.prod.yml down

# 2. Review logs
docker compose -f docker-compose.prod.yml logs

# 3. Fix issues in code or configuration

# 4. Rebuild and retry
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

## Performance Tuning

### Gunicorn Workers
Adjust workers in docker-compose.prod.yml:
```yaml
--workers 4  # CPU cores * 2 + 1
--threads 2   # For CPU-bound tasks
```

### PostgreSQL Tuning
Adjust PostgreSQL parameters in docker-compose.prod.yml based on server RAM.

### Redis Memory
Adjust max memory in docker-compose.prod.yml:
```yaml
--maxmemory 512mb  # Increase if needed
```

## Support

For issues:
1. Check service logs
2. Review this deployment guide
3. Consult [MINIO_SETUP.md](./MINIO_SETUP.md) for storage issues
4. Open an issue on GitHub
