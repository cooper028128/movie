from flask import Flask, request, make_response, jsonify, render_template
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import re
import os
from google.cloud.firestore import FirestoreProperty

app = Flask(__name__)

# ==================== Firebase 初始化 ====================
def init_firebase():
    """初始化 Firebase，支援環境變數或金鑰檔案"""
    try:
        # 優先使用環境變數（更安全）
        if os.getenv('FIREBASE_KEY_JSON'):
            import json
            key_dict = json.loads(os.getenv('FIREBASE_KEY_JSON'))
            cred = credentials.Certificate(key_dict)
        # 其次使用金鑰檔案
        elif os.path.exists("firebase-key.json"):
            cred = credentials.Certificate("firebase-key.json")
        else:
            print("找不到 Firebase 金鑰，請設定環境變數 FIREBASE_KEY_JSON 或放置 firebase-key.json")
            return None
        
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
    """
    解析中文日期格式，例如：「01月15日」→ "2025-01-15"
    """
    if not date_str or date_str == "未知":
        return None
    
    if reference_year is None:
        reference_year = datetime.now().year
    
    # 格式1: 01月15日
    match = re.match(r'(\d{1,2})月(\d{1,2})日', date_str)
    if match:
        month, day = int(match.group(1)), int(match.group(2))
        try:
            return datetime(reference_year, month, day).strftime('%Y-%m-%d')
        except ValueError:
            return None
    
    # 格式2: 2025-01-15 或 2025/01/15
    match = re.match(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', date_str)
    if match:
        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        try:
            return datetime(year, month, day).strftime('%Y-%m-%d')
        except ValueError:
            return None
    
    return None

def is_date_in_this_week(date_str):
    """判斷日期是否在本週內（週一到週日）"""
    if not date_str:
        return False
    
    try:
        # 嘗試解析日期
        if '-' in date_str:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        elif '/' in date_str:
            date_obj = datetime.strptime(date_str, '%Y/%m/%d').date()
        else:
            return False
        
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())  # 週一
        end_of_week = start_of_week + timedelta(days=6)  # 週日
        
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

# ==================== 爬蟲功能 ====================
@app.route("/")
def index():
    return '''
    <h1>電影資訊爬蟲系統</h1>
    <ul>
        <li><a href="/crawl">開始爬取開眼電影資訊</a></li>
        <li><a href="/webhook">Webhook 測試頁面</a></li>
    </ul>
    '''

@app.route("/crawl")
def crawl_movies():
    """爬取開眼電影最新電影資訊"""
    if db is None:
        return "Firebase 未初始化，請檢查設定", 500
    
    try:
        url = "https://www.atmovies.com.tw/movie/new/"
        response = requests.get(url, timeout=30)
        response.encoding = "utf-8"
        
        if response.status_code != 200:
            return f"網站回應錯誤：HTTP {response.status_code}", 500
        
        sp = BeautifulSoup(response.text, "html.parser")
        
        # 取得最後更新日期
        last_update_elem = sp.find(class_="smaller09")
        last_update = last_update_elem.text[5:] if last_update_elem else "未知"
        print(f"最後更新日期：{last_update}")
        
        # 解析電影列表
        film_list = sp.select(".filmList")
        if not film_list:
            return "找不到電影列表，網站結構可能已改變", 500
        
        count = 0
        errors = []
        
        for idx, film in enumerate(film_list, 1):
            try:
                # 基本資訊
                title_elem = film.find("a")
                if not title_elem:
                    continue
                title = title_elem.text.strip()
                
                # 介紹
                intro_elem = film.find("p")
                introduce = intro_elem.text.strip() if intro_elem else "無介紹"
                
                # 電影ID和連結
                movie_path = title_elem.get("href", "")
                movie_id = movie_path.replace("/", "").replace("movie", "")
                hyperlink = f"http://www.atmovies.com.tw/movie/{movie_id}"
                picture = f"https://www.atmovies.com.tw/photo101/{movie_id}/pm_{movie_id}.jpg"
                
                # 分級資訊
                runtime_elem = film.find(class_="runtime")
                rate_code = ""
                rate = "未分級"
                
                if runtime_elem:
                    img = runtime_elem.find("img")
                    if img and img.get("src"):
                        src = img.get("src")
                        rate_code = src.replace("/images/cer_", "").replace(".gif", "")
                        rate = get_rate_chinese(rate_code)
                    
                    # 解析片長和上映日期
                    runtime_text = runtime_elem.text
                    
                    # 片長
                    length_match = re.search(r'片長[：:]\s*(\d+)', runtime_text)
                    if length_match:
                        show_length = int(length_match.group(1))
                    else:
                        length_match = re.search(r'片長(\d+)分', runtime_text)
                        show_length = int(length_match.group(1)) if length_match else 0
                    
                    # 上映日期
                    date_match = re.search(r'上映日期[：:]\s*([^\d]+)?(\d{1,2}月\d{1,2}日|\d{4}[-/]\d{1,2}[-/]\d{1,2})', runtime_text)
                    if date_match:
                        show_date_raw = date_match.group(2)
                        # 從 last_update 推測年份
                        year_match = re.search(r'(\d{4})', last_update)
                        year = int(year_match.group(1)) if year_match else datetime.now().year
                        show_date = parse_chinese_date(show_date_raw, year) or "未知"
                    else:
                        show_date = "未知"
                else:
                    show_length = 0
                    show_date = "未知"
                
                # 儲存到 Firebase
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
                print(f"[{idx}] ✓ 已存入：{title} ({rate})")
                
            except Exception as e:
                error_msg = f"第 {idx} 筆存入失敗：{str(e)}"
                print(error_msg)
                errors.append(error_msg)
        
        result_msg = f"爬蟲完成！成功存入 {count} 部電影，網站更新日期：{last_update}"
        if errors:
            result_msg += f"\n\n錯誤訊息：\n" + "\n".join(errors[:5])
        
        return result_msg.replace("\n", "<br>")
        
    except requests.RequestException as e:
        return f"網路請求失敗：{str(e)}", 500
    except Exception as e:
        return f"爬蟲過程發生錯誤：{str(e)}", 500

# ==================== Webhook 查詢功能 ====================
@app.route("/webhook", methods=["POST"])
def webhook():
    """處理 Dialogflow 的 Webhook 請求"""
    if db is None:
        return make_response(jsonify({
            "fulfillmentText": "資料庫連線失敗，請稍後再試。",
            "fulfillmentMessages": [{
                "text": {"text": ["系統維護中，請稍後再試。"]}
            }]
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
        
        # 處理綜合查詢（分級 + 本週）
        elif action == "rateWithWeek":
            return handle_rate_with_week_query(parameters)
        
        # 預設回應
        else:
            return make_response(jsonify({
                "fulfillmentText": "您好！我可以幫您查詢電影資訊。\n\n您可以這樣問：\n• 推薦保護級的電影\n• 本週上映哪些電影\n• 本週有上映的保護級電影",
                "fulfillmentMessages": [{
                    "text": {"text": ["您好！我可以幫您查詢電影資訊。\n\n您可以這樣問：\n• 推薦保護級的電影\n• 本週上映哪些電影\n• 本週有上映的保護級電影"]}
                }]
            }))
    
    except Exception as e:
        print(f"Webhook 錯誤：{str(e)}")
        return make_response(jsonify({
            "fulfillmentText": f"處理請求時發生錯誤：{str(e)}"
        }))

def handle_rate_query(parameters):
    """處理只查詢分級的請求"""
    rate_param = parameters.get("rate", "")
    rate = normalize_rate(rate_param)
    
    try:
        docs = db.collection("電影含分級").where("rate", "==", rate).limit(20).get()
        
        if not docs:
            return make_response(jsonify({
                "fulfillmentText": f"目前資料庫中沒有「{rate}」的電影紀錄。\n\n建議：\n• 先執行爬蟲更新資料 (/crawl)\n• 或查詢其他分級"
            }))
        
        movies = []
        for doc in docs:
            data = doc.to_dict()
            movies.append({
                "title": data.get("title", "未知"),
                "hyperlink": data.get("hyperlink", "#"),
                "showDate": data.get("showDate", "日期待確認")
            })
        
        # 建立回應
        response_text = f"🎬 找到 {len(movies)} 部「{rate}」電影：\n\n"
        for i, movie in enumerate(movies[:10], 1):
            response_text += f"{i}. 【{movie['title']}】\n"
            response_text += f"   上映日期：{movie['showDate']}\n"
            response_text += f"   詳情：{movie['hyperlink']}\n\n"
        
        if len(movies) > 10:
            response_text += f"...還有 {len(movies) - 10} 部電影，請說「更多」繼續查詢。"
        
        return make_response(jsonify({"fulfillmentText": response_text}))
        
    except Exception as e:
        return make_response(jsonify({
            "fulfillmentText": f"查詢資料庫時發生錯誤：{str(e)}"
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
            today = datetime.now()
            week_range = f"{today.strftime('%m/%d')}~{(today + timedelta(days=6)).strftime('%m/%d')}"
            return make_response(jsonify({
                "fulfillmentText": f"本週（{week_range}）沒有找到上映的電影。\n\n建議：\n• 先執行爬蟲更新資料 (/crawl)\n• 或查詢其他週的電影"
            }))
        
        response_text = f"📅 本週上映電影（共 {len(this_week_movies)} 部）：\n\n"
        for i, movie in enumerate(this_week_movies[:10], 1):
            response_text += f"{i}. 【{movie.get('title', '未知')}】\n"
            response_text += f"   分級：{movie.get('rate', '未分級')}\n"
            response_text += f"   上映日期：{movie.get('showDate', '日期待確認')}\n"
            response_text += f"   詳情：{movie.get('hyperlink', '#')}\n\n"
        
        return make_response(jsonify({"fulfillmentText": response_text}))
        
    except Exception as e:
        return make_response(jsonify({
            "fulfillmentText": f"查詢本週電影時發生錯誤：{str(e)}"
        }))

def handle_rate_with_week_query(parameters):
    """處理查詢本週上映 + 特定分級的請求"""
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
            today = datetime.now()
            week_range = f"{today.strftime('%m/%d')}~{(today + timedelta(days=6)).strftime('%m/%d')}"
            return make_response(jsonify({
                "fulfillmentText": f"本週（{week_range}）沒有上映的「{rate}」電影。\n\n建議查詢：\n• 其他分級的電影\n• 不限本週的{rate}電影（直接說「{rate}電影」）"
            }))
        
        response_text = f"🎬 本週上映的「{rate}」電影（共 {len(matched_movies)} 部）：\n\n"
        for i, movie in enumerate(matched_movies[:10], 1):
            response_text += f"{i}. 【{movie.get('title', '未知')}】\n"
            response_text += f"   上映日期：{movie.get('showDate', '日期待確認')}\n"
            response_text += f"   片長：{movie.get('showLength', 0)} 分鐘\n"
            response_text += f"   詳情：{movie.get('hyperlink', '#')}\n\n"
        
        return make_response(jsonify({"fulfillmentText": response_text}))
        
    except Exception as e:
        return make_response(jsonify({
            "fulfillmentText": f"查詢時發生錯誤：{str(e)}"
        }))

# ==================== 測試與管理路由 ====================
@app.route("/webhook", methods=["GET"])
def webhook_get():
    """GET 方法測試"""
    return jsonify({
        "status": "ok",
        "message": "Webhook 正常運作，請使用 POST 方式發送請求。",
        "endpoints": {
            "crawl": "/crawl - 執行爬蟲更新資料",
            "webhook": "/webhook - Dialogflow Webhook 端點",
            "stats": "/stats - 查看資料庫統計"
        }
    })

@app.route("/stats")
def get_stats():
    """查看資料庫統計資訊"""
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
            "total_movies": total,
            "rate_distribution": rate_stats,
            "last_update": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clear", methods=["POST"])
def clear_database():
    """清空資料庫（僅用於測試）"""
    if db is None:
        return jsonify({"error": "資料庫未連線"}), 500
    
    try:
        docs = db.collection("電影含分級").get()
        deleted = 0
        for doc in docs:
            doc.reference.delete()
            deleted += 1
        return jsonify({"message": f"已刪除 {deleted} 筆資料"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== 主程式 ====================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "True").lower() == "true"
    
    print(f"啟動伺服器，Port: {port}, Debug: {debug}")
    print(f"Firebase 狀態：{'已連線' if db else '未連線'}")
    print("\n可用端點：")
    print("  GET  /          - 首頁")
    print("  GET  /crawl     - 執行爬蟲")
    print("  POST /webhook   - Webhook 端點")
    print("  GET  /stats     - 統計資訊")
    
    app.run(debug=debug, port=port, host="0.0.0.0")
