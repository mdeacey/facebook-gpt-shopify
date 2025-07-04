#!/bin/bash

source /app/.env

if [ -z "$SPACES_API_KEY" ] || [ -z "$SPACES_API_SECRET" ] || [ -z "$SPACES_REGION" ] || [ -z "$SPACES_BUCKET" ] || [ -z "$SPACES_ENDPOINT" ]; then
    echo "Error: Missing required environment variables for Spaces"
    exit 1
fi

DATE=$(date +%Y-%m-%d)
DB_PATH="${SESSION_DB_PATH:-/app/data/sessions.db}"
BACKUP_DIR="/app/backups"
BACKUP_FILE="$BACKUP_DIR/sessions_$DATE.db"

mkdir -p "$BACKUP_DIR"

if ! cp "$DB_PATH" "$BACKUP_FILE"; then
    echo "Error: Failed to copy sessions.db to backup directory"
    exit 1
fi

export AWS_ACCESS_KEY_ID="$SPACES_API_KEY"
export AWS_SECRET_ACCESS_KEY="$SPACES_API_SECRET"
export AWS_DEFAULT_REGION="$SPACES_REGION"

aws --endpoint-url "$SPACES_ENDPOINT" s3 cp "$BACKUP_FILE" "s3://$SPACES_BUCKET/backups/sessions_$DATE.db"
if [ $? -eq 0 ]; then
    echo "Successfully uploaded sessions_$DATE.db to Spaces"
else
    echo "Error: Failed to upload sessions_$DATE.db to Spaces"
    exit 1
fi