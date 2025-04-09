import asyncio
import urllib.parse
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import requests
from playwright.async_api import async_playwright

app = Flask(__name__)

# רשימת אתרים שיש לחשוב עליהם כ"דינמיים" (ניתן להרחיב)
DYNAMIC_SITES = ['youtube.com', 'twitter.com', 'tiktok.com', 'instagram.com']

def is_dynamic(url: str) -> bool:
    domain = urlparse(url).netloc
    return any(d in domain for d in DYNAMIC_SITES)

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
            context = await browser.new_context()
            page = await context.new_page()
            # במידה ומדובר ביוטיוב, נוסיף User-Agent מותאם
            if "youtube.com" in url:
                await page.set_extra_http_headers({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                })
            await page.goto(url, timeout=60000)
            # מחכים למצב 'networkidle' כדי לוודא שהדף נטען במלואו
            await page.wait_for_load_state('networkidle')
            html = await page.content()
            await browser.close()
            return html
    except Exception as e:
        print(f"Playwright error: {e}")
        return None

def rewrite_html(html, base_url):
    """
    עיבוד ה־HTML כך שכל הקישורים (ואת פעולות הטפסים) יעברו דרך השרת שלך.
    """
    soup = BeautifulSoup(html, "html.parser")
    proxy_prefix = "https://ivr-ai-server.onrender.com/scrape?url="
    # עדכון קישורים (anchor tags)
    for tag in soup.find_all("a", href=True):
        orig = tag["href"]
        # משלימים כתובת יחסית לכתובת הבסיס
        new_url = urljoin(base_url, orig)
        tag["href"] = proxy_prefix + urllib.parse.quote(new_url, safe='')
    # עדכון טפסים (form action)
    for tag in soup.find_all("form", action=True):
        orig = tag["action"]
        new_url = urljoin(base_url, orig)
        tag["action"] = proxy_prefix + urllib.parse.quote(new_url, safe='')
    return str(soup)

@app.route("/scrape", methods=["GET"])
def scrape():
    url = request.args.get("url")
    use_browser = request.args.get("use_browser", "0") == "1"
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    # אם לא מופיע "http", נניח https
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    # בחירה אם להשתמש ב־Playwright או ב־Requests:
    if use_browser or is_dynamic(url):
        html = asyncio.run(render_with_playwright(url))
    else:
        html = fetch_with_requests(url)

    if html is None:
        return jsonify({"error": "Failed to fetch content"}), 500

    # עיבוד מחדש של ה־HTML כך שהקישורים יעברו דרך השרת
    rewritten = rewrite_html(html, url)
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string if soup.title else "No title"

    return jsonify({
        "url": url,
        "title": title,
        "length": len(rewritten),
        "preview": rewritten[:500],
        "content": rewritten
    })

@app.route("/")
def index():
    # דף הבית – ממשק משתמש פשוט עם טופס להזנת כתובת אתר,
    # לחיצה תפתח את התוצאה בחלון חדש.
    return """
    <!DOCTYPE html>
    <html lang="he" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>Scraper - שרת פרוקסי</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; background: #f4f4f4; }
            .container { max-width: 500px; margin: auto; background: white; padding: 20px; border-radius: 12px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            input, button, label { font-size: 1em; padding: 0.5em; margin: 0.3em 0; width: 100%; }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Scraper - שרת פרוקסי</h2>
            <form onsubmit="event.preventDefault(); smartView();">
                <label>הכנס כתובת אתר:</label>
                <input type="text" id="urlInput" placeholder="https://example.com" required>
                <label>
                    <input type="checkbox" id="use_browser"> השתמש בדפדפן (ללאקייה אתרים דינמיים)
                </label>
                <button type="submit">פתח בחלון חדש</button>
            </form>
        </div>
        <script>
            async function smartView() {
                const url = document.getElementById("urlInput").value;
                const useBrowser = document.getElementById("use_browser").checked ? "&use_browser=1" : "";
                try {
                    const res = await fetch("/scrape?url=" + encodeURIComponent(url) + useBrowser);
                    const data = await res.json();
                    if (data.content) {
                        // פותח חלון חדש ומזריק אליו את ה־HTML שעבר עיבוד
                        const newWindow = window.open("", "_blank");
                        newWindow.document.open();
                        newWindow.document.write(data.content);
                        newWindow.document.close();
                    } else {
                        alert("שגיאה: " + (data.error || "לא הוחזר תוכן"));
                    }
                } catch (err) {
                    alert("שגיאה בשליפת התוכן: " + err);
                }
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    app.run(debug=True)
