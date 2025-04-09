from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import requests
import asyncio
from playwright.async_api import async_playwright

app = Flask(__name__)

# רשימה של דומיינים שידועים כ"דינמיים"
DYNAMIC_SITES = ['youtube.com', 'twitter.com', 'tiktok.com', 'instagram.com']

def is_dynamic(url: str) -> bool:
    domain = urlparse(url).netloc
    return any(d in domain for d in DYNAMIC_SITES)
@app.route("/")
def index():
    return """
    <!DOCTYPE html>
    <html lang="he" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>שרת פרוקסי - Scraper</title>
        <style>
            body { font-family: sans-serif; margin: 40px; background: #f4f4f4; }
            input, select, button { font-size: 1em; padding: 0.5em; margin: 0.3em 0; width: 100%; }
            .container { max-width: 500px; margin: auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            pre { background: #eee; padding: 10px; border-radius: 8px; white-space: pre-wrap; max-height: 300px; overflow-y: auto; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Scraper - שרת פרוקסי</h2>
            <label>הכנס כתובת אתר:</label>
            <input type="text" id="url" placeholder="https://example.com">
            <label><input type="checkbox" id="use_browser"> השתמש בדפדפן (Playwright)</label>
            <button onclick="scrape()">שלח</button>
            <h3>תוצאה:</h3>
            <pre id="result">אין עדיין תוצאה...</pre>
        </div>
        <script>
            async function scrape() {
                const url = document.getElementById("url").value;
                const useBrowser = document.getElementById("use_browser").checked ? "&use_browser=1" : "";
                const resBox = document.getElementById("result");
                resBox.textContent = "טוען...";
                try {
                    const res = await fetch(`/scrape?url=${encodeURIComponent(url)}${useBrowser}`);
                    const data = await res.json();
                    resBox.textContent = JSON.stringify(data, null, 2);
                } catch (err) {
                    resBox.textContent = "שגיאה: " + err;
                }
            }
        </script>
    </body>
    </html>
    """

@app.route("/scrape", methods=["GET"])
def scrape():
    url = request.args.get("url")
    use_browser = request.args.get("use_browser", "0") == "1"
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    if use_browser or is_dynamic(url):
        html = asyncio.run(render_with_playwright(url))
    else:
        html = fetch_with_requests(url)

    if html is None:
        return jsonify({"error": "Failed to fetch content"}), 500

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string if soup.title else "No title"
    return jsonify({
        "url": url,
        "title": title,
        "length": len(html),
        "preview": html[:500]
    })

def fetch_with_requests(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Requests error: {e}")
        return None

async def render_with_playwright(url):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=15000)
            await page.wait_for_timeout(3000)  # תן לעמוד זמן להיטען
            html = await page.content()
            await browser.close()
            return html
    except Exception as e:
        print(f"Playwright error: {e}")
        return None

