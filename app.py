from flask import Flask, request, render_template_string
import requests
from bs4 import BeautifulSoup
import urllib3
from datetime import datetime
import re
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# HTML 模板 - 首頁（同上，略）
INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>P級電影推薦系統</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Microsoft JhengHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }

        h1 {
            font-size: 3em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }

        .subtitle {
            font-size: 1.2em;
            opacity: 0.9;
        }

        .search-card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            text-align: center;
        }

        .search-form {
            display: flex;
            gap: 15px;
            justify-content: center;
            flex-wrap: wrap;
        }

        .rating-select {
            padding: 15px 20px;
            font-size: 18px;
            border: 2px solid #ddd;
            border-radius: 50px;
            width: 250px;
            cursor: pointer;
        }

        .search-btn {
            padding: 15px 40px;
            font-size: 18px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 50px;
            cursor: pointer;
            transition: transform 0.2s;
        }

        .search-btn:hover {
            transform: translateY(-2px);
        }

        .quick-buttons {
            margin-top: 20px;
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
        }

        .quick-btn {
            padding: 8px 20px;
            background: #f0f0f0;
            border: none;
            border-radius: 50px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .quick-btn:hover {
            background: #667eea;
            color: white;
        }

        .results-card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }

        .results-header {
            border-bottom: 2px solid #667eea;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }

        .results-header h2 {
            color: #667eea;
        }

        .results-count {
            color: #764ba2;
            font-weight: bold;
        }

        .movie-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
        }

        .movie-card {
            border: 1px solid #eee;
            border-radius: 15px;
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .movie-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        }

        .movie-poster {
            height: 200px;
            background: #f5f5f5;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        .movie-poster img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .no-poster {
            color: #999;
            font-size: 14px;
        }

        .movie-info {
            padding: 15px;
        }

        .movie-title {
            font-size: 1.2em;
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
        }

        .movie-rating {
            display: inline-block;
            background: #ff6b6b;
            color: white;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 12px;
            margin-bottom: 10px;
        }

        .movie-date {
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
        }

        .movie-link {
            display: inline-block;
            color: #667eea;
            text-decoration: none;
            font-size: 14px;
            margin-top: 10px;
        }

        .movie-link:hover {
            text-decoration: underline;
        }

        .no-results {
            text-align: center;
            padding: 50px;
            color: #999;
        }

        .footer {
            text-align: center;
            margin-top: 30px;
            color: white;
        }

        .debug-info {
            background: #fff3cd;
            border: 1px solid #ffc107;
            border-radius: 10px;
            padding: 15px;
            margin-top: 20px;
            font-size: 12px;
            color: #856404;
            text-align: left;
        }

        @media (max-width: 768px) {
            body {
                padding: 20px;
            }
            h1 {
                font-size: 2em;
            }
            .movie-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 P級電影推薦系統</h1>
            <p class="subtitle">查詢本週上映的保護級(P)電影，適合6歲以上觀賞</p>
        </div>

        <div class="search-card">
            <form method="get" action="/recommend" class="search-form">
                <select name="rating" class="rating-select">
                    <option value="P">🔞 P級 (保護級)</option>
                    <option value="G">👶 G級 (普遍級)</option>
                    <option value="PG12">🧒 PG12 (輔導12級)</option>
                    <option value="PG15">👦 PG15 (輔導15級)</option>
                    <option value="R">🔞 R級 (限制級)</option>
                    <option value="all">📽️ 顯示全部電影</option>
                </select>
                <button type="submit" class="search-btn">🔍 查詢推薦</button>
            </form>
            
            <div class="quick-buttons">
                <button class="quick-btn" onclick="location.href='/recommend?rating=P'">🎯 P級電影</button>
                <button class="quick-btn" onclick="location.href='/recommend?rating=all'">📅 本週全電影</button>
                <button class="quick-btn" onclick="location.href='/debug'">🔧 查看除錯</button>
                <button class="quick-btn" onclick="location.href='/'">🔄 重新整理</button>
            </div>
        </div>

        <div class="results-card">
            <div class="results-header">
                <h2>📽️ 電影推薦結果</h2>
            </div>
            <div id="results">
                <p style="text-align:center; color:#999;">請選擇電影分級進行查詢</p>
            </div>
        </div>

        <div class="footer">
            <p>資料來源：開眼電影網 | 分級依據：台灣電影分級制度</p>
        </div>
    </div>
</body>
</html>
'''

# HTML 模板 - 查詢結果
RECOMMEND_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ rating_name }}電影推薦 - 查詢結果</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Microsoft JhengHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 40px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }

        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .back-btn {
            display: inline-block;
            background: white;
            color: #667eea;
            text-decoration: none;
            padding: 10px 20px;
            border-radius: 50px;
            margin-top: 20px;
            transition: transform 0.2s;
        }

        .back-btn:hover {
            transform: translateY(-2px);
        }

        .results-card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }

        .results-header {
            border-bottom: 2px solid #667eea;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }

        .results-header h2 {
            color: #667eea;
        }

        .results-count {
            color: #764ba2;
            font-weight: bold;
        }

        .rating-badge {
            display: inline-block;
            background: {{ rating_color }};
            color: white;
            padding: 5px 15px;
            border-radius: 30px;
            margin-left: 10px;
            font-size: 14px;
        }

        .movie-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
        }

        .movie-card {
            border: 1px solid #eee;
            border-radius: 15px;
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .movie-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        }

        .movie-poster {
            height: 200px;
            background: #f5f5f5;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        .movie-poster img {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        .no-poster {
            color: #999;
            font-size: 14px;
        }

        .movie-info {
            padding: 15px;
        }

        .movie-title {
            font-size: 1.2em;
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
        }

        .movie-rating {
            display: inline-block;
            background: {{ rating_color }};
            color: white;
            padding: 3px 10px;
            border-radius: 20px;
            font-size: 12px;
            margin-bottom: 10px;
        }

        .movie-date {
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
        }

        .movie-link {
            display: inline-block;
            color: #667eea;
            text-decoration: none;
            font-size: 14px;
            margin-top: 10px;
        }

        .movie-link:hover {
            text-decoration: underline;
        }

        .no-results {
            text-align: center;
            padding: 50px;
            color: #999;
        }

        .footer {
            text-align: center;
            margin-top: 30px;
            color: white;
        }

        .search-again {
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            text-align: center;
        }

        .search-again select, .search-again button {
            padding: 10px 15px;
            margin: 0 5px;
            border-radius: 50px;
            border: 1px solid #ddd;
        }

        .search-again button {
            background: #667eea;
            color: white;
            border: none;
            cursor: pointer;
        }

        .debug-info {
            background: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 10px;
            margin-top: 20px;
            font-size: 12px;
            color: #0c5460;
        }

        @media (max-width: 768px) {
            body {
                padding: 20px;
            }
            h1 {
                font-size: 1.8em;
            }
            .movie-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎬 {{ rating_name }}電影推薦</h1>
            <p>{{ description }}</p>
            <a href="/" class="back-btn">← 返回首頁</a>
        </div>

        <div class="results-card">
            <div class="results-header">
                <h2>📽️ 本週上映電影 
                    <span class="rating-badge">{{ rating_name }}</span>
                </h2>
                <p>共找到 <span class="results-count">{{ movies|length }}</span> 部符合條件的電影</p>
                <p style="font-size: 14px; color: #666;">總共爬取 {{ total_count }} 部本週上映電影</p>
            </div>

            {% if movies %}
            <div class="movie-grid">
                {% for movie in movies %}
                <div class="movie-card">
                    <div class="movie-poster">
                        {% if movie.poster %}
                            <img src="{{ movie.poster }}" alt="{{ movie.title }}" onerror="this.parentElement.innerHTML='<div class=\'no-poster\'>🎬 無海報圖片</div>'">
                        {% else %}
                            <div class="no-poster">🎬 無海報圖片</div>
                        {% endif %}
                    </div>
                    <div class="movie-info">
                        <div class="movie-title">{{ movie.title }}</div>
                        <div class="movie-rating">{{ movie.rating }}</div>
                        <div class="movie-date">📅 上映日期：{{ movie.release_date }}</div>
                        <a href="{{ movie.url }}" class="movie-link" target="_blank">🔗 詳細介紹 →</a>
                    </div>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <div class="no-results">
                <p>😢 抱歉，本週沒有找到「{{ rating_name }}」電影</p>
                <p>💡 可能原因：</p>
                <ul style="text-align: left; display: inline-block; margin-top: 10px;">
                    <li>本週確實沒有該分級的電影上映</li>
                    <li>網站分級資訊標示不明確</li>
                    <li>建議點擊「顯示全部電影」查看所有電影的分級</li>
                </ul>
                <p style="margin-top: 20px;">
                    <a href="/recommend?rating=all" style="color: #667eea;">👉 點我查看全部電影 👈</a>
                </p>
            </div>
            {% endif %}

            <div class="search-again">
                <form method="get" action="/recommend" style="display: inline;">
                    <select name="rating">
                        <option value="P">P級 (保護級)</option>
                        <option value="G">G級 (普遍級)</option>
                        <option value="PG12">PG12 (輔導12級)</option>
                        <option value="PG15">PG15 (輔導15級)</option>
                        <option value="R">R級 (限制級)</option>
                        <option value="all">顯示全部電影</option>
                    </select>
                    <button type="submit">🔍 查詢其他分級</button>
                </form>
            </div>

            {% if debug_data %}
            <div class="debug-info">
                <strong>🔧 除錯資訊：</strong><br>
                所有電影分級統計：<br>
                {% for rating, count in debug_data.items() %}
                - {{ rating }}: {{ count }} 部<br>
                {% endfor %}
            </div>
            {% endif %}
        </div>

        <div class="footer">
            <p>資料來源：開眼電影網 | 更新時間：{{ update_time }} | 分級依據：台灣電影分級制度</p>
        </div>
    </div>
</body>
</html>
'''

# 除錯頁面
DEBUG_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>除錯資訊 - 電影分級查詢</title>
    <style>
        body {
            font-family: monospace;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            padding: 20px;
        }
        h1 { color: #333; }
        .movie-item {
            border-bottom: 1px solid #ddd;
            padding: 10px;
            margin: 5px 0;
        }
        .rating-P { background: #e8f5e9; }
        .rating-G { background: #e3f2fd; }
        .rating-PG12 { background: #fff3e0; }
        .rating-PG15 { background: #fbe9e7; }
        .rating-R { background: #ffebee; }
        .back-btn {
            display: inline-block;
            background: #667eea;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-btn">← 返回首頁</a>
        <h1>🔧 電影分級除錯資訊</h1>
        <p>總共爬取 {{ movies|length }} 部電影</p>
        
        <h2>📊 分級統計</h2>
        <ul>
        {% for rating, count in stats.items() %}
            <li><strong>{{ rating }}</strong>: {{ count }} 部</li>
        {% endfor %}
        </ul>
        
        <h2>📽️ 所有電影詳細資訊</h2>
        {% for movie in movies %}
        <div class="movie-item rating-{{ movie.rating_code }}">
            <strong>{{ movie.title }}</strong><br>
            分級: {{ movie.rating }}<br>
            上映日期: {{ movie.release_date }}<br>
            連結: <a href="{{ movie.url }}" target="_blank">{{ movie.url[:50] }}...</a><br>
            海報: <img src="{{ movie.poster }}" style="max-width: 100px; margin-top: 5px;" onerror="this.style.display='none'">
        </div>
        {% endfor %}
    </div>
</body>
</html>
'''

def get_movies_from_atmovies():
    """從開眼電影網爬取本週上映電影（改良版）"""
    url = "http://www.atmovies.com.tw/movie/next/"
    print(f"正在爬取: {url}")
    
    Data = requests.get(url, verify=False, timeout=10)
    Data.encoding = "utf-8"
    sp = BeautifulSoup(Data.text, "html.parser")
    result = sp.select(".filmListAllX li")
    
    print(f"找到 {len(result)} 部電影")
    
    movies = []
    
    for idx, item in enumerate(result):
        # 電影名稱
        title_tag = item.find("div", class_="filmtitle")
        if not title_tag:
            continue
        title = title_tag.text.strip()
        
        # 電影介紹頁
        a_tag = title_tag.find("a")
        hyperlink = "http://www.atmovies.com.tw" + a_tag.get("href") if a_tag else ""
        
        # 上映日期
        runtime_tag = item.find("div", class_="runtime")
        release_date = "未知"
        if runtime_tag:
            runtime_text = runtime_tag.text
            date_match = re.search(r'(\d{4}-\d{2}-\d{2})', runtime_text)
            if date_match:
                release_date = date_match.group(1)
        
        # 海報圖片
        img_tag = item.find("img")
        poster = img_tag.get("src") if img_tag else ""
        
        # 獲取電影分級資訊（從詳細頁面）
        rating = "未標示"
        rating_code = "unknown"
        
        if hyperlink:
            try:
                print(f"正在查詢分級: {title}")
                detail_response = requests.get(hyperlink, verify=False, timeout=5)
                detail_response.encoding = "utf-8"
                detail_sp = BeautifulSoup(detail_response.text, "html.parser")
                
                # 搜尋整個頁面文字
                page_text = detail_sp.get_text()
                
                # 更精確的分級判斷
                if re.search(r'保護級[（(]P[）)]|保護級\s*[（(]P[）)]|分級[：:]\s*保護級', page_text):
                    rating = '保護級(P)'
                    rating_code = 'P'
                elif re.search(r'普遍級[（(]G[）)]|普遍級\s*[（(]G[）)]|分級[：:]\s*普遍級', page_text):
                    rating = '普遍級(G)'
                    rating_code = 'G'
                elif re.search(r'輔導.*?12|輔12級|PG12', page_text):
                    rating = '輔導12級(PG12)'
                    rating_code = 'PG12'
                elif re.search(r'輔導.*?15|輔15級|PG15', page_text):
                    rating = '輔導15級(PG15)'
                    rating_code = 'PG15'
                elif re.search(r'限制級[（(]R[）)]|限制級\s*[（(]R[）)]|分級[：:]\s*限制級', page_text):
                    rating = '限制級(R)'
                    rating_code = 'R'
                else:
                    # 如果沒找到，檢查是否在 meta 標籤中
                    meta_rating = detail_sp.find('meta', {'property': 'rating'})
                    if meta_rating:
                        meta_content = meta_rating.get('content', '')
                        if '保護' in meta_content:
                            rating = '保護級(P)'
                            rating_code = 'P'
                        elif '普遍' in meta_content:
                            rating = '普遍級(G)'
                            rating_code = 'G'
                            
            except Exception as e:
                print(f"查詢 {title} 分級時發生錯誤: {e}")
        
        movies.append({
            'title': title,
            'url': hyperlink,
            'release_date': release_date,
            'rating': rating,
            'rating_code': rating_code,
            'poster': poster
        })
        
        print(f"電影 {idx}: {title} - {rating}")
    
    return movies

@app.route("/")
def index():
    return render_template_string(INDEX_TEMPLATE)

@app.route("/debug")
def debug():
    """除錯頁面 - 顯示所有爬取的電影和分級"""
    try:
        all_movies = get_movies_from_atmovies()
        
        # 統計各分級數量
        stats = {}
        for movie in all_movies:
            rating = movie['rating']
            stats[rating] = stats.get(rating, 0) + 1
        
        return render_template_string(DEBUG_TEMPLATE, movies=all_movies, stats=stats)
    
    except Exception as e:
        return f"除錯頁面發生錯誤: {str(e)}"

@app.route("/recommend")
def recommend():
    """查詢推薦電影 - 根據分級篩選"""
    rating = request.args.get("rating", "P")
    
    # 分級對照
    rating_map_display = {
        'P': {'name': '保護級(P)', 'color': '#4CAF50', 'description': '適合6歲以上觀眾觀賞，P級電影內容溫和，含有少量教育或娛樂元素。'},
        'G': {'name': '普遍級(G)', 'color': '#2196F3', 'description': '適合所有年齡層觀賞，內容普遍溫和。'},
        'PG12': {'name': '輔導12級(PG12)', 'color': '#FF9800', 'description': '未滿12歲不宜觀賞，12歲以上須家長陪同。'},
        'PG15': {'name': '輔導15級(PG15)', 'color': '#FF5722', 'description': '未滿15歲不宜觀賞，15歲以上須家長陪同。'},
        'R': {'name': '限制級(R)', 'color': '#F44336', 'description': '未滿18歲不得觀賞，內容可能包含成人議題。'},
        'all': {'name': '全部', 'color': '#9C27B0', 'description': '顯示本週所有上映電影及其分級資訊。'}
    }
    
    rating_info = rating_map_display.get(rating, rating_map_display['P'])
    
    # 爬取電影資料
    try:
        all_movies = get_movies_from_atmovies()
        
        if rating == 'all':
            filtered_movies = all_movies
        else:
            # 根據分級篩選
            filtered_movies = []
            for movie in all_movies:
                movie_rating = movie['rating']
                if rating == 'P' and ('保護級' in movie_rating or 'P' in movie_rating):
                    filtered_movies.append(movie)
                elif rating == 'G' and ('普遍級' in movie_rating or 'G' in movie_rating):
                    filtered_movies.append(movie)
                elif rating == 'PG12' and ('輔12' in movie_rating or 'PG12' in movie_rating):
                    filtered_movies.append(movie)
                elif rating == 'PG15' and ('輔15' in movie_rating or 'PG15' in movie_rating):
                    filtered_movies.append(movie)
                elif rating == 'R' and ('限制級' in movie_rating or 'R' in movie_rating):
                    filtered_movies.append(movie)
        
        # 準備除錯統計資料
        debug_stats = {}
        for movie in all_movies:
            r = movie['rating']
            debug_stats[r] = debug_stats.get(r, 0) + 1
        
        return render_template_string(
            RECOMMEND_TEMPLATE,
            movies=filtered_movies,
            total_count=len(all_movies),
            rating_name=rating_info['name'],
            rating_color=rating_info['color'],
            description=rating_info['description'],
            update_time=datetime.now().strftime('%Y-%m-%d %H:%M'),
            debug_data=debug_stats if rating != 'all' else None
        )
    
    except Exception as e:
        return render_template_string(
            RECOMMEND_TEMPLATE,
            movies=[],
            total_count=0,
            rating_name=rating_info['name'],
            rating_color=rating_info['color'],
            description=f"查詢發生錯誤：{str(e)}",
            update_time=datetime.now().strftime('%Y-%m-%d %H:%M'),
            debug_data=None
        )

# Vercel 需要這個
app = app

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
