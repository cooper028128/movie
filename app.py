# app.py
from flask import Flask, request, render_template_string
import requests
from bs4 import BeautifulSoup
import urllib3
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import re
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# 初始化 Firebase
firebase_initialized = False
db = None

# 嘗試載入憑證
cred_path = "serviceAccountKey.json"
if os.path.exists(cred_path):
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        firebase_initialized = True
        print("✅ Firebase 連線成功！")
    except Exception as e:
        print(f"❌ Firebase 初始化失敗: {e}")
else:
    print(f"❌ 找不到憑證檔案: {cred_path}")
    print("請將下載的 JSON 檔案重新命名為 serviceAccountKey.json 並放在此目錄下")

# ==================== HTML 模板 ====================

INDEX_HTML = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>電影爬蟲系統 - 靜宜大學資管系</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Microsoft JhengHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 50px;
            max-width: 600px;
            width: 90%;
            text-align: center;
        }
        h1 { color: #667eea; font-size: 2.5em; margin-bottom: 10px; }
        .subtitle { color: #666; margin-bottom: 30px; border-bottom: 2px solid #667eea; display: inline-block; padding-bottom: 5px; }
        h2 { color: #333; margin-bottom: 30px; font-size: 1.3em; }
        .btn {
            display: block;
            background: #667eea;
            color: white;
            text-decoration: none;
            padding: 15px 30px;
            margin: 20px 0;
            border-radius: 50px;
            font-size: 1.1em;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        .btn:hover { background: #764ba2; transform: translateY(-3px); }
        .btn-secondary { background: #ff6b6b; }
        .btn-secondary:hover { background: #ee5a52; }
        .status { margin-top: 20px; padding: 10px; border-radius: 10px; font-size: 14px; }
        .status-ok { background: #d4edda; color: #155724; }
        .status-error { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🕷️ 網路爬蟲</h1>
        <div class="subtitle">靜宜大學資管系 張哲綸</div>
        <h2>🎬 開眼電影網 - 近期上映爬蟲系統</h2>
        <a href="/spiderMovie" class="btn">🚀 爬取最新電影資料並存入資料庫</a>
        <a href="/searchMovie" class="btn btn-secondary">🔍 查詢電影（輸入關鍵字）</a>
        <div class="status {% if firebase_ok %}status-ok{% else %}status-error{% endif %}">
            {% if firebase_ok %}✅ Firebase 資料庫已連線{% else %}❌ Firebase 未連線，請檢查 serviceAccountKey.json{% endif %}
        </div>
    </div>
</body>
</html>
'''

SEARCH_HTML = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>查詢電影</title>
    <style>
        body {
            font-family: 'Microsoft JhengHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px;
            margin: 0;
        }
        .container { max-width: 1000px; margin: 0 auto; }
        h1, h2 { color: white; text-align: center; }
        .search-box {
            text-align: center;
            margin: 30px 0;
            background: rgba(255,255,255,0.2);
            padding: 20px;
            border-radius: 50px;
        }
        .search-box input {
            padding: 12px 20px;
            width: 300px;
            font-size: 16px;
            border: none;
            border-radius: 50px 0 0 50px;
            outline: none;
        }
        .search-box button {
            padding: 12px 25px;
            font-size: 16px;
            background: #ff6b6b;
            color: white;
            border: none;
            border-radius: 0 50px 50px 0;
            cursor: pointer;
        }
        .search-box button:hover { background: #ee5a52; }
        .movie-card {
            background: white;
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
            display: flex;
            gap: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        .movie-pic img { width: 120px; border-radius: 10px; object-fit: cover; }
        .movie-info { flex: 1; }
        .movie-title { color: #667eea; margin: 0 0 10px 0; }
        .movie-detail { color: #555; margin: 8px 0; }
        .movie-link a { color: #ff6b6b; text-decoration: none; }
        .back-link {
            display: inline-block;
            margin: 20px 10px;
            padding: 10px 20px;
            background: white;
            color: #667eea;
            text-decoration: none;
            border-radius: 50px;
        }
        .footer { text-align: center; }
        .no-result {
            background: white;
            border-radius: 15px;
            padding: 40px;
            text-align: center;
        }
        .info-bar {
            background: rgba(255,255,255,0.9);
            border-radius: 15px;
            padding: 15px;
            margin-bottom: 20px;
            text-align: center;
            color: #333;
        }
        .movie-id {
            background: #667eea;
            color: white;
            display: inline-block;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 12px;
            margin-left: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 查詢電影</h1>
        <div class="search-box">
            <form method="get" action="/searchMovie" style="display: inline-block;">
                <input type="text" name="keyword" placeholder="輸入電影名稱關鍵字" value="{{ keyword }}" required>
                <button type="submit">🔍 搜尋</button>
            </form>
        </div>
        
        {% if keyword %}
            <div class="info-bar">
                📊 找到 {{ movies|length }} 部符合「{{ keyword }}」的電影
            </div>
            
            {% if movies %}
                {% for movie in movies %}
                <div class="movie-card">
                    <div class="movie-pic">
                        <img src="{{ movie.poster }}" alt="{{ movie.title }}" onerror="this.src='https://via.placeholder.com/120x160?text=No+Image'">
                    </div>
                    <div class="movie-info">
                        <h2 class="movie-title">
                            🎬 {{ movie.title }}
                            <span class="movie-id">編號: {{ movie.id }}</span>
                        </h2>
                        <p class="movie-detail">📅 上映日期：{{ movie.release_date }}</p>
                        <p class="movie-detail">⏱️ 片長：{{ movie.duration }} 分鐘</p>
                        <p class="movie-link">🔗 <a href="{{ movie.url }}" target="_blank">點我看詳細介紹</a></p>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <div class="no-result">
                    <h2>❌ 找不到包含「{{ keyword }}」的電影</h2>
                    <p>請嘗試其他關鍵字</p>
                </div>
            {% endif %}
        {% else %}
            <div class="info-bar">
                💡 請在上方輸入片名關鍵字開始查詢
            </div>
        {% endif %}
        
        <div class="footer">
            <a href="/" class="back-link">🏠 回首頁</a>
        </div>
    </div>
</body>
</html>
'''

SPIDER_RESULT_HTML = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <title>爬蟲結果</title>
    <style>
        body {
            font-family: 'Microsoft JhengHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px;
            margin: 0;
        }
        .container { max-width: 800px; margin: 0 auto; background: white; border-radius: 20px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
        h1 { color: #667eea; text-align: center; }
        .info { background: #f0f0f0; padding: 15px; border-radius: 10px; margin: 20px 0; }
        .success { color: green; font-weight: bold; }
        .error { color: red; font-weight: bold; }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 50px;
        }
        .back-link:hover { background: #764ba2; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🕷️ 爬蟲結果</h1>
        <div class="info">
            <p>📅 <strong>資料庫最後更新時間：</strong> {{ last_update }}</p>
            <p>🎬 <strong>資料庫中共有 {{ count }} 部電影</strong></p>
            <p>📊 <strong>本次爬取狀態：</strong> <span class="{{ status_class }}">{{ status_msg }}</span></p>
            {% if new_count %}
            <p>✨ <strong>本次新增電影：</strong> {{ new_count }} 部</p>
            {% endif %}
            {% if error_msg %}
            <p class="error">⚠️ {{ error_msg }}</p>
            {% endif %}
        </div>
        <div style="text-align: center;">
            <a href="/" class="back-link">🏠 回首頁</a>
            <a href="/searchMovie" class="back-link" style="background: #ff6b6b;">🔍 前往查詢</a>
        </div>
    </div>
</body>
</html>
'''

# ==================== 爬蟲函式 ====================

def crawl_movies():
    """爬取開眼電影網近期上映電影"""
    url = "https://www.atmovies.com.tw/movie/next/"
    try:
        response = requests.get(url, verify=False, timeout=30)
        response.encoding = "utf-8"
        sp = BeautifulSoup(response.text, "html.parser")
        items = sp.select(".filmListAllX li")
        
        movies = []
        for item in items:
            try:
                title_tag = item.find("div", class_="filmtitle")
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                a_tag = title_tag.find("a")
                movie_url = "http://www.atmovies.com.tw" + a_tag.get("href") if a_tag else ""
                
                img_tag = item.find("img")
                poster = img_tag.get("src") if img_tag else ""
                if poster and not poster.startswith("http"):
                    poster = "http://www.atmovies.com.tw" + poster
                
                runtime_tag = item.find("div", class_="runtime")
                release_date = "未知"
                duration = "未知"
                if runtime_tag:
                    text = runtime_tag.get_text(strip=True)
                    date_match = re.search(r'上映日期：(\d{4}-\d{2}-\d{2})', text)
                    if date_match:
                        release_date = date_match.group(1)
                    duration_match = re.search(r'片長：(\d+)分', text)
                    if duration_match:
                        duration = duration_match.group(1)
                
                movies.append({
                    'title': title,
                    'url': movie_url,
                    'poster': poster,
                    'release_date': release_date,
                    'duration': duration
                })
            except Exception as e:
                print(f"解析單部電影失敗: {e}")
                continue
        
        return movies
    except Exception as e:
        print(f"爬蟲失敗: {e}")
        return []

# ==================== 路由 ====================

@app.route("/")
def index():
    return render_template_string(INDEX_HTML, firebase_ok=firebase_initialized)

@app.route("/spiderMovie")
def spider_movie():
    """爬取電影並存入 Firebase，顯示更新日期及總筆數"""
    if not firebase_initialized or db is None:
        return render_template_string(SPIDER_RESULT_HTML,
                                      last_update="無法連線",
                                      count=0,
                                      status_class="error",
                                      status_msg="失敗",
                                      error_msg="Firebase 未連線，請確認 serviceAccountKey.json 檔案是否存在")
    
    movies = crawl_movies()
    
    if not movies:
        return render_template_string(SPIDER_RESULT_HTML,
                                      last_update="取得失敗",
                                      count=0,
                                      status_class="error",
                                      status_msg="失敗",
                                      error_msg="無法爬取電影資料，請檢查網路連線")
    
    # 存入資料庫（使用電影標題作為 ID 避免重複）
    new_count = 0
    for movie in movies:
        doc_ref = db.collection('movies').document(movie['title'])
        doc = doc_ref.get()
        if not doc.exists:
            movie['created_at'] = datetime.now().isoformat()
            doc_ref.set(movie)
            new_count += 1
    
    # 取得資料庫總筆數
    movies_ref = db.collection('movies')
    total_count = len(list(movies_ref.stream()))
    
    # 取得最後更新時間
    last_update_docs = movies_ref.order_by('created_at', direction=firestore.Query.DESCENDING).limit(1).stream()
    last_update = "尚未有任何電影"
    for doc in last_update_docs:
        if doc.exists and 'created_at' in doc.to_dict():
            dt = doc.to_dict()['created_at'].replace('T', ' ')[:19]
            last_update = dt
    
    return render_template_string(SPIDER_RESULT_HTML,
                                  last_update=last_update,
                                  count=total_count,
                                  status_class="success",
                                  status_msg="成功",
                                  new_count=new_count)

@app.route("/searchMovie")
def search_movie():
    """查詢資料庫中符合關鍵字的電影"""
    keyword = request.args.get("keyword", "").strip()
    movies = []
    
    if firebase_initialized and db and keyword:
        movies_ref = db.collection('movies')
        docs = movies_ref.stream()
        
        for doc in docs:
            movie = doc.to_dict()
            movie['id'] = doc.id  # 使用文件 ID 作為編號
            if keyword.lower() in movie.get('title', '').lower():
                movies.append(movie)
        
        # 按上映日期排序
        movies.sort(key=lambda x: x.get('release_date', '9999-99-99'))
    
    return render_template_string(SEARCH_HTML, movies=movies, keyword=keyword)

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🎬 電影爬蟲系統啟動")
    print("="*50)
    print(f"📍 訪問網址: http://127.0.0.1:5000")
    print(f"📁 憑證檔案: {'✅ 已找到' if os.path.exists('serviceAccountKey.json') else '❌ 未找到'}")
    print("="*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
