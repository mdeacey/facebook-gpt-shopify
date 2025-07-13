#!/bin/bash

# Set file paths
GPG_FILE="/workspaces/facebook-gpt-shopify/.env.gpg"
ENV_FILE="/workspaces/facebook-gpt-shopify/.env"

# Encrypt or decrypt based on file presence
if [[ -f "$GPG_FILE" && ! -f "$ENV_FILE" ]]; then
    echo "Decrypting $GPG_FILE to $ENV_FILE..."
    gpg -o "$ENV_FILE" -d "$GPG_FILE" || { echo "Decryption failed"; exit 1; }

elif [[ -f "$ENV_FILE" && ! -f "$GPG_FILE" ]]; then
    echo "Encrypting $ENV_FILE to $GPG_FILE..."
    gpg -c -o "$GPG_FILE" "$ENV_FILE" || { echo "Encryption failed"; exit 1; }
    echo "Removing unencrypted .env for safety."
    rm "$ENV_FILE"

else
    echo "⚠️  Cannot determine action:"
    echo "- Either both files exist (won't overwrite),"
    echo "- Or neither exists."
    exit 1
fi
