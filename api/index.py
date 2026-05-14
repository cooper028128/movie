from flask import Flask, request, make_response, jsonify
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import re
import os
import json

app = Flask(__name__)

# ==================== Firebase 初始化 (Vercel 優化版) ====================
def init_firebase():
    """在 Vercel 環境中初始化 Firebase"""
    try:
        # Vercel 環境變數
        firebase_key = os.environ.get('FIREBASE_KEY')
        
        if firebase_key:
            # 從環境變數讀取金鑰
            key_dict = json.loads(firebase_key)
            cred = credentials.Certificate(key_dict)
        else:
            # 本地開發使用檔案
            cred = credentials.Certificate("firebase-key.json")
        
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase 初始化成功")
        return db
    except Exception as e:
        print(f"Firebase 初始化失敗：{e}")
        return None

db = init_firebase()

# ==================== 輔助函數 ====================
def parse_chinese_date(date_str, reference_year=None):
    """解析中文日期格式"""
    if not date_str or date_str == "未知":
        return None
    
    if reference_year is None:
        reference_year = datetime.now().year
    
    match = re.match(r'(\d{1,2})月(\d{1,2})日', date_str)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        try:
            return datetime(reference_year, month, day).strftime('%Y-%m-%d')
        except ValueError:
            return None
    
    match = re.match(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date_str)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return datetime(year, month, day).strftime('%Y-%m-%d')
        except ValueError:
            return None
    
    return None

def is_date_in_this_week(date_str):
    """判斷日期是否在本週內"""
    if not date_str or date_str == "未知":
        return False
    
    try:
        if '-' in date_str:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        elif '/' in date_str:
            date_obj = datetime.strptime(date_str, '%Y/%m/%d').date()
        else:
            return False
        
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        return start_of_week <= date_obj <= end_of_week
    except:
        return False

def get_rate_chinese(rate_code):
    """將分級代碼轉換為中文"""
    rate_map = {
        "G": "普遍級",
        "P": "保護級",
        "F2": "輔12級",
        "F5": "輔15級",
        "R": "限制級"
    }
    return rate_map.get(rate_code, "未分級")

def normalize_rate(rate_param):
    """標準化使用者輸入的分級名稱"""
    rate_map = {
        "普遍級": "普遍級", "G級": "普遍級", "普級": "普遍級", "G": "普遍級",
        "保護級": "保護級", "P級": "保護級", "護級": "保護級", "P": "保護級",
        "輔12級": "輔12級", "PG12級": "輔12級", "輔12": "輔12級", "F2": "輔12級",
        "輔15級": "輔15級", "PG15級": "輔15級", "輔15": "輔15級", "F5": "輔15級",
        "限制級": "限制級", "R級": "限制級", "限級": "限制級", "R": "限制級"
    }
    return rate_map.get(rate_param, rate_param)

# ==================== API 路由 ====================
@app.route('/', methods=['GET'])
def index():
    """首頁"""
    return jsonify({
        "status": "ok",
        "message": "電影查詢機器人 API 運行中",
        "endpoints": {
            "webhook": "POST /api/webhook - Dialogflow Webhook",
            "crawl": "GET /api/crawl - 執行爬蟲更新資料",
            "stats": "GET /api/stats - 查看資料庫統計"
        }
    })

@app.route('/api/webhook', methods=['POST'])
def webhook():
    """處理 Dialogflow 的 Webhook 請求"""
    if db is None:
        return make_response(jsonify({
            "fulfillmentText": "資料庫連線失敗，請檢查 Firebase 設定。"
        }))
    
    try:
        req = request.get_json(force=True)
        query_result = req.get("queryResult", {})
        action = query_result.get("action", "")
        parameters = query_result.get("parameters", {})
        
        print(f"收到請求 - Action: {action}, Parameters: {parameters}")
        
        # 處理分級查詢
        if action == "rateChoice":
            return handle_rate_query(parameters)
        
        # 處理本週上映查詢
        elif action == "thisWeekMovies":
            return handle_this_week_query(parameters)
        
        # 處理綜合查詢
        elif action == "rateWithWeek":
            return handle_rate_with_week_query(parameters)
        
        # 預設回應
        else:
            return make_response(jsonify({
                "fulfillmentText": "您好！我可以幫您查詢電影資訊。\n\n您可以這樣問：\n• 推薦保護級的電影\n• 本週上映哪些電影\n• 本週有上映的保護級電影"
            }))
    
    except Exception as e:
        print(f"Webhook 錯誤：{str(e)}")
        return make_response(jsonify({
            "fulfillmentText": f"處理請求時發生錯誤：{str(e)}"
        }))

@app.route('/api/webhook', methods=['GET'])
def webhook_get():
    """GET 方法測試"""
    return jsonify({
        "status": "ok",
        "message": "Webhook 端點正常運作，請使用 POST 方式發送請求。"
    })

@app.route('/api/crawl', methods=['GET', 'POST'])
def crawl_movies():
    """爬取開眼電影最新資訊"""
    if db is None:
        return jsonify({"error": "Firebase 未初始化"}), 500
    
    try:
        url = "https://www.atmovies.com.tw/movie/new/"
        response = requests.get(url, timeout=30)
        response.encoding = "utf-8"
        
        if response.status_code != 200:
            return jsonify({"error": f"網站回應錯誤：HTTP {response.status_code}"}), 500
        
        sp = BeautifulSoup(response.text, "html.parser")
        
        last_update_elem = sp.find(class_="smaller09")
        last_update = last_update_elem.text[5:] if last_update_elem else "未知"
        
        film_list = sp.select(".filmList")
        if not film_list:
            return jsonify({"error": "找不到電影列表，網站結構可能已改變"}), 500
        
        count = 0
        movies = []
        
        for film in film_list:
            try:
                title_elem = film.find("a")
                if not title_elem:
                    continue
                title = title_elem.text.strip()
                
                intro_elem = film.find("p")
                introduce = intro_elem.text.strip() if intro_elem else "無介紹"
                
                movie_path = title_elem.get("href", "")
                movie_id = movie_path.replace("/", "").replace("movie", "")
                hyperlink = f"http://www.atmovies.com.tw/movie/{movie_id}"
                picture = f"https://www.atmovies.com.tw/photo101/{movie_id}/pm_{movie_id}.jpg"
                
                runtime_elem = film.find(class_="runtime")
                rate_code = ""
                rate = "未分級"
                show_length = 0
                show_date = "未知"
                
                if runtime_elem:
                    img = runtime_elem.find("img")
                    if img and img.get("src"):
                        src = img.get("src")
                        rate_code = src.replace("/images/cer_", "").replace(".gif", "")
                        rate = get_rate_chinese(rate_code)
                    
                    runtime_text = runtime_elem.text
                    
                    length_match = re.search(r'片長[：:]\s*(\d+)', runtime_text)
                    if length_match:
                        show_length = int(length_match.group(1))
                    else:
                        length_match = re.search(r'片長(\d+)分', runtime_text)
                        show_length = int(length_match.group(1)) if length_match else 0
                    
                    date_match = re.search(r'上映日期[：:]\s*([^\d]+)?(\d{1,2}月\d{1,2}日|\d{4}[-/]\d{1,2}[-/]\d{1,2})', runtime_text)
                    if date_match:
                        show_date_raw = date_match.group(2)
                        year_match = re.search(r'(\d{4})', last_update)
                        year = int(year_match.group(1)) if year_match else datetime.now().year
                        show_date = parse_chinese_date(show_date_raw, year) or "未知"
                
                doc_data = {
                    "movie_id": movie_id,
                    "title": title,
                    "introduce": introduce,
                    "picture": picture,
                    "hyperlink": hyperlink,
                    "showDate": show_date,
                    "showLength": show_length,
                    "rate": rate,
                    "rate_code": rate_code,
                    "lastUpdate": last_update,
                    "crawlTime": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
                
                doc_ref = db.collection("電影含分級").document(movie_id)
                doc_ref.set(doc_data)
                count += 1
                movies.append(title)
                
            except Exception as e:
                print(f"存入失敗：{str(e)}")
                continue
        
        return jsonify({
            "success": True,
            "message": f"爬蟲完成！成功存入 {count} 部電影",
            "lastUpdate": last_update,
            "movies": movies[:20]
        })
        
    except Exception as e:
        return jsonify({"error": f"爬蟲失敗：{str(e)}"}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """查看資料庫統計"""
    if db is None:
        return jsonify({"error": "資料庫未連線"}), 500
    
    try:
        docs = db.collection("電影含分級").get()
        total = len(docs)
        
        rate_stats = {}
        for doc in docs:
            rate = doc.to_dict().get("rate", "未知")
            rate_stats[rate] = rate_stats.get(rate, 0) + 1
        
        return jsonify({
            "success": True,
            "total_movies": total,
            "rate_distribution": rate_stats,
            "last_check": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== 處理函數 ====================
def handle_rate_query(parameters):
    """處理只查詢分級的請求"""
    rate_param = parameters.get("rate", "")
    rate = normalize_rate(rate_param)
    
    try:
        docs = db.collection("電影含分級").where("rate", "==", rate).limit(20).get()
        
        if not docs:
            return make_response(jsonify({
                "fulfillmentText": f"目前沒有「{rate}」的電影紀錄。\n\n請先執行爬蟲更新資料：{os.environ.get('VERCEL_URL', 'localhost')}/api/crawl"
            }))
        
        response_text = f"🎬 找到 {len(docs)} 部「{rate}」電影：\n\n"
        for i, doc in enumerate(docs[:10], 1):
            data = doc.to_dict()
            response_text += f"{i}. 【{data.get('title', '未知')}】\n"
            response_text += f"   上映：{data.get('showDate', '日期待確認')}\n"
            response_text += f"   {data.get('hyperlink', '#')}\n\n"
        
        return make_response(jsonify({"fulfillmentText": response_text}))
        
    except Exception as e:
        return make_response(jsonify({
            "fulfillmentText": f"查詢失敗：{str(e)}"
        }))

def handle_this_week_query(parameters):
    """處理只查詢本週上映的請求"""
    try:
        all_docs = db.collection("電影含分級").get()
        
        this_week_movies = []
        for doc in all_docs:
            data = doc.to_dict()
            show_date = data.get("showDate", "")
            if show_date and show_date != "未知" and is_date_in_this_week(show_date):
                this_week_movies.append(data)
        
        if not this_week_movies:
            return make_response(jsonify({
                "fulfillmentText": "本週沒有上映的電影。\n\n請先執行爬蟲更新資料或查詢其他週。"
            }))
        
        response_text = f"📅 本週上映電影（共 {len(this_week_movies)} 部）：\n\n"
        for i, movie in enumerate(this_week_movies[:10], 1):
            response_text += f"{i}. 【{movie.get('title', '未知')}】\n"
            response_text += f"   分級：{movie.get('rate', '未分級')}\n"
            response_text += f"   上映：{movie.get('showDate', '日期待確認')}\n\n"
        
        return make_response(jsonify({"fulfillmentText": response_text}))
        
    except Exception as e:
        return make_response(jsonify({
            "fulfillmentText": f"查詢失敗：{str(e)}"
        }))

def handle_rate_with_week_query(parameters):
    """處理綜合查詢"""
    rate_param = parameters.get("rate", "")
    rate = normalize_rate(rate_param)
    
    try:
        docs = db.collection("電影含分級").where("rate", "==", rate).get()
        
        matched_movies = []
        for doc in docs:
            data = doc.to_dict()
            show_date = data.get("showDate", "")
            if show_date and show_date != "未知" and is_date_in_this_week(show_date):
                matched_movies.append(data)
        
        if not matched_movies:
            return make_response(jsonify({
                "fulfillmentText": f"本週沒有上映的「{rate}」電影。\n\n建議查詢不限本週的 {rate} 電影。"
            }))
        
        response_text = f"🎬 本週上映的「{rate}」電影（共 {len(matched_movies)} 部）：\n\n"
        for i, movie in enumerate(matched_movies[:10], 1):
            response_text += f"{i}. 【{movie.get('title', '未知')}】\n"
            response_text += f"   上映：{movie.get('showDate', '日期待確認')}\n"
            response_text += f"   片長：{movie.get('showLength', 0)} 分鐘\n\n"
        
        return make_response(jsonify({"fulfillmentText": response_text}))
        
    except Exception as e:
        return make_response(jsonify({
            "fulfillmentText": f"查詢失敗：{str(e)}"
        }))

# Vercel 需要這個 handler
app.debug = False

# 這個是給 Vercel 使用的
handler = app
