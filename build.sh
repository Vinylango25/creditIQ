#!/bin/bash
# Render build script — runs from repo root
set -e

echo "=== Working directory: $(pwd) ==="
echo "=== Repo contents: $(ls) ==="

echo "=== Installing Python dependencies ==="
pip install -r backend/requirements.txt
echo "=== Backend ready ==="

echo "=== Building Angular frontend ==="
cd frontend
npm install --legacy-peer-deps
npm run build -- --configuration production
echo "=== Frontend built ==="
echo "=== Dist contents: $(ls dist/) ==="
