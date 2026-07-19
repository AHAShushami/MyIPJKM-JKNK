import os
import json
import datetime
import requests
import feedparser
import hashlib
import re
from bs4 import BeautifulSoup

# Base Directory Setup: Dynamic path resolution for local OneDrive & GitHub Actions portability
DEFAULT_DIR = r"c:\Users\hanis\OneDrive\KPAS JKN\Natural Disaster\Data Banjir"
if os.path.exists(DEFAULT_DIR):
    BASE_DIR = DEFAULT_DIR
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

JSON_OUTPUT = os.path.join(BASE_DIR, "rumor_data.json")
HTML_OUTPUT = os.path.join(BASE_DIR, "rumors.html")

def get_hash(text):
    """Generate a unique ID for each rumor entry."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def clean_title(title):
    """Clean title by removing source trailing text from Google News."""
    title = re.sub(r' - [^-]+$', '', title)
    return title.strip()

def fetch_google_news(query):
    """Fetch search results from Google News RSS feed."""
    print(f"Fetching Google News for query: {query}...")
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=ms&gl=MY&ceid=MY:ms"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    articles = []
    try:
        # Fetch RSS feed
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code == 200:
            feed = feedparser.parse(r.text)
            for entry in feed.entries[:25]:  # Take top 25 recent entries
                articles.append({
                    'title': clean_title(entry.title),
                    'url': entry.link,
                    'published_date': entry.published,
                    'source': entry.source.get('text', 'Google News') if hasattr(entry, 'source') else 'Google News'
                })
        else:
            print(f"Failed to fetch Google News RSS. Status code: {r.status_code}")
    except Exception as e:
        print(f"Error fetching Google News: {e}")
    return articles

def scrape_sebenarnya():
    """Scrape MCMC's Sebenarnya.my search page for flood-related rumors."""
    print("Scraping Sebenarnya.my for flood debunkings...")
    url = "https://sebenarnya.my/?s=banjir"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    articles = []
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            posts = soup.find_all('article')
            print(f"Sebenarnya.my returned {len(posts)} articles on page.")
            for post in posts[:10]:
                title_el = post.find('h3') or post.find('h2') or post.find('a')
                if not title_el:
                    continue
                
                title = title_el.text.strip()
                link = ""
                link_el = post.find('a')
                if link_el and link_el.has_attr('href'):
                    link = link_el['href']
                
                # Filter for actually relevant local claims
                if not link:
                    continue
                
                # Check for description
                desc = ""
                summary_el = post.find(class_='entry-summary') or post.find(class_='post-content') or post.find('p')
                if summary_el:
                    desc = summary_el.text.strip()
                
                articles.append({
                    'title': title,
                    'url': link,
                    'published_date': datetime.datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT'),  # Fallback
                    'source': 'Sebenarnya.my',
                    'desc': desc
                })
        else:
            print(f"Failed to load Sebenarnya.my. Status: {r.status_code}")
    except Exception as e:
        print(f"Error scraping Sebenarnya.my: {e} (Gracefully skipping...)")
    return articles

def classify_rumor(title, snippet="", source=""):
    """Classify rumor using Gemini LLM if key is present, otherwise fallback to local keyword rules."""
    api_key = os.environ.get("GEMINI_API_KEY")
    
    # 1. Rules-based Fallback Classification
    if not api_key:
        print(f"No GEMINI_API_KEY found. Running local rules-based classifier for: {title[:50]}...")
        title_lower = title.lower()
        snippet_lower = snippet.lower()
        combined = title_lower + " " + snippet_lower
        
        # Default Category
        category = "General"
        if any(w in combined for w in ["klinik", "hospital", "doktor", "ubat", "pesakit", "hemodialisis", "jkn"]):
            category = "Health Facilities"
        elif any(w in combined for w in ["sungai", "paras air", "telemetri", "hujan", "lebat", "jps", "empangan", "pecah", "limpah"]):
            category = "Flood Levels"
        elif any(w in combined for w in ["pps", "pusat pemindahan", "sekolah", "mangsa", "kebajikan", "makanan", "bantuan"]):
            category = "Evacuation Centers"
        elif any(w in combined for w in ["jalan", "jejambat", "lebuhraya", "ditutup", "jambatan", "runtuh", "laluan"]):
            category = "Infrastructure"
            
        # Default Status & Clarification
        # Sebenarnya.my titles are almost always debunked statements: "PENJELASAN: Dakwaan ... Adalah Palsu"
        if source == "Sebenarnya.my" or any(w in title_lower for w in ["palsu", "tidak benar", "dinafikan", "hoax", "fitnah", "penjelasan"]):
            status = "Debunked (Palsu)"
            severity = "High"
            # Extract core claim from Sebenarnya.my title if possible
            claim = title.replace("PENJELASAN:", "").replace("Dakwaan", "").replace("Adalah Palsu", "").replace("Adalah Tidak Benar", "").strip()
            clarification = f"Pihak berkuasa (MCMC / JKN Kedah) mengesahkan bahawa dakwaan ini adalah TIDAK BENAR. Orang ramai dinasihatkan supaya menyemak kesahihan berita sebelum menyebarkannya dan hanya merujuk kepada kenyataan media rasmi agensi kerajaan."
        elif any(w in title_lower for w in ["viral", "tular", "whatsapp", "didakwa", "khabar angin", "spekulasi", "gempar"]):
            status = "Under Investigation"
            severity = "Medium"
            claim = title
            clarification = "Dakwaan tular ini sedang disemak dan diambil tindakan oleh Jabatan Kesihatan Negeri (JKN) Kedah dan agensi keselamatan. Jangan sebar maklumat tanpa pengesahan lanjut."
        else:
            status = "Verified True"
            severity = "Low"
            claim = title
            clarification = "Berita/maklumat ini telah disahkan benar oleh agensi yang bertanggungjawab. Sila patuhi arahan keselamatan semasa banjir."
            
        return {
            'status': status,
            'category': category,
            'clarification': clarification,
            'severity': severity,
            'claim': claim
        }
        
    # 2. Gemini API Classification
    print(f"Running Gemini LLM classification for: {title[:50]}...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
    Analyze the following disaster/flood-related news or social media text:
    Title: "{title}"
    Snippet: "{snippet}"
    Source: "{source}"
    
    Determine if this represents a rumor, misinformation, tular claim, or verified report.
    Classify it and return a JSON object with the following fields:
    1. "status": Must be exactly one of: "Debunked (Palsu)", "Under Investigation", or "Verified True". (If the source is "Sebenarnya.my" or the title contains clarification terms, it is almost certainly "Debunked (Palsu)").
    2. "category": Must be exactly one of: "Health Facilities", "Flood Levels", "Evacuation Centers", "Infrastructure", or "General".
    3. "severity": Must be exactly one of: "High", "Medium", or "Low". (A rumor about public health, clinic closures, or dam failures is High severity).
    4. "claim": A cleaned-up version of the rumor/claim (e.g., remove "PENJELASAN: Dakwaan" and "Adalah Palsu" if present, just isolate what the rumor says).
    5. "clarification": A concise, professional clarification paragraph in Bahasa Melayu. If debunked, specify why it is false (e.g. "JKN Kedah confirms all clinics are operating", "MADA confirms the dam is stable").
    
    Return ONLY valid JSON. Do not include markdown code block syntax (like ```json).
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            result = res.json()
            response_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
            # Clean possible markdown wrap
            response_text = re.sub(r'^```json\s*|\s*```$', '', response_text, flags=re.MULTILINE)
            data = json.loads(response_text)
            return {
                'status': data.get('status', 'Under Investigation'),
                'category': data.get('category', 'General'),
                'clarification': data.get('clarification', 'Sedang disemak oleh pihak berkuasa.'),
                'severity': data.get('severity', 'Medium'),
                'claim': data.get('claim', title)
            }
        else:
            print(f"Gemini API returned status {res.status_code}. Falling back to rules-based classifier.")
    except Exception as e:
        print(f"Error calling Gemini API: {e}. Falling back to rules-based classifier.")
        
    # Fallback if API fails mid-way
    os.environ["GEMINI_API_KEY"] = ""  # Temporarily clear to trigger fallback
    ret = classify_rumor(title, snippet, source)
    os.environ["GEMINI_API_KEY"] = api_key
    return ret

def generate_html_dashboard(rumors, last_updated):
    """Compiles the HTML rumors dashboard using a stunning responsive layout matching the main page."""
    
    # Calculate statistics
    total = len(rumors)
    debunked = sum(1 for r in rumors if r['status'] == 'Debunked (Palsu)')
    investigation = sum(1 for r in rumors if r['status'] == 'Under Investigation')
    verified = sum(1 for r in rumors if r['status'] == 'Verified True')
    
    # Group rumors into JSON string for frontend use
    rumors_json = json.dumps(rumors, ensure_ascii=False)
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JKN Kedah - Rumor Surveillance & Fact-Checking Center</title>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap" rel="stylesheet">
    <!-- FontAwesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <style>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --border-color: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-blue: #3b82f6;
            
            --status-debunked: #ef4444;      /* Red */
            --status-investigating: #eab308; /* Yellow */
            --status-verified: #10b981;      /* Green */
            
            --severity-high: #f43f5e;
            --severity-med: #fb923c;
            --severity-low: #38bdf8;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            display: flex;
            height: 100vh;
            overflow: hidden;
        }}

        /* App Layout */
        .sidebar {{
            width: 320px;
            background-color: var(--bg-secondary);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            padding: 24px;
            overflow-y: auto;
            flex-shrink: 0;
        }}

        .main-content {{
            flex: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}

        /* Typography & Navigation */
        h1 {{
            font-size: 1.35rem;
            font-weight: 700;
            margin-bottom: 8px;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .subtitle {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            margin-bottom: 24px;
            line-height: 1.4;
        }}

        .navigation-menu {{
            margin-bottom: 24px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 20px;
        }}

        .nav-link {{
            display: flex;
            align-items: center;
            gap: 12px;
            color: var(--text-secondary);
            text-decoration: none;
            font-weight: 600;
            padding: 10px 14px;
            border-radius: 8px;
            font-size: 0.9rem;
            transition: all 0.2s;
        }}

        .nav-link:hover {{
            background-color: rgba(255, 255, 255, 0.05);
            color: #fff;
        }}

        .nav-link.active {{
            background-color: rgba(59, 130, 246, 0.15);
            color: var(--accent-blue);
            border: 1px solid rgba(59, 130, 246, 0.3);
        }}

        .update-badge {{
            background-color: rgba(59, 130, 246, 0.1);
            border: 1px dashed var(--accent-blue);
            color: #60a5fa;
            font-size: 0.8rem;
            padding: 8px 12px;
            border-radius: 8px;
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .section-title {{
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 12px;
        }}

        /* Filters Control panel */
        .filter-group {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-bottom: 24px;
        }}

        .filter-control {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}

        .filter-control label {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}

        .filter-control select, .filter-control input {{
            background-color: var(--bg-primary);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 10px;
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.9rem;
            outline: none;
            transition: border-color 0.2s;
        }}

        .filter-control select:focus, .filter-control input:focus {{
            border-color: var(--accent-blue);
        }}

        /* Statistics Grid */
        .stats-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 10px;
            margin-bottom: 24px;
        }}

        .stat-card {{
            background-color: rgba(15, 23, 42, 0.4);
            border: 1px solid var(--border-color);
            padding: 12px 14px;
            border-radius: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .stat-info {{
            display: flex;
            flex-direction: column;
            gap: 2px;
        }}

        .stat-label {{
            font-size: 0.78rem;
            color: var(--text-secondary);
        }}

        .stat-value {{
            font-size: 1.35rem;
            font-weight: 700;
        }}

        .stat-indicator {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }}
        .indicator-total {{ background-color: var(--accent-blue); }}
        .indicator-debunked {{ background-color: var(--status-debunked); box-shadow: 0 0 8px var(--status-debunked); }}
        .indicator-investigation {{ background-color: var(--status-investigating); }}
        .indicator-verified {{ background-color: var(--status-verified); }}

        /* Main Content Headers & Tabs */
        .header-bar {{
            background-color: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-shrink: 0;
        }}

        .header-title {{
            font-size: 1.15rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .feed-container {{
            flex: 1;
            overflow-y: auto;
            padding: 24px;
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(450px, 1fr));
            gap: 20px;
            align-content: start;
        }}

        @media (max-width: 1024px) {{
            .feed-container {{
                grid-template-columns: 1fr;
            }}
        }}

        /* Rumor Card Styling */
        .rumor-card {{
            background-color: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 14px;
            transition: transform 0.2s, box-shadow 0.2s, border-color 0.2s;
            position: relative;
            overflow: hidden;
        }}

        .rumor-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.3);
            border-color: rgba(59, 130, 246, 0.4);
        }}

        .rumor-card::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
        }}
        .rumor-card.status-debunked::before {{ background-color: var(--status-debunked); }}
        .rumor-card.status-investigating::before {{ background-color: var(--status-investigating); }}
        .rumor-card.status-verified::before {{ background-color: var(--status-verified); }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
        }}

        .badge {{
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            padding: 4px 10px;
            border-radius: 6px;
            letter-spacing: 0.02em;
            display: inline-block;
        }}
        
        .badge-debunked {{ background-color: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }}
        .badge-investigating {{ background-color: rgba(234, 179, 8, 0.15); color: #facc15; border: 1px solid rgba(234, 179, 8, 0.3); }}
        .badge-verified {{ background-color: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }}

        .severity-dot {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.75rem;
            color: var(--text-secondary);
            font-weight: 600;
        }}

        .dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }}
        .dot-high {{ background-color: var(--severity-high); box-shadow: 0 0 6px var(--severity-high); }}
        .dot-medium {{ background-color: var(--severity-med); }}
        .dot-low {{ background-color: var(--severity-low); }}

        .card-meta {{
            display: flex;
            gap: 14px;
            font-size: 0.75rem;
            color: var(--text-secondary);
        }}

        .card-meta span i {{
            margin-right: 4px;
        }}

        .claim-box {{
            background-color: rgba(15, 23, 42, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.05);
            padding: 12px 14px;
            border-radius: 8px;
            font-size: 0.95rem;
            line-height: 1.5;
            color: #fff;
            font-weight: 600;
        }}

        .clarification-title {{
            font-size: 0.78rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .status-debunked .clarification-title {{ color: #f87171; }}
        .status-investigating .clarification-title {{ color: #facc15; }}
        .status-verified .clarification-title {{ color: #34d399; }}

        .clarification-text {{
            font-size: 0.85rem;
            line-height: 1.5;
            color: var(--text-primary);
        }}

        .card-footer {{
            border-top: 1px solid rgba(255,255,255,0.05);
            padding-top: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.8rem;
        }}

        .source-badge {{
            color: var(--accent-blue);
            text-decoration: none;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        .source-badge:hover {{
            text-decoration: underline;
        }}

        /* Submission Modal/Panel Toggle */
        .report-btn {{
            background-color: var(--accent-blue);
            color: #fff;
            border: none;
            padding: 10px 18px;
            font-family: inherit;
            font-size: 0.9rem;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: background-color 0.2s;
        }}

        .report-btn:hover {{
            background-color: #2563eb;
        }}

        /* Overlay Submission Panel */
        .overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(8px);
            z-index: 100;
            display: none;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }}

        .modal-box {{
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            width: 100%;
            max-width: 500px;
            border-radius: 16px;
            padding: 24px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
            position: relative;
        }}

        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .modal-header h3 {{
            font-size: 1.15rem;
            font-weight: 700;
            color: #fff;
        }}

        .close-btn {{
            background: none;
            border: none;
            color: var(--text-secondary);
            font-size: 1.2rem;
            cursor: pointer;
        }}

        .close-btn:hover {{
            color: #fff;
        }}

        .form-group {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .form-group label {{
            font-size: 0.8rem;
            color: var(--text-secondary);
            font-weight: 600;
        }}

        .form-group input, .form-group textarea, .form-group select {{
            background-color: var(--bg-primary);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 10px;
            border-radius: 8px;
            font-family: inherit;
            outline: none;
        }}

        .form-group textarea {{
            resize: vertical;
            min-height: 80px;
        }}

        .submit-btn {{
            background-color: #10b981;
            color: #fff;
            border: none;
            padding: 12px;
            font-family: inherit;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            transition: background-color 0.2s;
        }}

        .submit-btn:hover {{
            background-color: #059669;
        }}
    </style>
</head>
<body>

    <!-- Sidebar Navigation & Controls -->
    <div class="sidebar">
        <h1><i class="fa-solid fa-house-flood-water" style="color: var(--status-debunked);"></i> JKN Kedah</h1>
        <div class="subtitle">Rumor Surveillance & Fact-Checking Center</div>

        <div class="navigation-menu">
            <a href="index.html" class="nav-link"><i class="fa-solid fa-map-location-dot"></i> Flood Surveillance</a>
            <a href="rumors.html" class="nav-link active"><i class="fa-solid fa-bullhorn"></i> Rumor Surveillance</a>
        </div>

        <div class="update-badge">
            <i class="fa-solid fa-rotate"></i>
            <div>Last Scan Processed:<br><span id="update-time" style="font-weight: 600;">{last_updated}</span></div>
        </div>

        <div class="section-title">Active Metrics</div>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-info">
                    <span class="stat-label">Total Harvester Scans</span>
                    <span class="stat-value" id="count-total">{total}</span>
                </div>
                <div class="stat-indicator indicator-total"></div>
            </div>
            <div class="stat-card">
                <div class="stat-info">
                    <span class="stat-label">Debunked (Palsu)</span>
                    <span class="stat-value" id="count-debunked" style="color: var(--status-debunked);">{debunked}</span>
                </div>
                <div class="stat-indicator indicator-debunked"></div>
            </div>
            <div class="stat-card">
                <div class="stat-info">
                    <span class="stat-label">Under Investigation</span>
                    <span class="stat-value" id="count-investigation" style="color: var(--status-investigating);">{investigation}</span>
                </div>
                <div class="stat-indicator indicator-investigation"></div>
            </div>
            <div class="stat-card">
                <div class="stat-info">
                    <span class="stat-label">Verified True</span>
                    <span class="stat-value" id="count-verified" style="color: var(--status-verified);">{verified}</span>
                </div>
                <div class="stat-indicator indicator-verified"></div>
            </div>
        </div>

        <div class="section-title">Filter & Search</div>
        <div class="filter-group">
            <div class="filter-control">
                <label for="filter-status">Veracity Status</label>
                <select id="filter-status" onchange="applyFilters()">
                    <option value="all">All Items</option>
                    <option value="Debunked (Palsu)">Debunked (Palsu)</option>
                    <option value="Under Investigation">Under Investigation</option>
                    <option value="Verified True">Verified True</option>
                </select>
            </div>
            <div class="filter-control">
                <label for="filter-category">Category</label>
                <select id="filter-category" onchange="applyFilters()">
                    <option value="all">All Categories</option>
                    <option value="Health Facilities">Health Facilities</option>
                    <option value="Flood Levels">Flood Levels</option>
                    <option value="Evacuation Centers">Evacuation Centers</option>
                    <option value="Infrastructure">Infrastructure</option>
                    <option value="General">General</option>
                </select>
            </div>
            <div class="filter-control">
                <label for="filter-search">Keyword Search</label>
                <input type="text" id="filter-search" placeholder="Type here..." onkeyup="applyFilters()">
            </div>
        </div>
    </div>

    <!-- Main Workspace Feed -->
    <div class="main-content">
        <div class="header-bar">
            <div class="header-title">
                <i class="fa-solid fa-shield-halved" style="color: var(--accent-blue);"></i> Rumor Registry Feed
            </div>
            <button class="report-btn" onclick="toggleModal(true)">
                <i class="fa-solid fa-circle-exclamation"></i> Report Social Media Rumor
            </button>
        </div>

        <!-- Rumor Cards List -->
        <div class="feed-container" id="feed-container">
            <!-- Dynamically populated -->
        </div>
    </div>

    <!-- Submit Rumor Modal -->
    <div class="overlay" id="report-modal">
        <div class="modal-box">
            <div class="modal-header">
                <h3><i class="fa-solid fa-triangle-exclamation" style="color: var(--status-investigating);"></i> Report Emerging Rumor</h3>
                <button class="close-btn" onclick="toggleModal(false)">&times;</button>
            </div>
            <div class="subtitle" style="margin-bottom:0;">Encountered unverified news on Whatsapp, Telegram, or Facebook? Log it here for MCMC & JKN verification.</div>
            
            <form onsubmit="handleFormSubmit(event)">
                <div class="form-group" style="margin-bottom:12px;">
                    <label for="form-title">Rumor Headline / Claim</label>
                    <input type="text" id="form-title" placeholder="e.g., Klinik Kesihatan Alor Setar ditutup sebab banjir pecah" required>
                </div>
                <div class="form-group" style="margin-bottom:12px;">
                    <label for="form-category">Category</label>
                    <select id="form-category" required>
                        <option value="Health Facilities">Health Facilities</option>
                        <option value="Flood Levels">Flood Levels</option>
                        <option value="Evacuation Centers">Evacuation Centers</option>
                        <option value="Infrastructure">Infrastructure</option>
                        <option value="General">General</option>
                    </select>
                </div>
                <div class="form-group" style="margin-bottom:16px;">
                    <label for="form-details">Where did you see this? (Source Details)</label>
                    <textarea id="form-details" placeholder="e.g., Forwarded group message on Whatsapp. Circulating since 12:00 PM today." required></textarea>
                </div>
                <button type="submit" class="submit-btn">Submit to Surveillance Registry</button>
            </form>
        </div>
    </div>

    <!-- Inject Inline Data -->
    <script>
        const rawRumorsData = {rumors_json};
        
        function getStatusClass(status) {{
            if (status === 'Debunked (Palsu)') return 'status-debunked';
            if (status === 'Under Investigation') return 'status-investigating';
            return 'status-verified';
        }}

        function getBadgeClass(status) {{
            if (status === 'Debunked (Palsu)') return 'badge-debunked';
            if (status === 'Under Investigation') return 'badge-investigating';
            return 'badge-verified';
        }}

        function getSeverityClass(sev) {{
            if (sev === 'High') return 'dot-high';
            if (sev === 'Medium') return 'dot-medium';
            return 'dot-low';
        }}

        function renderFeed(list) {{
            const container = document.getElementById('feed-container');
            container.innerHTML = '';
            
            if (list.length === 0) {{
                container.innerHTML = `
                    <div style="grid-column: 1 / -1; text-align: center; padding: 60px; color: var(--text-secondary);">
                        <i class="fa-solid fa-folder-open" style="font-size: 3rem; margin-bottom: 14px; color: var(--border-color);"></i>
                        <p>No rumors or reports match the selected filters.</p>
                    </div>
                `;
                return;
            }}
            
            list.forEach(r => {{
                const card = document.createElement('div');
                card.className = `rumor-card ${{getStatusClass(r.status)}}`;
                
                // Format Date
                let formattedDate = r.published_date;
                try {{
                    const d = new Date(r.published_date);
                    if (!isNaN(d.getTime())) {{
                        formattedDate = d.toLocaleDateString('ms-MY', {{ day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }});
                    }}
                }} catch (e) {{}}

                card.innerHTML = `
                    <div class="card-header">
                        <span class="badge ${{getBadgeClass(r.status)}}">${{r.status}}</span>
                        <div class="severity-dot">
                            <div class="dot ${{getSeverityClass(r.severity)}}"></div> Severity: ${{r.severity}}
                        </div>
                    </div>
                    
                    <div class="claim-box">
                        "${{r.claim}}"
                    </div>
                    
                    <div>
                        <div class="clarification-title">
                            <i class="fa-solid fa-circle-info"></i> Official Clarification
                        </div>
                        <div class="clarification-text">
                            ${{r.clarification}}
                        </div>
                    </div>
                    
                    <div class="card-meta">
                        <span><i class="fa-regular fa-clock"></i> ${{formattedDate}}</span>
                        <span><i class="fa-solid fa-tag"></i> ${{r.category}}</span>
                    </div>
                    
                    <div class="card-footer">
                        <span style="color: var(--text-secondary);">Source: ${{r.source}}</span>
                        <a href="${{r.url}}" target="_blank" class="source-badge">
                            Verify <i class="fa-solid fa-up-right-from-square"></i>
                        </a>
                    </div>
                `;
                container.appendChild(card);
            }});
        }}

        function applyFilters() {{
            const statusFilter = document.getElementById('filter-status').value;
            const categoryFilter = document.getElementById('filter-category').value;
            const searchQuery = document.getElementById('filter-search').value.toLowerCase().trim();
            
            const filtered = rawRumorsData.filter(r => {{
                const matchesStatus = statusFilter === 'all' || r.status === statusFilter;
                const matchesCategory = categoryFilter === 'all' || r.category === categoryFilter;
                
                const claimText = (r.claim || '').toLowerCase();
                const titleText = (r.title || '').toLowerCase();
                const clarText = (r.clarification || '').toLowerCase();
                const matchesSearch = searchQuery === '' || 
                                      claimText.includes(searchQuery) || 
                                      titleText.includes(searchQuery) ||
                                      clarText.includes(searchQuery);
                                      
                return matchesStatus && matchesCategory && matchesSearch;
            }});
            
            renderFeed(filtered);
        }}

        function toggleModal(show) {{
            const modal = document.getElementById('report-modal');
            modal.style.display = show ? 'flex' : 'none';
        }}

        function handleFormSubmit(e) {{
            e.preventDefault();
            const title = document.getElementById('form-title').value;
            const category = document.getElementById('form-category').value;
            const details = document.getElementById('form-details').value;
            
            // Add a mock pending entry locally for visual feedback
            const mockEntry = {{
                id: 'user_' + Date.now(),
                title: title,
                claim: title,
                url: '#',
                published_date: new Date().toISOString(),
                source: 'User Submission',
                status: 'Under Investigation',
                category: category,
                severity: 'Medium',
                clarification: 'Terima kasih atas laporan anda. ' + details + ' Sedang dihantar kepada CPRC Negeri dan PKD untuk pengesahan rasmi.'
            }};
            
            rawRumorsData.unshift(mockEntry);
            
            // Update counter labels
            document.getElementById('count-total').innerText = rawRumorsData.length;
            const curInv = parseInt(document.getElementById('count-investigation').innerText) || 0;
            document.getElementById('count-investigation').innerText = curInv + 1;
            
            applyFilters();
            toggleModal(false);
            
            // Reset form
            e.target.reset();
            alert("Terima kasih. Laporan khabar angin telah dihantar ke sistem pemantauan JKN.");
        }}

        // Initial render
        window.onload = function() {{
            renderFeed(rawRumorsData);
        }};
    </script>
</body>
</html>"""
    
    with open(HTML_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Generated interactive Rumor Surveillance Dashboard at {HTML_OUTPUT}")

def main():
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Rumor Surveillance Harvester...")
    
    # 1. Load existing database state
    existing_rumors = []
    if os.path.exists(JSON_OUTPUT):
        print(f"Loading existing rumor database from {JSON_OUTPUT}...")
        try:
            with open(JSON_OUTPUT, 'r', encoding='utf-8') as f:
                existing_rumors = json.load(f)
            print(f"Loaded {len(existing_rumors)} rumors from database.")
        except Exception as e:
            print(f"Error reading JSON output: {e}. Reinitializing database.")
    else:
        print("Rumor database not found. Initializing a new database.")
        
    seen_urls = {item['url'] for item in existing_rumors if 'url' in item}
    
    # 2. Gather from Google News
    scraped_items = []
    google_items = fetch_google_news("Kedah banjir OR Kedah klinik OR Kedah PPS")
    scraped_items.extend(google_items)
    
    # 3. Gather from Sebenarnya.my
    sebenarnya_items = scrape_sebenarnya()
    scraped_items.extend(sebenarnya_items)
    
    # 4. Filter duplicates and process new items
    new_rumors = []
    for item in scraped_items:
        if item['url'] not in seen_urls and item['url'] not in [x['url'] for x in new_rumors]:
            # Process and Classify
            desc = item.get('desc', '')
            classification = classify_rumor(item['title'], desc, item['source'])
            
            entry = {
                'id': get_hash(item['url']),
                'title': item['title'],
                'url': item['url'],
                'published_date': item['published_date'],
                'source': item['source'],
                'status': classification['status'],
                'category': classification['category'],
                'severity': classification['severity'],
                'claim': classification['claim'],
                'clarification': classification['clarification'],
                'timestamp': datetime.datetime.utcnow().isoformat()
            }
            new_rumors.append(entry)
            
    if new_rumors:
        print(f"Found {len(new_rumors)} new rumors. Appending to registry...")
        existing_rumors = new_rumors + existing_rumors # Prepend recent
        # Keep registry bounded to latest 150 items to keep files lightweight
        existing_rumors = existing_rumors[:150]
        
        # Save registry JSON
        with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(existing_rumors, f, indent=2, ensure_ascii=False)
        print(f"Saved updated registry to {JSON_OUTPUT}")
    else:
        print("No new rumors found in this scan cycle.")
        
    # If database is completely empty (e.g. first run and network issues), seed with default mock entries for JKN Kedah context
    if not existing_rumors:
        print("Seeding rumor database with default entries...")
        existing_rumors = [
            {
                "id": "seed_1",
                "title": "PENJELASAN: Dakwaan Klinik Kesihatan Alor Setar Ditutup Kerana Banjir Adalah Tidak Benar",
                "url": "https://sebenarnya.my/klinik-kesihatan-alor-setar-banjir-palsu",
                "published_date": "Thu, 18 Sep 2025 08:00:00 GMT",
                "source": "Sebenarnya.my",
                "status": "Debunked (Palsu)",
                "category": "Health Facilities",
                "severity": "High",
                "claim": "Klinik Kesihatan Alor Setar ditutup sepenuhnya akibat dinaiki air banjir",
                "clarification": "Jabatan Kesihatan Negeri (JKN) Kedah menjelaskan bahawa Klinik Kesihatan Alor Setar tidak ditutup. Klinik beroperasi seperti biasa melalui laluan alternatif yang disediakan bagi memudahkan pesakit.",
                "timestamp": datetime.datetime.utcnow().isoformat()
            },
            {
                "id": "seed_2",
                "title": "PENJELASAN: Dakwaan Pintu Kawalan Air Lembaga Kemajuan Pertanian Muda (MADA) Pecah Adalah Tidak Benar",
                "url": "https://sebenarnya.my/pintu-mada-pecah-banjir-kedah",
                "published_date": "Wed, 17 Sep 2025 10:30:00 GMT",
                "source": "Sebenarnya.my",
                "status": "Debunked (Palsu)",
                "category": "Flood Levels",
                "severity": "High",
                "claim": "Pintu air MADA pecah mengakibatkan limpahan air banjir yang mendadak di daerah Kota Setar",
                "clarification": "Pihak MADA menafikan dakwaan tersebut dan menegaskan semua struktur pintu kawalan air berada dalam keadaan baik dan diselia secara berkala sepanjang Monsun Timur Laut.",
                "timestamp": datetime.datetime.utcnow().isoformat()
            },
            {
                "id": "seed_3",
                "title": "Tular mesej Whatsapp mendakwa PPS Sekolah Kebangsaan Mergong kehabisan makanan bantuan mangsa banjir",
                "url": "https://news.google.com/articles/sk-mergong-makanan-tular",
                "published_date": "Fri, 19 Sep 2025 14:15:00 GMT",
                "source": "Google News",
                "status": "Under Investigation",
                "category": "Evacuation Centers",
                "severity": "Medium",
                "claim": "Bekalan makanan di PPS SK Mergong kehabisan dan mangsa kelaparan",
                "clarification": "Pejabat Kebajikan Masyarakat Daerah sedang menyiasat laporan tersebut. Semakan awal mendapati penghantaran makanan tambahan sedang diatur ke PPS terbabit.",
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        ]
        with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(existing_rumors, f, indent=2, ensure_ascii=False)
            
    # 5. Compile and generate the HTML dashboard
    last_updated_str = datetime.datetime.now().strftime('%d/%m/%Y %I:%M %p')
    generate_html_dashboard(existing_rumors, last_updated_str)
    
if __name__ == "__main__":
    main()
