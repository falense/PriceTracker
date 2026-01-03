#!/bin/bash
# ====================================================================================
# PostgreSQL Automated Backup Script
# ====================================================================================
# Creates compressed PostgreSQL backups with retention policy
# Runs via cron in postgres-backup container
# ====================================================================================

set -e

# Configuration
BACKUP_DIR="/backups"
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="pricetracker_${TIMESTAMP}.sql.gz"

echo "[$(date +"%Y-%m-%d %H:%M:%S")] Starting PostgreSQL backup..."

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Create compressed backup
echo "[$(date +"%Y-%m-%d %H:%M:%S")] Creating backup: ${BACKUP_FILE}"
pg_dump \
  -h postgres \
  -U "${POSTGRES_USER}" \
  -d "${POSTGRES_DB}" \
  --no-owner \
  --no-acl \
  | gzip > "${BACKUP_DIR}/${BACKUP_FILE}"

# Verify backup was created successfully
if [ -f "${BACKUP_DIR}/${BACKUP_FILE}" ]; then
    BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] ✓ Backup created successfully: ${BACKUP_FILE} (${BACKUP_SIZE})"

    # Remove old backups (older than retention period)
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] Cleaning up old backups (retention: ${RETENTION_DAYS} days)..."
    find "${BACKUP_DIR}" -name "pricetracker_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

    # List remaining backups
    BACKUP_COUNT=$(find "${BACKUP_DIR}" -name "pricetracker_*.sql.gz" | wc -l)
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] Current backup count: ${BACKUP_COUNT}"

    echo "[$(date +"%Y-%m-%d %H:%M:%S")] Backup completed successfully!"
else
    echo "[$(date +"%Y-%m-%d %H:%M:%S")] ✗ ERROR: Backup failed - file not created"
    exit 1
fi
