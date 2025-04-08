from flask import Flask, request, Response, redirect
import requests
from bs4 import BeautifulSoup
import urllib.parse

app = Flask(__name__)

PROXY_BASE = 'https://your-proxy-url.onrender.com/proxy?url='  # שנה לכתובת שלך

def rewrite_url(base_url, target):
    absolute = urllib.parse.urljoin(base_url, target)
    return PROXY_BASE + urllib.parse.quote(absolute, safe='')

@app.route('/')
def home():
    return '🌀 פרוקסי פעיל. שלח בקשה ל-/proxy?url=https://example.com'

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
headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': url,
})

        data = request.form.to_dict() if method == 'POST' else None
        resp = requests.request(method, url, headers=headers, data=data, stream=True)

        content_type = resp.headers.get('Content-Type', '')
        disposition = resp.headers.get('Content-Disposition', '')

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

        proxy_headers = {}
        if 'Content-Disposition' in resp.headers:
            proxy_headers['Content-Disposition'] = resp.headers['Content-Disposition']
        if 'Content-Type' in resp.headers:
            proxy_headers['Content-Type'] = resp.headers['Content-Type']

        return Response(resp.content, headers=proxy_headers)

    except Exception as e:
        return f"שגיאה: {str(e)}", 500
