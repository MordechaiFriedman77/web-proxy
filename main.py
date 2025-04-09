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
<html lang="iw">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>פרוקסי - דף הבית</title>
</head>
<body>
    <h1>ברוך הבא לפרוקסי שלך!</h1>
    <form onsubmit="event.preventDefault(); scrape();">
        <label for="url">הכנס כתובת אתר:</label>
        <input type="text" id="url" placeholder="הכנס כתובת URL" required />
        <label>
            <input type="checkbox" id="use_browser" /> השתמש בבראוזר (לצורך אתרים כמו YouTube)
        </label>
        <button type="submit">שלח</button>
    </form>
    <h2>תוצאה:</h2>
    <pre id="result">לא בוצעה שאילתה עדיין...</pre>

    <!-- כפתורים להורדה -->
    <button id="download_html" onclick="downloadHtmlFile()" style="display:none;">📄 הורד כקובץ HTML</button>
    <button id="download_pdf" onclick="downloadPdfFile()" style="display:none;">🖨️ הדפס או שמור כ-PDF</button>

    <script>
        let latestHtml = "";

        async function scrape() {
            const url = document.getElementById("url").value;
            const useBrowser = document.getElementById("use_browser").checked ? "&use_browser=1" : "";
            const resBox = document.getElementById("result");
            resBox.textContent = "טוען...";
            latestHtml = "";
            toggleDownloadButtons(false);

            try {
                const res = await fetch(`/scrape?url=${encodeURIComponent(url)}${useBrowser}`);
                const data = await res.json();
                resBox.textContent = JSON.stringify(data, null, 2);
                latestHtml = data.content || "";
                toggleDownloadButtons(true);
            } catch (err) {
                resBox.textContent = "שגיאה: " + err;
            }
        }

        function toggleDownloadButtons(show) {
            document.getElementById("download_html").style.display = show ? "block" : "none";
            document.getElementById("download_pdf").style.display = show ? "block" : "none";
        }

        function downloadHtmlFile() {
            const blob = new Blob([latestHtml], { type: "text/html" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "scraped.html";
            a.click();
            URL.revokeObjectURL(url);
        }

        function downloadPdfFile() {
            const w = window.open("", "_blank");
            w.document.write(latestHtml);
            w.document.close();
            w.focus();
            w.print();
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

