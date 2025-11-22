#!/bin/bash
# Test enriched RIASEC endpoint via curl

echo "Testing enriched RIASEC endpoint with ACR code..."
echo "================================================"

curl -X POST "http://localhost:8000/api/v1/assessment/riasec" \
  -H "Content-Type: application/json" \
  -d '{"riasec_code": "ACR", "limit": 10}' \
  2>/dev/null | python -m json.tool | head -60

echo ""
echo "================================================"
echo "Check if Craft Artists (27-1012.00) is in top positions"
