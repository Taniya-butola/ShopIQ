# PriceWise - Render Deployment Guide

This guide deploys PriceWise to Render (free tier) with MongoDB Atlas (free).

---

## Prerequisites

- GitHub account
- Render account (free): https://render.com
- MongoDB Atlas account (free): https://mongodb.com/atlas

---

## Step 1: Push to GitHub

```bash
# Initialize git (if not already)
git init

git add .
git commit -m "Initial commit"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/pricewise.git
git branch -M main
git push -u origin main
```

---

## Step 2: Setup MongoDB Atlas (Free)

1. Go to: https://mongodb.com/atlas
2. Create free account
3. Create a **Free M0 Cluster**
4. Create database user:
   - Database Access → Add User
   - Username: `pricewise`
   - Password: (generate and save it)
   - Role: `readWriteAnyDatabase`
5. Whitelist all IPs (for Render):
   - Network Access → Add IP → Allow Access from Anywhere
6. Get connection string:
   - Connect → Connect your application
   - Driver: Python
   - Copy the connection string
   - Replace `<password>` with your password

Connection string looks like:
```
mongodb+srv://pricewise:YOUR_PASSWORD@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
```

---

## Step 3: Deploy on Render

### Option A: Using render.yaml (Blueprint)

1. Go to: https://dashboard.render.com
2. Click **New** → **Blueprint**
3. Connect your GitHub repo
4. Render will detect `render.yaml`
5. Click **Apply**
6. Add environment variables:
   - `MONGO_URI`: Paste your MongoDB Atlas connection string
   - `SERPAPI_API_KEY`: Your SerpAPI key

### Option B: Manual Setup (More Control)

#### 3a. Create Redis (Free)

1. Render Dashboard → **New** → **Redis**
2. Name: `pricewise-redis`
3. Plan: **Free**
4. Click **Create Redis**
5. Copy the Internal Redis URL (e.g., `redis://red-xxxxx.render.com:6379/0`)

#### 3b. Create Web Service (Free)

1. Render Dashboard → **New** → **Web Service**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `pricewise`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:create_app() --bind 0.0.0.0:$PORT --workers 2 --timeout 120`
   - **Plan**: Free

4. Add Environment Variables:
   | Key | Value |
   |-----|-------|
   | `SECRET_KEY` | (click Generate) |
   | `MONGO_URI` | Your MongoDB Atlas connection string |
   | `REDIS_URL` | Your Render Redis URL |
   | `SERPAPI_API_KEY` | Your SerpAPI key |
   | `SERPAPI_GL` | `in` |
   | `SERPAPI_HL` | `en` |

5. Click **Create Web Service**

---

## Step 4: Verify Deployment

1. Wait for build to complete (2-5 minutes)
2. Check logs for any errors
3. Visit your app at: `https://pricewise.onrender.com`
4. Test the health endpoint: `https://pricewise.onrender.com/health`

---

## Free Tier Limits

| Service | Limit |
|---------|-------|
| Render Web | 750 hours/month, spins down after inactivity |
| Render Redis | 25MB storage |
| MongoDB Atlas | 512MB storage |

---

## Troubleshooting

### App spins down on free tier
Free tier spins down after 15 min inactivity. First request takes ~30s to wake up.

### Database connection fails
- Check MongoDB Atlas IP whitelist (allow all: `0.0.0.0/0`)
- Verify connection string password
- Check database user permissions

### Build fails
- Check `requirements.txt` for incompatible packages
- View build logs in Render dashboard

### Scrapers timeout
- Free tier has 60s timeout limit
- Reduce `MAX_SCRAPERS` to 2-3

---

## Your App URLs

After deployment:
- Main: `https://YOUR_APP_NAME.onrender.com`
- Health: `https://YOUR_APP_NAME.onrender.com/health`
- API: `https://YOUR_APP_NAME.onrender.com/api/search?q=iphone`

---

## Quick Commands

| Task | Command/Action |
|------|----------------|
| View logs | Render Dashboard → Your Service → Logs |
| Restart | Render Dashboard → Your Service → Manual Deploy → Deploy latest |
| Update env vars | Render Dashboard → Your Service → Environment |
| Check status | Render Dashboard → Your Service → Events |
