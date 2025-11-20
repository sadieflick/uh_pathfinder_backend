# Render Environment Variables Checklist

## Check These in Render Dashboard:

1. **Go to:** https://dashboard.render.com/
2. **Select:** Your backend web service
3. **Click:** "Environment" tab
4. **Verify DATABASE_URL is set to:**

```
postgresql://uhpathfinderdb_user:YOUR_PASSWORD@dpg-d4ed6m1r0fns73blnhu0-a.oregon-postgres.render.com:5432/uhpathfinderdb
```

## Common Issues:

### Issue 1: Using localhost
If DATABASE_URL shows `localhost` or `127.0.0.1`, the backend is trying to connect locally instead of to production database.

**Fix:** Update DATABASE_URL to the production database connection string

### Issue 2: Using Internal URL when you need External
If your database and backend are on different Render accounts or regions, you need the External URL.

**External URL format:**
```
postgresql://USER:PASSWORD@dpg-XXXXX-a.oregon-postgres.render.com:5432/DATABASE
```

**Internal URL format (only if both services on same Render account):**
```
postgresql://USER:PASSWORD@dpg-XXXXX/DATABASE
```

### Issue 3: Cached environment variables
After changing DATABASE_URL, Render needs to redeploy.

**Check:**
- Does the "Events" tab show a recent deployment after you changed DATABASE_URL?
- If not, click "Manual Deploy" → "Deploy latest commit"

## Quick Test:

Run this to check if backend is hitting the production database:

```bash
# Check the logs from Render
# Look for: "connection to server at localhost" (BAD)
# vs: "connection to server at dpg-..." (GOOD)
```

## Your Production Database Details:

Host: `dpg-d4ed6m1r0fns73blnhu0-a.oregon-postgres.render.com`
Port: `5432`
Database: `uhpathfinderdb`
User: `uhpathfinderdb_user`
Password: `[You need to get this from Render database dashboard]`

## To Get the Correct DATABASE_URL:

1. Go to your **Database** in Render dashboard (not backend)
2. Look for "External Connection String" or "Connection String"
3. Copy the entire string (includes password)
4. Paste that into your backend's DATABASE_URL environment variable
5. Save and wait for redeploy (2-5 minutes with paid plan)

## Verify It's Working:

After setting and redeploying, check the Render logs. You should see:
- ✅ "Application startup complete" (no database errors)
- ✅ Successful API requests in logs
- ✗ NO "connection to server at localhost" errors
