# Render Backend Configuration Fix

## Problem
The backend on Render is trying to connect to localhost instead of the production database.

Error: `connection to server at "localhost" (::1), port 5432 failed`

## Solution
You need to set the DATABASE_URL environment variable in Render.

### Steps to Fix:

1. **Get your production database URL:**
   Based on your psql command, your database is at:
   ```
   Host: dpg-d4ed6m1r0fns73blnhu0-a.oregon-postgres.render.com
   User: uhpathfinderdb_user
   Database: uhpathfinderdb
   ```

2. **Format the DATABASE_URL:**
   The format should be:
   ```
   postgresql://USERNAME:PASSWORD@HOST:PORT/DATABASE
   ```
   
   For your database:
   ```
   postgresql://uhpathfinderdb_user:YOUR_PASSWORD@dpg-d4ed6m1r0fns73blnhu0-a.oregon-postgres.render.com:5432/uhpathfinderdb
   ```
   
   Replace `YOUR_PASSWORD` with your actual database password.

3. **Set in Render Dashboard:**
   - Go to https://dashboard.render.com/
   - Select your backend web service
   - Go to "Environment" tab
   - Add or update the environment variable:
     - Key: `DATABASE_URL`
     - Value: `postgresql://uhpathfinderdb_user:YOUR_PASSWORD@dpg-d4ed6m1r0fns73blnhu0-a.oregon-postgres.render.com:5432/uhpathfinderdb`
   - Click "Save Changes"
   - Render will automatically redeploy

4. **Alternative - Use Internal Connection:**
   If your database and backend are both on Render, you can use the internal connection string:
   - In your database dashboard, look for "Internal Database URL"
   - This is faster and free of egress charges
   - Copy that entire URL and use it as DATABASE_URL

### Finding Your Database Password:

If you don't have the password, you can find it in Render:
- Go to your database dashboard
- Look for "Connection String" or "External Database URL"
- Copy the entire URL (it includes the password)

### After Setting DATABASE_URL:

The backend will automatically redeploy. Wait 2-3 minutes, then test again:

```bash
python debug_500.py
```

The programs endpoint should now work!

### Notes:
- The DATABASE_URL must include the password
- Use the External URL if accessing from outside Render
- Use the Internal URL if both services are on Render (faster, free)
- After setting, Render will redeploy automatically
