#!/usr/bin/env python3
"""
Shop Xu Su Kien CFL - Server v4
- PostgreSQL (Supabase) for persistent storage
- Falls back to JSON file if no DB configured
- Telegram Bot notifications (orders, topups, support)
- Auto topup approval
- Coupon / discount code system
"""
import json, os, hashlib, shutil, threading, time, random
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import urllib.request, urllib.parse as uparse

# ========== TELEGRAM BOT ==========
TELEGRAM_BOT_TOKEN = "7654400767:AAEAn3XScjjcavAWnu9g-lG0Q6VBMyF1OQM"
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

def tg_send(msg):
    """Send a message to Telegram (non-blocking)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    def _send():
        try:
            url = "https://api.telegram.org/bot{}/sendMessage".format(TELEGRAM_BOT_TOKEN)
            payload = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}).encode()
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=8)
        except Exception as e:
            print("  [TG] Send error:", e)
    threading.Thread(target=_send, daemon=True).start()

DATA_FILE = "data.json"
PORT = int(os.environ.get("PORT", 8080))
BACKUP_DIR = "backup"
MAX_BACKUPS = 60
BACKUP_INTERVAL = 6 * 60 * 60  # backup every 6h

# ========== DEFAULT DATA ==========
def make_default():
    return {
        "settings": {
            "shop_name": "Shop Xu Su Kien CFL",
            "zalo": "0964149813",
            "fb_page": "https://www.facebook.com/NguyenChiCuong.AC9",
            "bank_name": "MB Bank",
            "bank_number": "09090669999",
            "bank_owner": "NGUYEN TRAN CHI CUONG",
            "momo": "0964149813",
            "momo_owner": "NGUYEN TRAN CHI CUONG",
            "announcement": "Chao mung den voi Shop Xu Su Kien CFL!",
            "spin_cost": 5000,
            "auto_topup": False,
            "telegram_notify_orders": True,
            "telegram_notify_topups": True,
            "telegram_notify_support": True,
            "spin_prizes": [
                {"id":"s1","label":"10,000d","value":10000,"type":"balance","weight":20,"color":"#f5a623"},
                {"id":"s2","label":"5 Xu","value":5,"type":"xu","weight":25,"color":"#00d4ff"},
                {"id":"s3","label":"10 Xu","value":10,"type":"xu","weight":20,"color":"#00ff88"},
                {"id":"s4","label":"50,000d","value":50000,"type":"balance","weight":5,"color":"#a855f7"},
                {"id":"s5","label":"1 Xu","value":1,"type":"xu","weight":30,"color":"#ff6b35"},
                {"id":"s6","label":"100,000d","value":100000,"type":"balance","weight":2,"color":"#ffd166"},
                {"id":"s7","label":"20 Xu","value":20,"type":"xu","weight":10,"color":"#ff3366"},
                {"id":"s8","label":"Thu lai","value":0,"type":"none","weight":15,"color":"#3a3a60"}
            ]
        },
        "ranks": [
            {"id":"bronze","name":"Khách lẻ","min_spent":0,"color":"#cd7f32","discount":3},
            {"id":"silver","name":"Cộng Tác Viên","min_spent":200000,"color":"#c0c0c0","discount":10},
            {"id":"gold","name":"Đại Lí","min_spent":3000000,"color":"#f5a623","discount":20},
            {"id":"diamond","name":"Tổng Đại lí","min_spent":10000000,"color":"#00d4ff","discount":30}
        ],
        "accounts": [
            {"id":"admin","username":"admin","name":"Nguyen Chi Cuong",
             "pin_hash":hashlib.sha256("admin123".encode()).hexdigest(),
             "role":"admin","balance":0,"total_spent":0,"rank":"diamond","created":datetime.now().strftime("%d/%m/%Y")}
        ],
        "prices": [
            {"id":"xu_sk","name":"Xu Su Kien","price":30000,"unit":"xu","note":"Lien he Zalo","active":True},
            {"id":"xu_th","name":"Xu Thuong","price":4000,"unit":"xu","note":"Giao nhanh","active":True}
        ],
        "cf_packages": [
            {"id":"cf1","name":"5,000 Xu CF","xu":5000,"price":50000,"bonus":"","active":True},
            {"id":"cf2","name":"10,000 Xu CF","xu":10000,"price":95000,"bonus":"Bonus 5%","active":True},
            {"id":"cf3","name":"25,000 Xu CF","xu":25000,"price":230000,"bonus":"Bonus 8%","active":True},
            {"id":"cf4","name":"50,000 Xu CF","xu":50000,"price":450000,"bonus":"Bonus 10%","active":True}
        ],
        "topups": [],
        "orders": [],
        "spin_history": [],
        "subwebs": [],
        "posts": [],
        "svc_tabs": [],
        "coupons": [],
        "support_requests": []
    }

AVATAR_COLORS = [
    {"color":"#f59e0b","bg":"#1a1400"},{"color":"#10b981","bg":"#001a0e"},
    {"color":"#3b82f6","bg":"#00091a"},{"color":"#f43f5e","bg":"#1a0008"},
    {"color":"#a855f7","bg":"#0e001a"},{"color":"#06b6d4","bg":"#001519"}
]

# ========== POSTGRES SUPPORT ==========
DB_URL = os.environ.get("DATABASE_URL", "")
db_conn = None

def get_db():
    global db_conn
    if not DB_URL:
        return None
    try:
        import psycopg2
        if db_conn is None or db_conn.closed:
            db_conn = psycopg2.connect(DB_URL, sslmode='require')
        return db_conn
    except Exception as e:
        print("  [DB] Cannot connect:", e)
        return None

def db_init():
    conn = get_db()
    if not conn:
        return False
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS store (
                key VARCHAR(50) PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.commit()
        cur.close()
        print("  [DB] PostgreSQL connected and ready!")
        return True
    except Exception as e:
        print("  [DB] Init error:", e)
        return False

def load_data():
    conn = get_db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT value FROM store WHERE key='data'")
            row = cur.fetchone()
            cur.close()
            if row:
                d = json.loads(row[0])
                _ensure_defaults(d)
                return d
        except Exception as e:
            print("  [DB] Load error:", e)
    # fallback to file
    if not os.path.exists(DATA_FILE):
        d = make_default()
        save_data(d)
        return d
    with open(DATA_FILE,"r",encoding="utf-8") as f:
        d = json.load(f)
    _ensure_defaults(d)
    return d

def save_data(data):
    conn = get_db()
    jdata = json.dumps(data, ensure_ascii=False)
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO store (key, value, updated_at)
                VALUES ('data', %s, NOW())
                ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()
            """, (jdata,))
            conn.commit()
            cur.close()
        except Exception as e:
            print("  [DB] Save error:", e)
            try: conn.rollback()
            except: pass
    # always save to file as backup
    with open(DATA_FILE,"w",encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _ensure_defaults(d):
    ddef = make_default()
    for k,v in ddef.items():
        if k not in d: d[k] = v
    for k,v in ddef["settings"].items():
        if k not in d["settings"]: d["settings"][k] = v
    if "coupons" not in d: d["coupons"] = []
    if "support_requests" not in d: d["support_requests"] = []

# ========== BACKUP ==========
def do_backup():
    if not os.path.exists(DATA_FILE): return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dest = os.path.join(BACKUP_DIR, "data_{}.json".format(datetime.now().strftime("%Y-%m-%d_%H-%M")))
    shutil.copy2(DATA_FILE, dest)
    files = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".json")])
    while len(files) > MAX_BACKUPS: os.remove(os.path.join(BACKUP_DIR, files.pop(0)))

def backup_loop():
    time.sleep(10); do_backup()
    while True: time.sleep(BACKUP_INTERVAL); do_backup()

# ========== HELPERS ==========
def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def safe_acc(a): return {k:v for k,v in a.items() if k!="pin_hash"}
def get_rank(ranks, total_spent):
    sranks = sorted(ranks, key=lambda r: r["min_spent"], reverse=True)
    for r in sranks:
        if total_spent >= r["min_spent"]: return r["id"]
    return ranks[0]["id"] if ranks else "bronze"

# ========== HTTP ==========
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass

    def sj(self,code,obj):
        b=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(b)))
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers(); self.wfile.write(b)

    def sf(self,path,mime):
        with open(path,"rb") as f: b=f.read()
        self.send_response(200)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def rb(self):
        n=int(self.headers.get("Content-Length",0))
        return json.loads(self.rfile.read(n)) if n else {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed=urlparse(self.path)
        p=parsed.path
        if p in ("/","/index.html"):
            if os.path.exists("index.html"): self.sf("index.html","text/html; charset=utf-8")
            else: self.sj(404,{"error":"index.html not found"})
            return
        # sub-web ref lookup
        if p=="/api/subweb/ref":
            from urllib.parse import parse_qs
            qs=parse_qs(parsed.query)
            ref=qs.get("ref",[""])[0].strip().lower()
            d2=load_data()
            if ref:
                acc=next((a for a in d2["accounts"] if a["username"].lower()==ref),None)
                if acc:
                    sw=next((w for w in d2.get("subwebs",[]) if w["uid"]==acc["id"]),None)
                    if sw:self.sj(200,{"ok":True,"web":sw,"account":safe_acc(acc)});return
            self.sj(200,{"ok":False});return
        d=load_data()
        routes={
            "/api/settings":     lambda:d["settings"],
            "/api/prices":       lambda:d["prices"],
            "/api/topups":       lambda:d["topups"],
            "/api/orders":       lambda:d["orders"],
            "/api/ranks":        lambda:d["ranks"],
            "/api/cf_packages":  lambda:d.get("cf_packages",[]),
            "/api/spin_history": lambda:d.get("spin_history",[]),
            "/api/accounts/all": lambda:[safe_acc(a) for a in d["accounts"]],
            "/api/subwebs":      lambda:d.get("subwebs",[]),
            "/api/posts":        lambda:d.get("posts",[]),
            "/api/svc_tabs":     lambda:d.get("svc_tabs",[]),
        }
        if p in routes: self.sj(200,routes[p]())
        else: self.sj(404,{"error":"not found"})

    def do_POST(self):
        p=urlparse(self.path).path; b=self.rb(); d=load_data()

        if p=="/api/login":
            un=b.get("username","").strip().lower(); pw=b.get("password","")
            acc=next((a for a in d["accounts"] if a["username"].lower()==un),None)
            if acc and acc["pin_hash"]==hash_pw(pw): self.sj(200,{"ok":True,"account":safe_acc(acc)})
            else: self.sj(401,{"ok":False,"error":"Sai ten dang nhap hoac mat khau"})
            return

        if p=="/api/register":
            un=b.get("username","").strip(); name=b.get("name","").strip(); pw=b.get("password","")
            if not un or not name or not pw: self.sj(400,{"ok":False,"error":"Dien day du thong tin"}); return
            if len(pw)<6: self.sj(400,{"ok":False,"error":"Mat khau phai tu 6 ky tu"}); return
            if any(a["username"].lower()==un.lower() for a in d["accounts"]):
                self.sj(400,{"ok":False,"error":"Ten dang nhap da ton tai"}); return
            idx=len([a for a in d["accounts"] if a["role"]=="user"])
            st=AVATAR_COLORS[idx%len(AVATAR_COLORS)]
            na={"id":"u"+str(int(time.time()*1000)),"username":un,"name":name,
                "pin_hash":hash_pw(pw),"role":"user","balance":0,"total_spent":0,
                "rank":"bronze","color":st["color"],"bg":st["bg"],
                "created":datetime.now().strftime("%d/%m/%Y")}
            d["accounts"].append(na); save_data(d)
            self.sj(200,{"ok":True,"account":safe_acc(na)}); return

        if p=="/api/change_password":
            uid=b.get("uid"); op=b.get("old_password",""); np=b.get("new_password","")
            if len(np)<6: self.sj(400,{"ok":False,"error":"Mat khau moi phai tu 6 ky tu"}); return
            for acc in d["accounts"]:
                if acc["id"]==uid:
                    if acc["pin_hash"]!=hash_pw(op): self.sj(401,{"ok":False,"error":"Mat khau cu khong dung"}); return
                    acc["pin_hash"]=hash_pw(np); save_data(d); self.sj(200,{"ok":True}); return
            self.sj(404,{"ok":False}); return

        if p=="/api/admin/reset_password":
            uid=b.get("uid"); np=b.get("new_password","")
            if len(np)<6: self.sj(400,{"ok":False,"error":"Mat khau phai tu 6 ky tu"}); return
            for acc in d["accounts"]:
                if acc["id"]==uid: acc["pin_hash"]=hash_pw(np); save_data(d); self.sj(200,{"ok":True}); return
            self.sj(404,{"ok":False}); return

        if p=="/api/topup/request":
            uid=b.get("uid"); amt=int(b.get("amount",0)); method=b.get("method",""); note=b.get("note","")
            if amt<10000: self.sj(400,{"ok":False,"error":"Toi thieu 10,000d"}); return
            acc_tp=next((a for a in d["accounts"] if a["id"]==uid),None)
            uname_tp=acc_tp["name"] if acc_tp else uid
            req={"id":"tp"+str(int(time.time()*1000)),"uid":uid,"amount":amt,"method":method,
                 "note":note,"status":"pending","time":datetime.now().strftime("%d/%m/%Y %H:%M")}
            # Auto approve if enabled
            if d["settings"].get("auto_topup",False):
                req["status"]="approved"; req["approved_time"]=datetime.now().strftime("%d/%m/%Y %H:%M")
                if acc_tp: acc_tp["balance"]=acc_tp.get("balance",0)+amt
            d["topups"].append(req); save_data(d)
            # Telegram notification
            if d["settings"].get("telegram_notify_topups",True):
                auto_tag="✅ AUTO DUYỆT" if req["status"]=="approved" else "⏳ Chờ duyệt"
                tg_send(f"💳 <b>YÊU CẦU NẠP TIỀN</b> [{auto_tag}]\n"
                        f"👤 {uname_tp} ({uid})\n"
                        f"💰 {amt:,}đ | {method}\n"
                        f"📝 {note}\n"
                        f"🕐 {req['time']}")
            self.sj(200,{"ok":True,"topup":req,"new_balance":acc_tp.get("balance",0) if acc_tp else 0}); return

        if p=="/api/topup/approve":
            tid=b.get("id")
            for tp in d["topups"]:
                if tp["id"]==tid:
                    if tp["status"]=="approved": self.sj(400,{"ok":False,"error":"Da duyet"}); return
                    tp["status"]="approved"; tp["approved_time"]=datetime.now().strftime("%d/%m/%Y %H:%M")
                    for acc in d["accounts"]:
                        if acc["id"]==tp["uid"]: acc["balance"]=acc.get("balance",0)+tp["amount"]
                    break
            save_data(d); self.sj(200,{"ok":True}); return

        if p=="/api/topup/reject":
            tid=b.get("id")
            for tp in d["topups"]:
                if tp["id"]==tid: tp["status"]="rejected"; break
            save_data(d); self.sj(200,{"ok":True}); return

        if p=="/api/order":
            uid=b.get("uid"); pid=b.get("price_id"); qty=int(b.get("qty",1)); gid=b.get("game_id","")
            coupon_code=b.get("coupon","").strip().upper()
            acc=next((a for a in d["accounts"] if a["id"]==uid),None)
            price=next((pr for pr in d["prices"] if pr["id"]==pid),None)
            if not acc or not price: self.sj(400,{"ok":False,"error":"Du lieu khong hop le"}); return
            rk=next((r for r in d["ranks"] if r["id"]==acc.get("rank","bronze")),None)
            disc=rk["discount"] if rk else 0
            # Apply coupon
            coupon_used=None
            coupon_disc=0
            if coupon_code:
                cp=next((c for c in d.get("coupons",[]) if c["code"]==coupon_code and c["active"]),None)
                if not cp: self.sj(400,{"ok":False,"error":"Mã giảm giá không hợp lệ hoặc đã hết hạn"}); return
                if cp.get("uses",0)>=cp.get("max_uses",9999): self.sj(400,{"ok":False,"error":"Mã giảm giá đã dùng hết"}); return
                coupon_disc=cp["discount"]; coupon_used=cp
            total_disc=min(disc+coupon_disc,100)
            total=int(price["price"]*qty*(1-total_disc/100))
            if acc.get("balance",0)<total: self.sj(400,{"ok":False,"error":"So du khong du"}); return
            acc["balance"]-=total; acc["total_spent"]=acc.get("total_spent",0)+total
            acc["rank"]=get_rank(d["ranks"],acc["total_spent"])
            if coupon_used: coupon_used["uses"]=coupon_used.get("uses",0)+1
            od={"id":"od"+str(int(time.time()*1000)),"uid":uid,"uname":acc["name"],
                "price_id":pid,"price_name":price["name"],"qty":qty,"total":total,
                "discount":total_disc,"coupon":coupon_code if coupon_code else "","game_id":gid,
                "status":"pending","time":datetime.now().strftime("%d/%m/%Y %H:%M")}
            d["orders"].append(od); save_data(d)
            # Telegram
            if d["settings"].get("telegram_notify_orders",True):
                cpn_info=f"\n🎫 Coupon: {coupon_code} (-{coupon_disc}%)" if coupon_code else ""
                tg_send(f"🛒 <b>ĐƠN HÀNG MỚI</b>\n"
                        f"👤 {acc['name']} ({uid})\n"
                        f"📦 {price['name']} x{qty}\n"
                        f"💸 {total:,}đ (giảm {total_disc}%){cpn_info}\n"
                        f"🎮 ID: {gid}\n"
                        f"🕐 {od['time']}")
            self.sj(200,{"ok":True,"order":od,"new_balance":acc["balance"],"new_rank":acc["rank"]}); return

        if p=="/api/cf_order":
            uid=b.get("uid"); pkid=b.get("pkg_id"); gid=b.get("game_id",""); sv=b.get("server","")
            acc=next((a for a in d["accounts"] if a["id"]==uid),None)
            pkg=next((pk for pk in d.get("cf_packages",[]) if pk["id"]==pkid),None)
            if not acc or not pkg: self.sj(400,{"ok":False,"error":"Du lieu khong hop le"}); return
            if acc.get("balance",0)<pkg["price"]: self.sj(400,{"ok":False,"error":"So du khong du"}); return
            acc["balance"]-=pkg["price"]; acc["total_spent"]=acc.get("total_spent",0)+pkg["price"]
            acc["rank"]=get_rank(d["ranks"],acc["total_spent"])
            od={"id":"cf"+str(int(time.time()*1000)),"uid":uid,"uname":acc["name"],
                "type":"cf","pkg_name":pkg["name"],"xu":pkg["xu"],"total":pkg["price"],
                "game_id":gid,"server":sv,"status":"pending","time":datetime.now().strftime("%d/%m/%Y %H:%M")}
            d["orders"].append(od); save_data(d)
            self.sj(200,{"ok":True,"order":od,"new_balance":acc["balance"]}); return

        if p=="/api/order/complete":
            oid=b.get("id")
            for od in d["orders"]:
                if od["id"]==oid: od["status"]="completed"; od["done_time"]=datetime.now().strftime("%d/%m/%Y %H:%M"); break
            save_data(d); self.sj(200,{"ok":True}); return

        if p=="/api/order/cancel":
            oid=b.get("id")
            for od in d["orders"]:
                if od["id"]==oid and od["status"]=="pending":
                    od["status"]="cancelled"
                    for acc in d["accounts"]:
                        if acc["id"]==od["uid"]: acc["balance"]=acc.get("balance",0)+od["total"]
                    break
            save_data(d); self.sj(200,{"ok":True}); return

        if p=="/api/spin":
            uid=b.get("uid")
            acc=next((a for a in d["accounts"] if a["id"]==uid),None)
            if not acc: self.sj(404,{"ok":False,"error":"Khong tim thay user"}); return
            cost=d["settings"].get("spin_cost",5000)
            if acc.get("balance",0)<cost: self.sj(400,{"ok":False,"error":"So du khong du de quay"}); return
            acc["balance"]-=cost
            prizes=d["settings"].get("spin_prizes",[])
            if not prizes: self.sj(400,{"ok":False,"error":"Chua co phan thuong"}); return
            weights=[pz.get("weight",10) for pz in prizes]
            prize=random.choices(prizes,weights=weights,k=1)[0]
            pidx=prizes.index(prize)
            if prize["type"]=="balance": acc["balance"]=acc.get("balance",0)+prize["value"]
            sh={"id":"sp"+str(int(time.time()*1000)),"uid":uid,"uname":acc["name"],
                "prize_label":prize["label"],"prize_type":prize["type"],"prize_value":prize["value"],
                "time":datetime.now().strftime("%d/%m/%Y %H:%M")}
            if "spin_history" not in d: d["spin_history"]=[]
            d["spin_history"].append(sh); save_data(d)
            self.sj(200,{"ok":True,"prize":prize,"prize_index":pidx,"new_balance":acc["balance"]}); return

        if p=="/api/prices":
            np2={"id":"pr"+str(int(time.time()*1000)),"name":b.get("name",""),
                 "price":int(b.get("price",0)),"unit":b.get("unit","xu"),"note":b.get("note",""),"active":True}
            d["prices"].append(np2); save_data(d); self.sj(200,{"ok":True,"price":np2}); return

        if p=="/api/cf_packages":
            np2={"id":"cfp"+str(int(time.time()*1000)),"name":b.get("name",""),
                 "xu":int(b.get("xu",0)),"price":int(b.get("price",0)),"bonus":b.get("bonus",""),"active":True}
            d["cf_packages"].append(np2); save_data(d); self.sj(200,{"ok":True}); return

        if p=="/api/ranks":
            d["ranks"]=b.get("ranks",d["ranks"]); save_data(d); self.sj(200,{"ok":True}); return

        if p=="/api/settings":
            for k,v in b.items():
                d["settings"][k]=v
            save_data(d); self.sj(200,{"ok":True}); return

        if p=="/api/spin_prizes":
            d["settings"]["spin_prizes"]=b.get("prizes",d["settings"]["spin_prizes"])
            save_data(d); self.sj(200,{"ok":True}); return

        if p=="/api/balance/adjust":
            uid=b.get("uid"); amt=int(b.get("amount",0))
            for acc in d["accounts"]:
                if acc["id"]==uid:
                    acc["balance"]=max(0,acc.get("balance",0)+amt); save_data(d)
                    self.sj(200,{"ok":True,"new_balance":acc["balance"]}); return
            self.sj(404,{"ok":False}); return

        if p=="/api/set_rank":
            uid=b.get("uid"); rk=b.get("rank")
            for acc in d["accounts"]:
                if acc["id"]==uid: acc["rank"]=rk; save_data(d); self.sj(200,{"ok":True}); return
            self.sj(404,{"ok":False}); return

        if p=="/api/backup/now":
            do_backup(); self.sj(200,{"ok":True}); return

        if p=="/api/subwebs":
            uid=b.get("uid");name=b.get("name","");ann=b.get("announcement","");color=b.get("color","#00d4ff")
            if not uid: self.sj(400,{"ok":False,"error":"Thiếu uid"}); return
            # Remove existing if any
            d["subwebs"]=[w for w in d.get("subwebs",[]) if w["uid"]!=uid]
            sw={"id":"sw"+str(int(time.time()*1000)),"uid":uid,"name":name,"announcement":ann,"color":color}
            d.setdefault("subwebs",[]).append(sw); save_data(d)
            self.sj(200,{"ok":True,"web":sw}); return

        if p=="/api/posts":
            title=b.get("title","").strip(); body=b.get("body","").strip()
            ptype=b.get("type","news"); pin=bool(b.get("pin",False))
            if not title or not body: self.sj(400,{"ok":False,"error":"Thiếu tiêu đề hoặc nội dung"}); return
            post={"id":"pt"+str(int(time.time()*1000)),"title":title,"body":body,"type":ptype,"pin":pin,
                  "time":datetime.now().strftime("%d/%m/%Y %H:%M")}
            d.setdefault("posts",[]).append(post); save_data(d)
            self.sj(200,{"ok":True,"post":post}); return

        if p=="/api/svc_tabs":
            icon=b.get("icon","🛍"); name=b.get("name","").strip(); desc=b.get("desc",""); items=b.get("items",[])
            if not name: self.sj(400,{"ok":False,"error":"Thiếu tên tab"}); return
            tab={"id":"svc"+str(int(time.time()*1000)),"icon":icon,"name":name,"desc":desc,"items":items}
            d.setdefault("svc_tabs",[]).append(tab); save_data(d)
            self.sj(200,{"ok":True,"tab":tab}); return

        # ===== COUPON ENDPOINTS =====
        if p=="/api/coupon/check":
            code=b.get("code","").strip().upper()
            cp=next((c for c in d.get("coupons",[]) if c["code"]==code and c["active"]),None)
            if not cp: self.sj(404,{"ok":False,"error":"Mã không hợp lệ"}); return
            if cp.get("uses",0)>=cp.get("max_uses",9999): self.sj(400,{"ok":False,"error":"Mã đã hết lượt dùng"}); return
            self.sj(200,{"ok":True,"coupon":cp}); return

        if p=="/api/coupon/create":
            code=b.get("code","").strip().upper()
            disc=int(b.get("discount",10)); mx=int(b.get("max_uses",100)); note=b.get("note","")
            if not code: self.sj(400,{"ok":False,"error":"Thiếu mã"}); return
            if any(c["code"]==code for c in d.get("coupons",[])):
                self.sj(400,{"ok":False,"error":"Mã đã tồn tại"}); return
            cp={"id":"cp"+str(int(time.time()*1000)),"code":code,"discount":disc,
                "max_uses":mx,"uses":0,"note":note,"active":True,
                "created":datetime.now().strftime("%d/%m/%Y %H:%M")}
            d.setdefault("coupons",[]).append(cp); save_data(d)
            self.sj(200,{"ok":True,"coupon":cp}); return

        if p=="/api/coupon/toggle":
            cid=b.get("id")
            for cp in d.get("coupons",[]):
                if cp["id"]==cid: cp["active"]=not cp.get("active",True); break
            save_data(d); self.sj(200,{"ok":True}); return

        # ===== SUPPORT REQUEST =====
        if p=="/api/support/request":
            uid=b.get("uid",""); msg_text=b.get("message","").strip()
            if not msg_text: self.sj(400,{"ok":False,"error":"Nhập nội dung yêu cầu"}); return
            acc_s=next((a for a in d["accounts"] if a["id"]==uid),None)
            uname_s=acc_s["name"] if acc_s else "Khách"
            sr={"id":"sr"+str(int(time.time()*1000)),"uid":uid,"uname":uname_s,
                "message":msg_text,"status":"open","time":datetime.now().strftime("%d/%m/%Y %H:%M")}
            d.setdefault("support_requests",[]).append(sr); save_data(d)
            if d["settings"].get("telegram_notify_support",True):
                tg_send(f"🆘 <b>YÊU CẦU HỖ TRỢ</b>\n"
                        f"👤 {uname_s} ({uid})\n"
                        f"💬 {msg_text}\n"
                        f"🕐 {sr['time']}")
            self.sj(200,{"ok":True,"sr":sr}); return

        self.sj(404,{"error":"not found"})

    def do_PUT(self):
        p=urlparse(self.path).path; b=self.rb(); d=load_data()
        if p.startswith("/api/prices/"):
            pid=p.split("/")[-1]
            for pr in d["prices"]:
                if pr["id"]==pid: pr.update({k:b[k] for k in b if k in pr})
            save_data(d); self.sj(200,{"ok":True}); return
        if p.startswith("/api/cf_packages/"):
            pid=p.split("/")[-1]
            for pr in d.get("cf_packages",[]):
                if pr["id"]==pid: pr.update({k:b[k] for k in b if k in pr})
            save_data(d); self.sj(200,{"ok":True}); return
        self.sj(404,{"error":"not found"})

    def do_DELETE(self):
        p=urlparse(self.path).path; d=load_data()
        if p.startswith("/api/prices/"):
            pid=p.split("/")[-1]; d["prices"]=[pr for pr in d["prices"] if pr["id"]!=pid]
            save_data(d); self.sj(200,{"ok":True}); return
        if p.startswith("/api/cf_packages/"):
            pid=p.split("/")[-1]; d["cf_packages"]=[pr for pr in d.get("cf_packages",[]) if pr["id"]!=pid]
            save_data(d); self.sj(200,{"ok":True}); return
        if p.startswith("/api/accounts/"):
            uid=p.split("/")[-1]
            if uid=="admin": self.sj(400,{"ok":False,"error":"Khong xoa duoc admin"}); return
            d["accounts"]=[a for a in d["accounts"] if a["id"]!=uid]; save_data(d)
            self.sj(200,{"ok":True}); return
        if p.startswith("/api/subwebs/"):
            wid=p.split("/")[-1]; d["subwebs"]=[w for w in d.get("subwebs",[]) if w["id"]!=wid]
            save_data(d); self.sj(200,{"ok":True}); return
        if p.startswith("/api/posts/"):
            pid=p.split("/")[-1]; d["posts"]=[pt for pt in d.get("posts",[]) if pt["id"]!=pid]
            save_data(d); self.sj(200,{"ok":True}); return
        if p.startswith("/api/svc_tabs/"):
            tid=p.split("/")[-1]; d["svc_tabs"]=[t for t in d.get("svc_tabs",[]) if t["id"]!=tid]
            save_data(d); self.sj(200,{"ok":True}); return
        if p.startswith("/api/coupon/"):
            cid=p.split("/")[-1]; d["coupons"]=[c for c in d.get("coupons",[]) if c["id"]!=cid]
            save_data(d); self.sj(200,{"ok":True}); return
        self.sj(404,{"error":"not found"})

if __name__=="__main__":
    import socket
    try: local_ip=socket.gethostbyname(socket.gethostname())
    except: local_ip="127.0.0.1"

    print("="*55)
    print("  SHOP XU CFL - SERVER v3.0")
    print("="*55)

    if DB_URL:
        print("  [DB] Connecting to PostgreSQL...")
        db_init()
    else:
        print("  [DB] No DATABASE_URL — using local file")
        print("  [DB] Set DATABASE_URL env var for persistent storage")

    threading.Thread(target=backup_loop,daemon=True).start()
    server=HTTPServer(("0.0.0.0",PORT),H)
    print("  Local  : http://localhost:{}".format(PORT))
    print("  Network: http://{}:{}".format(local_ip,PORT))
    print("  Admin: username=admin  password=admin123")
    print("="*55)
    if TELEGRAM_BOT_TOKEN:
        print("  [TG] Telegram Bot: ENABLED (chat_id={})".format(TELEGRAM_CHAT_ID))
    else:
        print("  [TG] Telegram Bot: Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID to enable")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nStopped.")


# ==================== PATCH: NEW ENDPOINTS ====================
# These are injected by patch script - subwebs, posts, svc_tabs
