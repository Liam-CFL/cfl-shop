#!/usr/bin/env python3
"""
Shop Xu Su Kien CFL - Backend Server
"""
import json, os, hashlib, shutil, threading, time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

DATA_FILE = "data.json"
PORT = int(os.environ.get("PORT", 8080))
BACKUP_DIR = "backup"
MAX_BACKUPS = 30
BACKUP_INTERVAL = 24 * 60 * 60

# ========== DEFAULT DATA ==========
DEFAULT_DATA = {
    "settings": {
        "shop_name": "Shop Xu Sự Kiện CFL",
        "zalo": "0964149813",
        "admin_name": "Nguyễn Chí Cường",
        "bank_name": "MB Bank",
        "bank_number": "09090669999",
        "bank_owner": "NGUYEN TRAN CHI CUONG",
        "momo": "",
        "announcement": "🔥 Chào mừng đến với Shop Xu Sự Kiện CFL uy tín - nhanh chóng - giá tốt!",
    },
    "prices": [
        {"id": "xu_sk",  "name": "Xu Sự Kiện", "price": 30000, "unit": "xu", "note": "Liên hệ Zalo để đặt", "active": True},
        {"id": "xu_th",  "name": "Xu Thường",  "price": 4000,  "unit": "xu", "note": "Đặt qua shop",        "active": True},
    ],
    "accounts": [
        {
            "id": "admin",
            "username": "admin",
            "name": "Nguyễn Chí Cường",
            "pin_hash": hashlib.sha256("admin123".encode()).hexdigest(),
            "role": "admin",
            "balance": 0,
            "created": datetime.now().strftime("%d/%m/%Y"),
        }
    ],
    "topups": [],
    "orders": [],
}

AVATAR_COLORS = [
    {"color": "#f59e0b", "bg": "#1a1400"},
    {"color": "#10b981", "bg": "#001a0e"},
    {"color": "#3b82f6", "bg": "#00091a"},
    {"color": "#f43f5e", "bg": "#1a0008"},
    {"color": "#a855f7", "bg": "#0e001a"},
    {"color": "#06b6d4", "bg": "#001519"},
]

# ========== DATA HELPERS ==========
def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
        return json.loads(json.dumps(DEFAULT_DATA))
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        d = json.load(f)
    # ensure keys
    for k, v in DEFAULT_DATA.items():
        if k not in d:
            d[k] = v
    return d

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def safe_account(a):
    return {k: v for k, v in a.items() if k != "pin_hash"}

# ========== AUTO BACKUP ==========
def do_backup():
    if not os.path.exists(DATA_FILE): return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dest = os.path.join(BACKUP_DIR, "data_{}.json".format(datetime.now().strftime("%Y-%m-%d_%H-%M")))
    shutil.copy2(DATA_FILE, dest)
    files = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".json")])
    while len(files) > MAX_BACKUPS:
        os.remove(os.path.join(BACKUP_DIR, files.pop(0)))

def backup_loop():
    time.sleep(5)
    do_backup()
    while True:
        time.sleep(BACKUP_INTERVAL)
        do_backup()

# ========== HTTP HANDLER ==========
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, mime):
        with open(path, "rb") as f: body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            if os.path.exists("index.html"):
                self.send_file("index.html", "text/html; charset=utf-8")
            else:
                self.send_json(404, {"error": "index.html not found"})
            return
        d = load_data()
        routes = {
            "/api/settings":     lambda: d["settings"],
            "/api/prices":       lambda: d["prices"],
            "/api/topups":       lambda: d["topups"],
            "/api/orders":       lambda: d["orders"],
            "/api/accounts/all": lambda: [safe_account(a) for a in d["accounts"]],
        }
        if p in routes:
            self.send_json(200, routes[p]())
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path).path
        b = self.read_body()
        d = load_data()

        # --- AUTH ---
        if p == "/api/login":
            username = b.get("username", "").strip().lower()
            pw = b.get("password", "")
            acc = next((a for a in d["accounts"] if a["username"].lower() == username), None)
            if acc and acc["pin_hash"] == hash_pw(pw):
                self.send_json(200, {"ok": True, "account": safe_account(acc)})
            else:
                self.send_json(401, {"ok": False, "error": "Sai tên đăng nhập hoặc mật khẩu"})
            return

        if p == "/api/register":
            username = b.get("username", "").strip()
            name     = b.get("name", "").strip()
            pw       = b.get("password", "")
            if not username or not name or not pw:
                self.send_json(400, {"ok": False, "error": "Vui lòng điền đầy đủ thông tin"})
                return
            if len(pw) < 6:
                self.send_json(400, {"ok": False, "error": "Mật khẩu phải từ 6 ký tự"})
                return
            if any(a["username"].lower() == username.lower() for a in d["accounts"]):
                self.send_json(400, {"ok": False, "error": "Tên đăng nhập đã tồn tại"})
                return
            idx = len([a for a in d["accounts"] if a["role"] == "user"])
            style = AVATAR_COLORS[idx % len(AVATAR_COLORS)]
            new_acc = {
                "id":       "u" + str(int(time.time()*1000)),
                "username": username,
                "name":     name,
                "pin_hash": hash_pw(pw),
                "role":     "user",
                "balance":  0,
                "color":    style["color"],
                "bg":       style["bg"],
                "created":  datetime.now().strftime("%d/%m/%Y"),
            }
            d["accounts"].append(new_acc)
            save_data(d)
            self.send_json(200, {"ok": True, "account": safe_account(new_acc)})
            return

        # --- TOPUP (admin duyệt tay) ---
        if p == "/api/topup/request":
            uid    = b.get("uid")
            amount = int(b.get("amount", 0))
            method = b.get("method", "")
            note   = b.get("note", "")
            if amount < 10000:
                self.send_json(400, {"ok": False, "error": "Số tiền tối thiểu 10,000đ"})
                return
            req = {
                "id":     "tp" + str(int(time.time()*1000)),
                "uid":    uid,
                "amount": amount,
                "method": method,
                "note":   note,
                "status": "pending",
                "time":   datetime.now().strftime("%d/%m/%Y %H:%M"),
            }
            d["topups"].append(req)
            save_data(d)
            self.send_json(200, {"ok": True, "topup": req})
            return

        if p == "/api/topup/approve":
            tid    = b.get("id")
            amount = int(b.get("amount", 0))
            for tp in d["topups"]:
                if tp["id"] == tid:
                    if tp["status"] == "approved":
                        self.send_json(400, {"ok": False, "error": "Đã duyệt rồi"})
                        return
                    tp["status"] = "approved"
                    tp["approved_time"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    for acc in d["accounts"]:
                        if acc["id"] == tp["uid"]:
                            acc["balance"] = acc.get("balance", 0) + tp["amount"]
                    break
            save_data(d)
            self.send_json(200, {"ok": True})
            return

        if p == "/api/topup/reject":
            tid = b.get("id")
            for tp in d["topups"]:
                if tp["id"] == tid:
                    tp["status"] = "rejected"
                    tp["reject_time"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    break
            save_data(d)
            self.send_json(200, {"ok": True})
            return

        # --- ORDER ---
        if p == "/api/order":
            uid      = b.get("uid")
            price_id = b.get("price_id")
            qty      = int(b.get("qty", 1))
            game_id  = b.get("game_id", "")
            acc = next((a for a in d["accounts"] if a["id"] == uid), None)
            price = next((p2 for p2 in d["prices"] if p2["id"] == price_id), None)
            if not acc or not price:
                self.send_json(400, {"ok": False, "error": "Dữ liệu không hợp lệ"})
                return
            total = price["price"] * qty
            if acc.get("balance", 0) < total:
                self.send_json(400, {"ok": False, "error": "Số dư không đủ"})
                return
            acc["balance"] -= total
            order = {
                "id":         "od" + str(int(time.time()*1000)),
                "uid":        uid,
                "uname":      acc["name"],
                "price_id":   price_id,
                "price_name": price["name"],
                "qty":        qty,
                "total":      total,
                "game_id":    game_id,
                "status":     "pending",
                "time":       datetime.now().strftime("%d/%m/%Y %H:%M"),
            }
            d["orders"].append(order)
            save_data(d)
            self.send_json(200, {"ok": True, "order": order, "new_balance": acc["balance"]})
            return

        if p == "/api/order/complete":
            oid = b.get("id")
            for od in d["orders"]:
                if od["id"] == oid:
                    od["status"] = "completed"
                    od["done_time"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                    break
            save_data(d)
            self.send_json(200, {"ok": True})
            return

        if p == "/api/order/cancel":
            oid = b.get("id")
            for od in d["orders"]:
                if od["id"] == oid and od["status"] == "pending":
                    od["status"] = "cancelled"
                    # hoàn tiền
                    for acc in d["accounts"]:
                        if acc["id"] == od["uid"]:
                            acc["balance"] = acc.get("balance", 0) + od["total"]
                    break
            save_data(d)
            self.send_json(200, {"ok": True})
            return

        # --- PRICES (admin) ---
        if p == "/api/prices":
            new_p = {
                "id":     "pr" + str(int(time.time()*1000)),
                "name":   b.get("name", ""),
                "price":  int(b.get("price", 0)),
                "unit":   b.get("unit", "xu"),
                "note":   b.get("note", ""),
                "active": True,
            }
            d["prices"].append(new_p)
            save_data(d)
            self.send_json(200, {"ok": True, "price": new_p})
            return

        # --- SETTINGS (admin) ---
        if p == "/api/settings":
            for k, v in b.items():
                if k in d["settings"]:
                    d["settings"][k] = v
            save_data(d)
            self.send_json(200, {"ok": True})
            return

        # --- BALANCE ADJUST (admin) ---
        if p == "/api/balance/adjust":
            uid    = b.get("uid")
            amount = int(b.get("amount", 0))
            for acc in d["accounts"]:
                if acc["id"] == uid:
                    acc["balance"] = max(0, acc.get("balance", 0) + amount)
                    self.send_json(200, {"ok": True, "new_balance": acc["balance"]})
                    save_data(d)
                    return
            self.send_json(404, {"ok": False})
            return

        if p == "/api/backup/now":
            do_backup()
            self.send_json(200, {"ok": True})
            return

        self.send_json(404, {"error": "not found"})

    def do_PUT(self):
        p = urlparse(self.path).path
        b = self.read_body()
        d = load_data()

        if p.startswith("/api/prices/"):
            pid = p.split("/")[-1]
            for pr in d["prices"]:
                if pr["id"] == pid:
                    pr.update({k: b[k] for k in ["name","price","unit","note","active"] if k in b})
            save_data(d)
            self.send_json(200, {"ok": True})
            return

        self.send_json(404, {"error": "not found"})

    def do_DELETE(self):
        p = urlparse(self.path).path
        d = load_data()

        if p.startswith("/api/prices/"):
            pid = p.split("/")[-1]
            d["prices"] = [pr for pr in d["prices"] if pr["id"] != pid]
            save_data(d)
            self.send_json(200, {"ok": True})
            return

        if p.startswith("/api/accounts/"):
            uid = p.split("/")[-1]
            if uid == "admin":
                self.send_json(400, {"ok": False, "error": "Không xóa được admin"})
                return
            d["accounts"] = [a for a in d["accounts"] if a["id"] != uid]
            save_data(d)
            self.send_json(200, {"ok": True})
            return

        self.send_json(404, {"error": "not found"})


# ========== START ==========
if __name__ == "__main__":
    import socket
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except:
        local_ip = "127.0.0.1"

    threading.Thread(target=backup_loop, daemon=True).start()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print("=" * 55)
    print("  SHOP XU SU KIEN CFL - SERVER")
    print("=" * 55)
    print("  Local  : http://localhost:{}".format(PORT))
    print("  Network: http://{}:{}".format(local_ip, PORT))
    print("  Admin  : username=admin  password=admin123")
    print("  [!] Doi mat khau admin sau khi dang nhap!")
    print("=" * 55)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
