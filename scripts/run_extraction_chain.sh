#!/bin/bash
cd "$(dirname "$0")/.."

echo "=== Score 6+ extraction ==="
python -m backend.extract_dart --min-score 6

echo ""
echo "=== Score 5 extraction ==="
python -m backend.extract_dart --min-score 5

echo ""
echo "=== Auto-validation ==="
python scripts/auto_validate.py

echo ""
echo "=== All done ==="
