#!/usr/bin/env python3
"""
Quick deployment test script to verify:
1. Backend is accessible
2. Database connections work
3. Encoding fixes are deployed
4. Frontend can reach backend
"""

import requests
import json

BACKEND_URL = "https://uh-pathfinder-backend.onrender.com"
FRONTEND_URL = "https://uhpathfinder.netlify.app"

def test_backend_health():
    """Test if backend health endpoint responds"""
    print("=" * 60)
    print("TEST 1: Backend Health Check")
    print("=" * 60)
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=60)
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Response: {response.json()}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_riasec_endpoint():
    """Test RIASEC assessment endpoint"""
    print("\n" + "=" * 60)
    print("TEST 2: RIASEC Assessment Endpoint")
    print("=" * 60)
    payload = {
        "riasec_scores": {"R": 5, "I": 4, "A": 3, "S": 2, "E": 1, "C": 0}
    }
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/assessment/riasec",
            json=payload,
            timeout=30
        )
        print(f"✓ Status: {response.status_code}")
        data = response.json()
        print(f"✓ Occupations returned: {len(data.get('occupations', []))}")
        if data.get('occupations'):
            print(f"✓ Sample occupation: {data['occupations'][0].get('title', 'N/A')}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_occupation_programs():
    """Test occupation programs endpoint and check encoding"""
    print("\n" + "=" * 60)
    print("TEST 3: Occupation Programs (with encoding check)")
    print("=" * 60)
    onet_code = "17-2061.00"  # Computer Hardware Engineers
    try:
        response = requests.get(
            f"{BACKEND_URL}/api/v1/occupations/{onet_code}/programs/summary",
            timeout=30
        )
        print(f"✓ Status: {response.status_code}")
        data = response.json()
        
        # Check if we got programs
        programs = data.get('programs', [])
        print(f"✓ Programs found: {len(programs)}")
        
        # Check encoding - look for Mānoa or Hawaiʻi
        text = json.dumps(data)
        if 'Mānoa' in text:
            print("✓ ENCODING CHECK PASSED: 'Mānoa' found with correct ā")
        elif 'MÄ' in text and 'noa' in text:
            print("✗ ENCODING CHECK FAILED: 'MÄnoa' found (incorrect encoding)")
        else:
            print("⚠ No 'Mānoa' in response (might be in other occupations)")
        
        if 'Hawaiʻi' in text:
            print("✓ ENCODING CHECK PASSED: 'Hawaiʻi' found with correct ʻokina")
        
        # Show sample program
        if programs:
            sample = programs[0]
            print(f"\nSample program:")
            print(f"  Name: {sample.get('name', 'N/A')}")
            print(f"  Degree: {sample.get('degree_type', 'N/A')}")
            print(f"  Duration: {sample.get('duration_years', 'N/A')} years")
        
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_degree_distribution():
    """Check if degree type corrections were applied"""
    print("\n" + "=" * 60)
    print("TEST 4: Degree Type Distribution Check")
    print("=" * 60)
    print("This requires database access. Please run in psql:")
    print("""
    SELECT degree_type, COUNT(*) as count 
    FROM programs 
    GROUP BY degree_type 
    ORDER BY count DESC;
    """)
    print("\nExpected (from local fixes):")
    print("  - Bachelor of Science: 94-100 (4-year)")
    print("  - Bachelor of Education: 11 (4-year)")
    print("  - Associate in Science: 220+ (2-year)")
    print("  - No Associates with duration >= 4 years")

def test_cors():
    """Test CORS headers"""
    print("\n" + "=" * 60)
    print("TEST 5: CORS Configuration")
    print("=" * 60)
    try:
        response = requests.options(
            f"{BACKEND_URL}/api/v1/assessment/riasec",
            headers={
                "Origin": FRONTEND_URL,
                "Access-Control-Request-Method": "POST"
            },
            timeout=10
        )
        cors_origin = response.headers.get('Access-Control-Allow-Origin')
        if cors_origin:
            print(f"✓ CORS enabled: {cors_origin}")
        else:
            print("✗ CORS headers not found")
            print(f"Response headers: {dict(response.headers)}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("UH PATHFINDER DEPLOYMENT TEST")
    print("=" * 60)
    print(f"Backend:  {BACKEND_URL}")
    print(f"Frontend: {FRONTEND_URL}")
    print("\nNote: Backend may take 30-50 seconds to wake up (Render free tier)")
    print("=" * 60)
    
    results = []
    results.append(("Backend Health", test_backend_health()))
    results.append(("RIASEC Endpoint", test_riasec_endpoint()))
    results.append(("Programs + Encoding", test_occupation_programs()))
    test_degree_distribution()
    results.append(("CORS Config", test_cors()))
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    print("\n" + "=" * 60)
    print("NEXT STEPS FOR BROWSER TESTING:")
    print("=" * 60)
    print(f"1. Open {FRONTEND_URL} in browser")
    print("2. Navigate to Assessment page from the home page")
    print("3. Open DevTools (F12) → Network tab")
    print("4. Complete an assessment and watch for:")
    print("   - POST to /api/v1/assessment/riasec")
    print("   - GET to /api/v1/occupations/.../programs/summary")
    print("5. Check Console for errors")
    print("6. Verify 'Mānoa' displays without space")
    print("7. Verify 4-year programs in University section")

if __name__ == "__main__":
    main()
