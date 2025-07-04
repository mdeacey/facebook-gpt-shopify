#!/bin/bash

if [ -f /app/.env ]; then
    set -a
    . /app/.env
    set +a
else
    echo "Error: /app/.env not found" >&2
    exit 1
fi

BACKUP_DIR="/app/backups"
TOKENS_DB="/app/data/tokens.db"
BACKUP_KEY="backups/tokens_$(date +%F).db"

if [ -z "$SPACES_BUCKET" ] || [ -z "$SPACES_REGION" ] || [ -z "$SPACES_ACCESS_KEY" ] || [ -z "$SPACES_SECRET_KEY" ]; then
    echo "Error: Missing required environment variables (SPACES_BUCKET, SPACES_REGION, SPACES_ACCESS_KEY, SPACES_SECRET_KEY)" >&2
    exit 1
fi

mkdir -p $BACKUP_DIR

if [ ! -f "$TOKENS_DB" ]; then
    echo "Error: $TOKENS_DB not found" >&2
    exit 1
fi

cp $TOKENS_DB $BACKUP_DIR/tokens_$(date +%F).db
if [ $? -ne 0 ]; then
    echo "Error: Failed to copy $TOKENS_DB to $BACKUP_DIR" >&2
    exit 1
fi

AWS_ACCESS_KEY_ID=$SPACES_ACCESS_KEY AWS_SECRET_ACCESS_KEY=$SPACES_SECRET_KEY aws s3 cp \
    $BACKUP_DIR/tokens_$(date +%F).db \
    s3://$SPACES_BUCKET/$BACKUP_KEY \
    --acl private \
    --endpoint-url https://$SPACES_REGION.digitaloceanspaces.com
if [ $? -ne 0 ]; then
    echo "Error: Failed to upload backup to Spaces" >&2
    exit 1
fi

find $BACKUP_DIR -name "tokens_*.db" -mtime +7 -delete

echo "Backup of $TOKENS_DB to s3://$SPACES_BUCKET/$BACKUP_KEY completed successfully"
exit 0