import asyncio
import urllib.parse
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import requests
from playwright.async_api import async_playwright
import aiohttp
import os

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

async def get_free_proxy():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                'https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=yes&anonymity=elite'
            ) as resp:
                text = await resp.text()
                proxies = text.strip().split('\n')
                return proxies[0] if proxies else None
    except Exception as e:
        print(f"Proxy fetch error: {e}")
        return None

async def render_with_playwright(url):
    try:
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                if "youtube.com" in url:
                    await page.set_extra_http_headers({
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                    })
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state('networkidle')
                html = await page.content()
                await browser.close()
                return html
            except:
                print("Trying with proxy...")
                proxy = await get_free_proxy()
                if not proxy:
                    raise Exception("No proxy found")
                browser = await p.chromium.launch(
                    headless=True,
                    proxy={"server": f"http://{proxy}"}
                )
                context = await browser.new_context()
                page = await context.new_page()
                await page.goto(url, timeout=60000)
                await page.wait_for_load_state('networkidle')
                html = await page.content()
                await browser.close()
                with open("proxy_usage.log", "a", encoding="utf-8") as log:
                    log.write(f"[{url}] used proxy: {proxy}\n")
                return html
    except Exception as e:
        print(f"Playwright error: {e}")
        return None

def rewrite_html(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    proxy_prefix = "https://ivr-ai-server.onrender.com/scrape?url="
    for tag in soup.find_all("a", href=True):
        orig = tag["href"]
        new_url = urljoin(base_url, orig)
        tag["href"] = proxy_prefix + urllib.parse.quote(new_url, safe='')
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

    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url

    if use_browser or is_dynamic(url):
        html = asyncio.run(render_with_playwright(url))
    else:
        html = fetch_with_requests(url)

    if html is None:
        return jsonify({"error": "Failed to fetch content"}), 500

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
