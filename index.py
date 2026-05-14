from flask import Flask, request, make_response, jsonify, render_template
import requests
from bs4 import BeautifulSoup
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)

# 初始化 Firebase（請將金鑰檔案放在同目錄下）
try:
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase 初始化成功")
except Exception as e:
    print("Firebase 初始化失敗：", e)
    db = None

# ==================== 爬蟲功能 ====================
@app.route("/")
def index():
    return '<a href="/rate">開始爬取開眼電影資訊（含分級）</a>'

@app.route("/rate")
def rate():
    if db is None:
        return "Firebase 未初始化，請檢查金鑰檔案"

    url = "https://www.atmovies.com.tw/movie/new/"
    Data = requests.get(url)
    Data.encoding = "utf-8"
    sp = BeautifulSoup(Data.text, "html.parser")
    lastUpdate = sp.find(class_="smaller09").text[5:]
    print("最後更新日期：", lastUpdate)

    result = sp.select(".filmList")
    count = 0

    for x in result:
        title = x.find("a").text
        introduce = x.find("p").text

        movie_id = x.find("a").get("href").replace("/", "").replace("movie", "")
        hyperlink = "http://www.atmovies.com.tw/movie/" + movie_id
        picture = "https://www.atmovies.com.tw/photo101/" + movie_id + "/pm_" + movie_id + ".jpg"

        # 處理分級
        r = x.find(class_="runtime").find("img")
        rate = ""
        if r != None:
            rr = r.get("src").replace("/images/cer_", "").replace(".gif", "")
            if rr == "G":
                rate = "普遍級"
            elif rr == "P":
                rate = "保護級"
            elif rr == "F2":
                rate = "輔12級"
            elif rr == "F5":
                rate = "輔15級"
            else:
                rate = "限制級"

        t = x.find(class_="runtime").text

        # 處理片長
        t1 = t.find("片長")
        t2 = t.find("分")
        showLength = t[t1+3:t2] if t1 != -1 and t2 != -1 else "0"

        # 處理上映日期
        t1 = t.find("上映日期")
        t2 = t.find("上映廳數")
        showDate = t[t1+5:t2-8] if t1 != -1 and t2 != -1 else "未知"

        doc = {
            "title": title,
            "introduce": introduce,
            "picture": picture,
            "hyperlink": hyperlink,
            "showDate": showDate,
            "showLength": int(showLength) if showLength.isdigit() else 0,
            "rate": rate,
            "lastUpdate": lastUpdate
        }

        try:
            doc_ref = db.collection("電影含分級").document(movie_id)
            doc_ref.set(doc)
            count += 1
            print(f"已存入：{title} ({rate})")
        except Exception as e:
            print(f"存入失敗：{title} - {e}")

    return f"爬蟲完成！共存入 {count} 部電影，網站最近更新日期為：{lastUpdate}"

# ==================== Webhook 查詢功能 ====================
@app.route("/webhook", methods=["POST"])
def webhook():
    if db is None:
        return make_response(jsonify({"fulfillmentText": "資料庫連線失敗，請檢查設定"}))

    req = request.get_json(force=True)
    action = req.get("queryResult").get("action")

    if action == "rateChoice":
        rate_param = req.get("queryResult").get("parameters").get("rate")

        # 同義詞對應（支援 Dialogflow Entity 的同義詞）
        rate_map = {
            "普遍級": "普遍級", "G級": "普遍級", "普級": "普遍級",
            "保護級": "保護級", "P級": "保護級", "護級": "保護級",
            "輔12級": "輔12級", "PG12級": "輔12級",
            "輔15級": "輔15級", "PG15級": "輔15級",
            "限制級": "限制級", "R級": "限制級", "限級": "限制級"
        }
        rate = rate_map.get(rate_param, rate_param)

        info = f"我是楊子青開發的電影聊天機器人，您選擇的電影分級是：{rate}，相關電影：\n"

        try:
            collection_ref = db.collection("電影含分級")
            docs = collection_ref.where("rate", "==", rate).get()

            result = ""
            for doc in docs:
                dict_data = doc.to_dict()
                result += f"🎬 片名：{dict_data.get('title', '未知')}\n"
                result += f"📖 介紹：{dict_data.get('hyperlink', '無連結')}\n\n"

            if result == "":
                result = f"目前沒有找到「{rate}」的電影，請稍後再試試看。\n"

            info += result

        except Exception as e:
            info = f"查詢資料庫時發生錯誤：{str(e)}"

        return make_response(jsonify({"fulfillmentText": info}))

    # 如果沒有匹配的 action
    return make_response(jsonify({"fulfillmentText": "請詢問電影分級相關問題，例如：推薦保護級的電影"}))

# ==================== 測試用 GET 路由 ====================
@app.route("/webhook", methods=["GET"])
def webhook_get():
    return "Webhook 正常運作，請使用 POST 方式發送請求。"

if __name__ == "__main__":
    app.run(debug=True, port=5000)
