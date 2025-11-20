#!/usr/bin/env python3
"""Debug the 500 error from the programs endpoint"""

import requests
import json

BACKEND_URL = "https://uh-pathfinder-backend.onrender.com"

def test_programs_endpoint_detailed():
    """Test with detailed error reporting"""
    print("=" * 60)
    print("DEBUGGING PROGRAMS ENDPOINT 500 ERROR")
    print("=" * 60)
    
    onet_code = "17-2061.00"  # Computer Hardware Engineers
    url = f"{BACKEND_URL}/api/v1/occupations/{onet_code}/programs/summary"
    
    print(f"\nTesting URL: {url}")
    print("Sending request...")
    
    try:
        response = requests.get(url, timeout=30)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"\nResponse Text (first 500 chars):")
        print(response.text[:500])
        
        if response.status_code == 500:
            print("\n" + "=" * 60)
            print("500 ERROR DETECTED")
            print("=" * 60)
            print("\nFull response:")
            print(response.text)
            
            # Try to parse as JSON for error details
            try:
                error_data = response.json()
                print("\nParsed error details:")
                print(json.dumps(error_data, indent=2))
            except:
                print("\nCouldn't parse response as JSON")
        
        elif response.status_code == 200:
            print("\n✓ Success! Let's check the data...")
            data = response.json()
            print(f"\nPrograms count: {len(data.get('programs', []))}")
            
            # Check encoding
            text = json.dumps(data)
            if 'Mānoa' in text:
                print("✓ 'Mānoa' encoding correct")
            elif 'MÄ' in text:
                print("✗ 'Mānoa' encoding incorrect (shows as MÄnoa)")
            
            # Show sample
            if data.get('programs'):
                print(f"\nSample program:")
                prog = data['programs'][0]
                print(f"  Name: {prog.get('name')}")
                print(f"  Degree: {prog.get('degree_type')}")
                print(f"  Duration: {prog.get('duration_years')} years")
    
    except requests.exceptions.Timeout:
        print("\n✗ Request timed out (30 seconds)")
    except requests.exceptions.ConnectionError as e:
        print(f"\n✗ Connection error: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {type(e).__name__}: {e}")

def test_different_occupations():
    """Try different occupation codes to see if it's specific to one"""
    print("\n" + "=" * 60)
    print("TESTING MULTIPLE OCCUPATION CODES")
    print("=" * 60)
    
    test_codes = [
        ("17-2061.00", "Computer Hardware Engineers"),
        ("15-1252.00", "Software Developers"),
        ("29-1141.00", "Registered Nurses"),
        ("11-9013.00", "Farmers, Ranchers, and Other Agricultural Managers"),
    ]
    
    for onet_code, title in test_codes:
        url = f"{BACKEND_URL}/api/v1/occupations/{onet_code}/programs/summary"
        print(f"\nTesting: {title} ({onet_code})")
        
        try:
            response = requests.get(url, timeout=15)
            print(f"  Status: {response.status_code}", end="")
            
            if response.status_code == 200:
                data = response.json()
                print(f" - Programs: {len(data.get('programs', []))}")
            elif response.status_code == 500:
                print(" - ✗ 500 ERROR")
            else:
                print(f" - {response.text[:100]}")
                
        except Exception as e:
            print(f"  ✗ Error: {e}")

def check_base_endpoints():
    """Check if other endpoints work"""
    print("\n" + "=" * 60)
    print("CHECKING OTHER ENDPOINTS")
    print("=" * 60)
    
    endpoints = [
        "/health",
        "/api/v1/",
    ]
    
    for endpoint in endpoints:
        url = f"{BACKEND_URL}{endpoint}"
        print(f"\nTesting: {url}")
        try:
            response = requests.get(url, timeout=10)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                print(f"  Response: {response.text[:200]}")
        except Exception as e:
            print(f"  ✗ Error: {e}")

if __name__ == "__main__":
    print("\nUH PATHFINDER - 500 ERROR DEBUG SCRIPT")
    print("This will help identify why the programs endpoint is failing\n")
    
    check_base_endpoints()
    test_programs_endpoint_detailed()
    test_different_occupations()
    
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print("1. Check Render dashboard logs at:")
    print("   https://dashboard.render.com/")
    print("2. Look for Python tracebacks or database errors")
    print("3. Verify environment variables are set (DATABASE_URL)")
    print("4. Check if latest code is deployed (git push)")
    print("5. If database connection issue, verify pg connection string")
