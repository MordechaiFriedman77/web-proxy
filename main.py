from flask import Flask, request, Response
import requests
from bs4 import BeautifulSoup
import urllib.parse

app = Flask(__name__)

# כתובת הפרוקסי שלך
PROXY_BASE = 'https://ivr-ai-server.onrender.com/proxy?url='

def rewrite_url(base_url, target):
    absolute = urllib.parse.urljoin(base_url, target)
    return PROXY_BASE + urllib.parse.quote(absolute, safe='')

@app.route('/')
def home():
    return '🌀 פרוקסי פעיל. שלח בקשה ל-/proxy?url=https://example.com'
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

@app.route('/proxy', methods=['GET', 'POST'])
def proxy():
    url = request.args.get('url')
    if not url:
        return "חסר פרמטר ?url=", 400

    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    try:
        method = request.method
        headers = {k: v for k, v in request.headers if k.lower() != 'host'}
        data = request.form.to_dict() if method == 'POST' else None
        resp = requests.request(method, url, headers=headers, data=data, stream=True)

        content_type = resp.headers.get('Content-Type', '')
        if 'text/html' in content_type:
            soup = BeautifulSoup(resp.text, 'html.parser')

            for a in soup.find_all('a', href=True):
                a['href'] = rewrite_url(url, a['href'])

            for form in soup.find_all('form', action=True):
                form['action'] = rewrite_url(url, form['action'])

            for tag in soup.find_all(['script', 'link', 'img', 'iframe']):
                attr = 'src' if tag.name != 'link' else 'href'
                if tag.has_attr(attr):
                    tag[attr] = rewrite_url(url, tag[attr])

            banner = soup.new_tag('div')
            banner.string = "⚠️ זהו עמוד דרך פרוקסי ⚠️"
            banner['style'] = 'background: yellow; padding: 10px; font-weight: bold; text-align: center;'
            if soup.body:
                soup.body.insert(0, banner)

            return Response(str(soup), content_type='text/html')

        proxy_headers = {
            'Content-Type': resp.headers.get('Content-Type', ''),
            'Content-Disposition': resp.headers.get('Content-Disposition', '')
        }

        return Response(resp.content, headers=proxy_headers)

    except Exception as e:
        return f"שגיאה: {str(e)}", 500
