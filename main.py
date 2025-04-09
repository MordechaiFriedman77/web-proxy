from flask import Flask, request, jsonify, Response, send_from_directory
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import requests
import asyncio
from playwright.async_api import async_playwright

app = Flask(__name__)

# רשימה של דומיינים שמוכרים כ"עבור דפים דינמיים"
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
            page = await browser.new_page()
            page.set_default_timeout(30000)
            await page.goto(url)
            await page.wait_for_load_state('networkidle')
            html = await page.content()
            await browser.close()
            return html
    except Exception as e:
        print(f"Playwright error: {e}")
        return None

@app.route("/scrape", methods=["GET"])
def scrape():
    url = request.args.get("url")
    use_browser = request.args.get("use_browser", "0") == "1"
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    # בחר אם להשתמש ב־Playwright או ב־Requests:
    if use_browser or is_dynamic(url):
        html = asyncio.run(render_with_playwright(url))
    else:
        html = fetch_with_requests(url)

    if html is None:
        return jsonify({"error": "Failed to fetch content"}), 500

    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string if soup.title else "No title"

    # נשלח חזרה את כל תוכן הדף בשדה content
    return jsonify({
        "url": url,
        "title": title,
        "length": len(html),
        "preview": html[:500],
        "content": html
    })

@app.route("/")
def index():
    # דף הבית – ממשק משתמש פשוט עם טופס והסברים
    return """
    <!DOCTYPE html>
    <html lang="he" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <title>שרת פרוקסי - דף הבית</title>
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
                    <input type="checkbox" id="use_browser"> השתמש בדפדפן (לאתרים דינמיים)
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
                        // פותח חלון חדש ומזריק את ה-HTML שהתקבל
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
