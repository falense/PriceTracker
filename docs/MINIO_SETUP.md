# MinIO Setup Guide

This guide covers MinIO configuration for PriceTracker production deployment, including private file storage, CORS setup for browser extensions, and GitHub Actions integration.

## Overview

MinIO provides S3-compatible object storage for:
- Product images and screenshots
- Price history artifacts
- Extractor pattern artifacts
- GitHub Actions build artifacts (optional)

**Access Control:**
- **Private Storage:** All files require authentication
- **Signed URLs:** Django generates temporary access URLs (1-hour expiry)
- **GitHub Actions:** Authenticates with MinIO credentials
- **Browser Extension:** Uploads via Django API (Django handles MinIO auth)

## Architecture

```
┌─────────────────┐
│  Traefik (SSL)  │
└────────┬────────┘
         │
    ┌────┴────┐
    │ MinIO   │
    └────┬────┘
         │
    ┌────┴────────────────────┐
    │                         │
┌───┴────┐            ┌───────┴─────┐
│ Django │            │ GitHub       │
│  App   │            │ Actions      │
└────────┘            └──────────────┘
```

**Endpoints:**
- **API:** `https://s3.yourdomain.com` (S3-compatible)
- **Console:** `https://minio.yourdomain.com` (Web UI)

## Initial Setup

### 1. Access MinIO Console

Navigate to: `https://minio.yourdomain.com`

Login credentials from `.env`:
- **Username:** `MINIO_ROOT_USER`
- **Password:** `MINIO_ROOT_PASSWORD`

### 2. Create Bucket

**Via Console:**
1. Click "Buckets" → "Create Bucket"
2. Name: `pricetracker-media`
3. Versioning: Disabled (optional)
4. Object Locking: Disabled
5. Click "Create Bucket"

**Via MinIO Client (mc):**
```bash
# Install mc
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc /usr/local/bin/

# Configure alias
mc alias set minio https://s3.yourdomain.com MINIO_ROOT_USER MINIO_ROOT_PASSWORD

# Create bucket
mc mb minio/pricetracker-media

# Verify
mc ls minio/
```

### 3. Configure Bucket Policy

**Default Policy (Private):**
Files are private by default. No public access configuration needed.

**Verify Policy:**
```bash
mc anonymous get minio/pricetracker-media
# Should return: Access permission for 'minio/pricetracker-media' is 'none'
```

## CORS Configuration

Browser extensions need CORS to upload files. Configure CORS on the bucket:

### Method 1: Via MinIO Console

1. Go to "Buckets" → `pricetracker-media`
2. Click "Access" tab
3. Scroll to "CORS Configuration"
4. Add CORS rule:

```json
{
  "CORSRules": [
    {
      "AllowedOrigins": [
        "https://pricetracker.example.com",
        "moz-extension://*",
        "chrome-extension://*"
      ],
      "AllowedMethods": [
        "GET",
        "PUT",
        "POST",
        "DELETE",
        "HEAD"
      ],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag", "x-amz-request-id"],
      "MaxAgeSeconds": 3000
    }
  ]
}
```

5. Click "Save"

### Method 2: Via MinIO Client (mc)

Create `cors-policy.json`:
```json
{
  "CORSRules": [
    {
      "AllowedOrigins": [
        "https://pricetracker.example.com",
        "moz-extension://*",
        "chrome-extension://*"
      ],
      "AllowedMethods": [
        "GET",
        "PUT",
        "POST",
        "DELETE",
        "HEAD"
      ],
      "AllowedHeaders": ["*"],
      "ExposeHeaders": ["ETag", "x-amz-request-id"],
      "MaxAgeSeconds": 3000
    }
  ]
}
```

Apply CORS policy:
```bash
mc cors set-json cors-policy.json minio/pricetracker-media

# Verify
mc cors get minio/pricetracker-media
```

## Django Integration

Django uses `django-storages` with `boto3` to interact with MinIO as an S3-compatible backend.

### Configuration (Automatic)

Settings are configured in `WebUI/config/settings.py`:

```python
# Production only (when DEBUG=False)
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

AWS_ACCESS_KEY_ID = MINIO_ROOT_USER
AWS_SECRET_ACCESS_KEY = MINIO_ROOT_PASSWORD
AWS_STORAGE_BUCKET_NAME = 'pricetracker-media'
AWS_S3_ENDPOINT_URL = 'https://s3.yourdomain.com'

# Private files with signed URLs
AWS_DEFAULT_ACL = 'private'
AWS_QUERYSTRING_AUTH = True  # Generate signed URLs
AWS_QUERYSTRING_EXPIRE = 3600  # 1 hour
```

### Usage in Code

```python
from django.db import models

class Product(models.Model):
    # Files automatically uploaded to MinIO
    image = models.ImageField(upload_to='products/')
    screenshot = models.ImageField(upload_to='screenshots/')
```

### Get Signed URLs

Django automatically generates signed URLs for private files:

```python
# In views
product = Product.objects.get(id=product_id)

# This URL is valid for 1 hour
signed_url = product.image.url

# Pass to template
context = {'image_url': signed_url}
```

## GitHub Actions Integration

GitHub Actions can upload build artifacts directly to MinIO.

### 1. Add Secrets to GitHub

In your repository:
1. Go to "Settings" → "Secrets and variables" → "Actions"
2. Add repository secrets:
   - `MINIO_ACCESS_KEY`: Your `MINIO_ROOT_USER`
   - `MINIO_SECRET_KEY`: Your `MINIO_ROOT_PASSWORD`
   - `MINIO_ENDPOINT`: `https://s3.yourdomain.com`

### 2. Use in Workflow

Example GitHub Actions workflow:

```yaml
name: Build and Upload

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Build artifacts
        run: |
          # Your build commands
          npm run build

      - name: Upload to MinIO
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.MINIO_ACCESS_KEY }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.MINIO_SECRET_KEY }}
          AWS_EC2_METADATA_DISABLED: true
        run: |
          # Install AWS CLI
          pip install awscli

          # Upload to MinIO
          aws s3 cp dist/ s3://pricetracker-media/builds/${{ github.sha }}/ \
            --recursive \
            --endpoint-url ${{ secrets.MINIO_ENDPOINT }}

          echo "Artifacts uploaded to: builds/${{ github.sha }}/"
```

### 3. Verify Upload

Check MinIO console:
1. Go to "Object Browser"
2. Navigate to `pricetracker-media/builds/`
3. Verify your build artifacts are present

## File Access Methods

### 1. Via Django (Recommended)

**Upload:**
```python
from django.core.files.base import ContentFile

# Django handles MinIO authentication
product.image.save('product.jpg', ContentFile(image_data))
```

**Download:**
```python
# Get signed URL (valid 1 hour)
url = product.image.url

# Or read file directly
with product.image.open('rb') as f:
    data = f.read()
```

### 2. Direct MinIO API (GitHub Actions)

**Upload:**
```bash
aws s3 cp file.zip s3://pricetracker-media/path/to/file.zip \
  --endpoint-url https://s3.yourdomain.com
```

**Download:**
```bash
aws s3 cp s3://pricetracker-media/path/to/file.zip ./file.zip \
  --endpoint-url https://s3.yourdomain.com
```

### 3. Via MinIO Console (Manual)

1. Login to `https://minio.yourdomain.com`
2. Navigate to bucket
3. Upload/download files manually

## Browser Extension Integration

Browser extensions upload files through Django API, not directly to MinIO.

**Flow:**
```
Extension → Django API → MinIO (authenticated)
```

**Django handles:**
- MinIO authentication
- File validation
- Signed URL generation

**Extension receives:**
- Signed URL for uploaded file
- 1-hour access to view/download

## Security Considerations

### Private Files
- All files stored with `private` ACL
- No anonymous access
- Requires authentication or signed URL

### Signed URLs
- Valid for 1 hour only
- Cannot be refreshed (must request new URL)
- Include cryptographic signature

### Credentials
- Never expose MinIO credentials in client-side code
- Use environment variables only
- Rotate credentials if compromised

### GitHub Actions
- Store credentials as GitHub Secrets (encrypted)
- Never log credentials
- Use minimal permissions

## Monitoring

### Check Bucket Usage
```bash
mc du minio/pricetracker-media
```

### List Recent Uploads
```bash
mc ls --recursive minio/pricetracker-media | tail -20
```

### Bucket Statistics
Via MinIO Console:
1. Go to "Monitoring" → "Metrics"
2. View storage usage, requests, bandwidth

## Troubleshooting

### Connection Refused
```bash
# Check MinIO is running
docker compose -f docker-compose.prod.yml ps minio

# Check MinIO logs
docker compose -f docker-compose.prod.yml logs minio
```

### Authentication Failed
```bash
# Verify credentials match
echo $MINIO_ROOT_USER
echo $MINIO_ROOT_PASSWORD

# Check Django settings
docker compose -f docker-compose.prod.yml exec web \
  python manage.py shell -c "from django.conf import settings; print(settings.AWS_ACCESS_KEY_ID)"
```

### CORS Errors
```bash
# Check CORS policy
mc cors get minio/pricetracker-media

# Re-apply CORS
mc cors set-json cors-policy.json minio/pricetracker-media
```

### File Upload Fails
```bash
# Check bucket exists
mc ls minio/ | grep pricetracker-media

# Check permissions
mc stat minio/pricetracker-media

# Test upload
echo "test" | mc pipe minio/pricetracker-media/test.txt
mc cat minio/pricetracker-media/test.txt
mc rm minio/pricetracker-media/test.txt
```

## Backup & Disaster Recovery

### Backup MinIO Data

**Method 1: Volume Backup**
```bash
# Backup minio-data volume
docker run --rm \
  -v pricetracker_minio-data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/minio-backup-$(date +%Y%m%d).tar.gz /data
```

**Method 2: MinIO Mirror**
```bash
# Mirror to another MinIO/S3
mc mirror minio/pricetracker-media backup-minio/pricetracker-media
```

### Restore MinIO Data
```bash
# Restore from volume backup
docker compose -f docker-compose.prod.yml stop minio
docker run --rm \
  -v pricetracker_minio-data:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd / && tar xzf /backup/minio-backup-YYYYMMDD.tar.gz"
docker compose -f docker-compose.prod.yml start minio
```

## Advanced Configuration

### Lifecycle Policies
Auto-delete old files:

```bash
# Create lifecycle policy
mc ilm add --expiry-days 90 minio/pricetracker-media/temp/

# List lifecycle rules
mc ilm ls minio/pricetracker-media
```

### Bucket Versioning
Keep file versions:

```bash
# Enable versioning
mc version enable minio/pricetracker-media

# List versions
mc ls --versions minio/pricetracker-media/path/to/file.jpg
```

### Encryption
Server-side encryption:

```bash
# Enable default encryption
mc encrypt set sse-s3 minio/pricetracker-media
```

## References

- [MinIO Documentation](https://docs.min.io/)
- [django-storages Documentation](https://django-storages.readthedocs.io/)
- [AWS CLI S3 Commands](https://docs.aws.amazon.com/cli/latest/reference/s3/)
