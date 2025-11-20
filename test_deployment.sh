#!/bin/bash

# UH Pathfinder Deployment Test Script
# Tests: Frontend → Backend → Database connections

echo "=========================================="
echo "UH PATHFINDER DEPLOYMENT TEST"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BACKEND_URL="https://uh-pathfinder-backend.onrender.com"
FRONTEND_URL="https://uhpathfinder.netlify.app"

echo "Testing deployment at:"
echo "  Backend:  $BACKEND_URL"
echo "  Frontend: $FRONTEND_URL"
echo ""

# Test 1: Backend Health Check
echo "=========================================="
echo "TEST 1: Backend Health Check"
echo "=========================================="
echo -n "Checking backend health endpoint... "
HEALTH_RESPONSE=$(curl -s -m 30 "$BACKEND_URL/health" 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Backend is responding${NC}"
    echo "Response: $HEALTH_RESPONSE"
else
    echo -e "${RED}✗ Backend not responding (timeout or error)${NC}"
    echo "Error: $HEALTH_RESPONSE"
fi
echo ""

# Test 2: Backend API Root
echo "=========================================="
echo "TEST 2: Backend API Root"
echo "=========================================="
echo -n "Checking API root... "
API_ROOT=$(curl -s -m 30 "$BACKEND_URL/api/v1/" 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ API root responding${NC}"
    echo "Response: $API_ROOT"
else
    echo -e "${RED}✗ API root not responding${NC}"
    echo "Error: $API_ROOT"
fi
echo ""

# Test 3: RIASEC Assessment Endpoint
echo "=========================================="
echo "TEST 3: RIASEC Assessment Endpoint"
echo "=========================================="
echo -n "Testing RIASEC assessment... "
RIASEC_PAYLOAD='{"riasec_scores":{"R":5,"I":4,"A":3,"S":2,"E":1,"C":0}}'
RIASEC_RESPONSE=$(curl -s -m 30 -X POST "$BACKEND_URL/api/v1/assessment/riasec" \
  -H "Content-Type: application/json" \
  -d "$RIASEC_PAYLOAD" 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ RIASEC endpoint responding${NC}"
    echo "Sample response (first 200 chars): ${RIASEC_RESPONSE:0:200}..."
else
    echo -e "${RED}✗ RIASEC endpoint failed${NC}"
    echo "Error: $RIASEC_RESPONSE"
fi
echo ""

# Test 4: Occupation Programs Endpoint
echo "=========================================="
echo "TEST 4: Occupation Programs Endpoint"
echo "=========================================="
ONET_CODE="17-2061.00" # Computer Hardware Engineers
echo -n "Testing occupation programs for $ONET_CODE... "
PROGRAMS_RESPONSE=$(curl -s -m 30 "$BACKEND_URL/api/v1/occupations/$ONET_CODE/programs/summary" 2>&1)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Programs endpoint responding${NC}"
    echo "Sample response (first 300 chars): ${PROGRAMS_RESPONSE:0:300}..."
else
    echo -e "${RED}✗ Programs endpoint failed${NC}"
    echo "Error: $PROGRAMS_RESPONSE"
fi
echo ""

# Test 5: Check for encoding issues in response
echo "=========================================="
echo "TEST 5: Encoding Check (Mānoa, Hawaiʻi)"
echo "=========================================="
echo -n "Checking for proper Hawaiian character encoding... "
if echo "$PROGRAMS_RESPONSE" | grep -q "Mānoa"; then
    echo -e "${GREEN}✓ 'Mānoa' found with correct encoding${NC}"
elif echo "$PROGRAMS_RESPONSE" | grep -q "MÄ.*noa"; then
    echo -e "${RED}✗ 'Mānoa' has encoding issues (shows as MÄnoa)${NC}"
else
    echo -e "${YELLOW}⚠ No 'Mānoa' found in response${NC}"
fi

if echo "$PROGRAMS_RESPONSE" | grep -q "Hawaiʻi"; then
    echo -e "${GREEN}✓ 'Hawaiʻi' found with correct ʻokina${NC}"
elif echo "$PROGRAMS_RESPONSE" | grep -q "Hawai.*i"; then
    echo -e "${YELLOW}⚠ 'Hawaiʻi' might have encoding issues${NC}"
fi
echo ""

# Test 6: Frontend accessibility
echo "=========================================="
echo "TEST 6: Frontend Accessibility"
echo "=========================================="
echo -n "Checking if frontend is accessible... "
FRONTEND_RESPONSE=$(curl -s -m 30 -I "$FRONTEND_URL/assessment" 2>&1)
if [ $? -eq 0 ] && echo "$FRONTEND_RESPONSE" | grep -q "200\|301\|302"; then
    echo -e "${GREEN}✓ Frontend is accessible${NC}"
else
    echo -e "${RED}✗ Frontend not accessible${NC}"
    echo "Response: $FRONTEND_RESPONSE"
fi
echo ""

# Test 7: CORS headers
echo "=========================================="
echo "TEST 7: CORS Configuration"
echo "=========================================="
echo -n "Checking CORS headers from backend... "
CORS_RESPONSE=$(curl -s -m 30 -I -X OPTIONS "$BACKEND_URL/api/v1/assessment/riasec" \
  -H "Origin: $FRONTEND_URL" \
  -H "Access-Control-Request-Method: POST" 2>&1)
if echo "$CORS_RESPONSE" | grep -q "Access-Control-Allow-Origin"; then
    echo -e "${GREEN}✓ CORS headers present${NC}"
    echo "$CORS_RESPONSE" | grep "Access-Control"
else
    echo -e "${RED}✗ CORS headers missing${NC}"
fi
echo ""

echo "=========================================="
echo "TEST COMPLETE"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Review any failed tests above"
echo "2. Open browser DevTools on $FRONTEND_URL/assessment"
echo "3. Check Network tab for API calls"
echo "4. Check Console for JavaScript errors"
echo ""
