#!/bin/bash

source /app/.env

if [ -z "$SPACES_API_KEY" ] || [ -z "$SPACES_API_SECRET" ] || [ -z "$SPACES_REGION" ] || [ -z "$SPACES_BUCKET" ] || [ -z "$SPACES_ENDPOINT" ]; then
    echo "Error: Missing required environment variables for Spaces"
    exit 1
fi

DATE=$(date +%Y-%m-%d)
DB_PATH="${TOKEN_DB_PATH:-/app/data/tokens.db}"
BACKUP_DIR="/app/backups"
BACKUP_FILE="$BACKUP_DIR/tokens_$DATE.db"

mkdir -p "$BACKUP_DIR"

if ! cp "$DB_PATH" "$BACKUP_FILE"; then
    echo "Error: Failed to copy tokens.db to backup directory"
    exit 1
fi

export AWS_ACCESS_KEY_ID="$SPACES_API_KEY"
export AWS_SECRET_ACCESS_KEY="$SPACES_API_SECRET"
export AWS_DEFAULT_REGION="$SPACES_REGION"

aws --endpoint-url "$SPACES_ENDPOINT" s3 cp "$BACKUP_FILE" "s3://$SPACES_BUCKET/backups/tokens_$DATE.db"
if [ $? -eq 0 ]; then
    echo "Successfully uploaded tokens_$DATE.db to Spaces"
else
    echo "Error: Failed to upload tokens_$DATE.db to Spaces"
    exit 1
fi