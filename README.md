# SHOPIQ - Price Comparison Web App

SHOPIQ is a Flask-based price comparison website that helps users compare the price of a single product across multiple platforms. It provides a clean UI, filterable results, price history, and price-drop alerts.

## Features

- Compare product prices across multiple platforms
- Highlight the best available deal
- Filter by platform, price range, and rating
- View product price history
- Create price-drop alerts
- Autocomplete suggestions for search
- Cached and live search responses
- Responsive card-based frontend

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python, Flask, Flask-CORS |
| Frontend | HTML, CSS, JavaScript |
| Scraping | Requests, BeautifulSoup, optional Selenium |
| Charts | Chart.js |
| Storage | JSON files |
| Optional services | Redis, MongoDB, APScheduler |

## Project Structure

``text
JAVA PRICE COMPARISON/
├── app.py
├── routes.py
├── app.js
├── style.css
├── index.html
├── requirements.txt
├── amazon_scraper.py
├── flipkart_scraper.py
├── demo_scraper.py
├── base_scraper.py
├── search_coordinator.py
├── cache.py
├── deal_suggester.py
├── price_history.py
├── price_predictor.py
├── alerts.py
├── scheduler.py
├── test_api.py
├── docker-compose.yml
├── data/
├── logs/
├── __pycache__/
└── .vscode/
``

## Main Files

- `app.py` - Flask entry point and frontend/static route serving
- `routes.py` - API endpoints
- `index.html` - main frontend page
- `style.css` - website styling
- `app.js` - frontend logic and API integration
- `search_coordinator.py` - combines results from available scrapers
- `amazon_scraper.py` - Amazon search scraper
- `flipkart_scraper.py` - Flipkart search scraper
- `demo_scraper.py` - mock/demo scraper for fallback testing
- `price_history.py` - price history storage and retrieval
- `alerts.py` - price alert creation and management
- `cache.py` - cache layer
- `scheduler.py` - background scheduler support
- `test_api.py` - API tests

## Run Locally

### PowerShell

``powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
``

Open:

``text
http://localhost:5000
``

## Run In VS Code

This project includes VS Code configuration in `.vscode/`.

Steps:

1. Open the folder in VS Code
2. Open the terminal
3. Run:

cd path 
.venv\Scripts\activate
python app.py


Or use:

1. `Ctrl+Shift+B` for tasks
2. `F5` for Run/Debug

## Available Routes

### Frontend Routes

- `GET /`
- `GET /static/css/style.css`
- `GET /static/js/app.js`
- `GET /health`

### API Routes

- `GET /api/search`
- `GET /api/product/<product_id>/history`
- `POST /api/alerts`
- `GET /api/alerts`
- `DELETE /api/alerts/<alert_id>`
- `GET /api/suggest`
- `GET /api/best-deal`

## Search Flow

1. User enters a product name
2. API receives the query at `/api/search`
3. Scrapers run and collect results
4. Results are filtered, sorted, and merged
5. Best deal is identified
6. Price history is stored
7. Response is shown in the frontend

## Data Storage

- `data/price_history/` stores price history snapshots
- `data/alerts.json` stores user alerts
- `logs/app.log` stores application logs

## Notes

- Some packages in `requirements.txt` are optional or version-sensitive depending on Python version
- The app can still run locally even if optional services like Redis or MongoDB are not configured
- Demo scraper support is available for local development and fallback behavior

## Deployment

### Deploy on Render (Free Tier)

Your app is already configured for Render deployment with `render.yaml`.

**Prerequisites:**
- GitHub account
- Render account (free): https://render.com
- SerpAPI key (optional): https://serpapi.com

**Steps:**

1. **Go to Render Dashboard**
   - Visit: https://dashboard.render.com
   - Sign up / Log in with your GitHub account

2. **Create a New Blueprint**
   - Click **New +** then **Blueprint**
   - Connect your GitHub account if not already connected
   - Select repository: **Taniya-butola/ShopIQ**
   - Render will auto-detect your `render.yaml` file
   - Click **Apply**

3. **Set Environment Variables**
   
   | Key | Value |
   |-----|-------|
   | `SERPAPI_API_KEY` | Your SerpAPI key (get free at serpapi.com) |

   > Note: Redis is included automatically in your `render.yaml` (free tier)

4. **Deploy**
   - Click **Deploy**
   - Wait 3-5 minutes for build to complete
   - Your app will be live at: `https://shopiq.onrender.com`

5. **Verify Deployment**
   - Visit: `https://your-app-name.onrender.com/health`
   - Should return: `{"status": "ok", "service": "PriceWise API"}`

**Free Tier Limits:**

| Service | Limit |
|---------|-------|
| Render Web | 750 hours/month, spins down after 15 min inactivity |
| Render Redis | 25MB storage |

**Troubleshooting:**

- **App spins down:** Free tier apps spin down after 15 min inactivity. First request takes ~30s to wake up.
- **Build fails:** Check `requirements.txt` for incompatible packages. View build logs in Render dashboard.
- **Scrapers timeout:** Free tier has timeout limits. Reduce `MAX_SCRAPERS` to 2-3.
