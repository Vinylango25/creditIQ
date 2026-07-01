#!/usr/bin/env bash
# Render build script for CreditIQ backend
set -e

echo "=== CreditIQ Backend Build ==="
cd backend

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Build complete ==="
