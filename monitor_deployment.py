#!/usr/bin/env python3
"""
Monitor Render deployment progress
Checks every 30 seconds until deployment succeeds or times out
"""

import requests
import time
from datetime import datetime

BACKEND_URL = "https://uh-pathfinder-backend.onrender.com"
CHECK_INTERVAL = 30  # seconds
MAX_WAIT = 600  # 10 minutes

def test_endpoint():
    """Test if the programs endpoint works"""
    try:
        url = f"{BACKEND_URL}/api/v1/occupations/17-2061.00/programs/summary"
        response = requests.get(url, timeout=20)
        return response.status_code, response.text[:100]
    except Exception as e:
        return None, str(e)

def main():
    print("=" * 70)
    print("MONITORING RENDER DEPLOYMENT")
    print("=" * 70)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Checking every {CHECK_INTERVAL} seconds")
    print(f"Max wait time: {MAX_WAIT // 60} minutes")
    print("=" * 70)
    print("\nPress Ctrl+C to stop monitoring\n")
    
    start_time = time.time()
    check_count = 0
    
    while time.time() - start_time < MAX_WAIT:
        check_count += 1
        elapsed = int(time.time() - start_time)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        print(f"[{timestamp}] Check #{check_count} (elapsed: {elapsed}s)", end=" ... ")
        
        status, response = test_endpoint()
        
        if status == 200:
            print(f"✓ SUCCESS! Status: {status}")
            print("\n" + "=" * 70)
            print("DEPLOYMENT COMPLETE!")
            print("=" * 70)
            print(f"Time taken: {elapsed // 60} minutes {elapsed % 60} seconds")
            print("\nBackend is now connected to the database!")
            print("\nNext steps:")
            print("1. Run: python test_deployment.py")
            print("2. Check encoding fixes are applied")
            print("3. Test frontend at: https://uhpathfinder.netlify.app")
            return True
            
        elif status == 500:
            print(f"✗ Still getting 500 error")
            
        elif status is None:
            print(f"⏳ Backend not responding yet ({response[:50]}...)")
            
        else:
            print(f"⚠ Status: {status}")
        
        if elapsed < MAX_WAIT - CHECK_INTERVAL:
            print(f"   Waiting {CHECK_INTERVAL} seconds before next check...")
            time.sleep(CHECK_INTERVAL)
        else:
            break
    
    print("\n" + "=" * 70)
    print("TIMEOUT REACHED")
    print("=" * 70)
    print(f"Deployment has been running for {MAX_WAIT // 60} minutes")
    print("\nPlease check Render dashboard:")
    print("1. Go to: https://dashboard.render.com/")
    print("2. Check your backend service status")
    print("3. Look for any deployment errors in the 'Events' tab")
    print("4. Check logs for Python errors")
    return False

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✋ Monitoring stopped by user")
        print("You can check manually by running: python debug_500.py")
