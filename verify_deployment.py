#!/usr/bin/env python3
"""
Post-deployment verification checklist for UH Pathfinder
Run after setting DATABASE_URL in Render
"""

import requests
import time
import sys

BACKEND_URL = "https://uh-pathfinder-backend.onrender.com"

def wait_for_deployment(max_wait=120):
    """Wait for Render to finish deploying"""
    print("=" * 60)
    print("WAITING FOR RENDER DEPLOYMENT")
    print("=" * 60)
    print(f"Will check every 10 seconds for up to {max_wait} seconds...")
    print("(Render typically takes 2-3 minutes to deploy)")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < max_wait:
        try:
            response = requests.get(f"{BACKEND_URL}/health", timeout=10)
            current_status = response.status_code
            
            if current_status != last_status:
                elapsed = int(time.time() - start_time)
                print(f"[{elapsed}s] Health check: {current_status}")
                last_status = current_status
            
            time.sleep(10)
            
        except Exception as e:
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed}s] Waiting... ({type(e).__name__})")
            time.sleep(10)
    
    print(f"\nFinished waiting. Proceeding with tests...")

def check_deployment_status():
    """Instructions for checking Render deployment status"""
    print("\n" + "=" * 60)
    print("MANUAL DEPLOYMENT CHECK")
    print("=" * 60)
    print("\nPlease verify in Render Dashboard:")
    print("1. Go to: https://dashboard.render.com/")
    print("2. Click on your backend service")
    print("3. Check the 'Events' tab - is deployment complete?")
    print("4. Check the 'Logs' tab - any errors?")
    print("\nLook for these in the logs:")
    print("  ✓ 'Application startup complete'")
    print("  ✗ Any Python tracebacks")
    print("  ✗ 'connection refused' errors")
    print("  ✗ 'No module named...' errors")
    
    response = input("\nIs deployment showing as 'Live' in Render? (y/n): ")
    return response.lower() == 'y'

def verify_database_connection():
    """Check if the database is accessible"""
    print("\n" + "=" * 60)
    print("DATABASE CONNECTION VERIFICATION")
    print("=" * 60)
    
    print("\nIn your psql terminal, run these queries:")
    print("-" * 60)
    print("-- 1. Verify connection works")
    print("SELECT current_database(), current_user;")
    print("\n-- 2. Check programs table")
    print("SELECT COUNT(*) FROM programs;")
    print("\n-- 3. Check for Mānoa encoding")
    print("SELECT name FROM programs WHERE name LIKE '%noa%' LIMIT 3;")
    print("-" * 60)
    
    response = input("\nDo all queries return data successfully? (y/n): ")
    return response.lower() == 'y'

def test_backend_with_db():
    """Test if backend can reach database"""
    print("\n" + "=" * 60)
    print("TESTING BACKEND → DATABASE CONNECTION")
    print("=" * 60)
    
    onet_code = "17-2061.00"
    url = f"{BACKEND_URL}/api/v1/occupations/{onet_code}/programs/summary"
    
    print(f"\nTesting: {url}")
    
    try:
        response = requests.get(url, timeout=30)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ SUCCESS! Backend is connected to database")
            data = response.json()
            print(f"\nPrograms returned: {len(data.get('programs', []))}")
            
            # Check encoding
            import json
            text = json.dumps(data)
            if 'Mānoa' in text:
                print("✓ Encoding appears correct (Mānoa found)")
            elif 'MÄ' in text:
                print("⚠ Warning: Old encoding detected (MÄnoa)")
            
            return True
            
        elif response.status_code == 500:
            print("✗ STILL GETTING 500 ERROR")
            print("\nPossible causes:")
            print("1. Deployment not complete - check Render dashboard")
            print("2. DATABASE_URL incorrect - verify in Render Environment tab")
            print("3. Database schema missing - need to run migrations?")
            print("4. Code error - check Render logs for Python traceback")
            return False
            
        else:
            print(f"✗ Unexpected status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"✗ Request failed: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("UH PATHFINDER - DEPLOYMENT VERIFICATION")
    print("=" * 60)
    print("\nThis script helps verify your Render deployment")
    print("after setting the DATABASE_URL environment variable.\n")
    
    # Step 1: Check deployment status
    deployment_live = check_deployment_status()
    
    if not deployment_live:
        print("\n⚠ Deployment not complete. Please wait and run this script again.")
        print("Render deployments typically take 2-3 minutes.")
        sys.exit(0)
    
    # Step 2: Verify database connection
    db_accessible = verify_database_connection()
    
    if not db_accessible:
        print("\n✗ Database connection issue detected")
        print("Please verify your DATABASE_URL is correct in Render")
        sys.exit(1)
    
    # Step 3: Test backend
    print("\n" + "=" * 60)
    print("FINAL TEST: Backend → Database")
    print("=" * 60)
    
    success = test_backend_with_db()
    
    if success:
        print("\n" + "=" * 60)
        print("✓✓✓ DEPLOYMENT SUCCESSFUL! ✓✓✓")
        print("=" * 60)
        print("\nYour backend is now connected to the database!")
        print("\nNext steps:")
        print("1. Test the frontend at: https://uhpathfinder.netlify.app")
        print("2. Complete an assessment")
        print("3. Verify program recommendations appear")
        print("4. Check for encoding issues (Mānoa, Hawaiʻi)")
    else:
        print("\n" + "=" * 60)
        print("✗ DEPLOYMENT ISSUE DETECTED")
        print("=" * 60)
        print("\nPlease check Render logs for detailed error messages")
        print("Common fixes:")
        print("- Verify DATABASE_URL includes password")
        print("- Check database allows connections from Render")
        print("- Ensure all dependencies in requirements.txt")
        print("- Verify latest code is pushed to GitHub")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user")
        sys.exit(0)
