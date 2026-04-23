#!/usr/bin/env python3
import json, os, hashlib, shutil, threading, time, random
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

DATA_FILE = "data.json"
PORT = int(os.environ.get("PORT", 8080))
BACKUP_DIR = "backup"
MAX_BACKUPS = 30
BACKUP_INTERVAL = 24 * 60 * 60

DEFAULT_DATA = {
    "settings": {
        "shop_name": "Shop Xu Su Kien CFL",
        "zalo": "0964149813",
        "fb_page": "https://www.facebook.com/NguyenChiCuong.AC9",
        "bank_name": "MB Bank",
        "bank_number": "09090669999",
        "bank_owner": "NGUYEN TRAN CHI CUONG",
        "momo": "",
        "announcement": "Chao mung den voi Shop Xu Su Kien CFL!",
        "spin_cost": 5000,
        "spin_prizes": [
            {"label":"10,000d","value":10000,"type":"balance","weight":20},
            {"label":"5 Xu","value":5,"type":"xu","weight":25},
            {"label":"10 Xu","value":10,"type":"xu","weight":20},
            {"label":"50,000d","value":50000,"type":"balance","weight":5},
            {"label":"1 Xu","value":1,"type":"xu","weight":30},
            {"label":"100,000d","value":100000,"type":"balance","weight":2},
            {"label":"20 Xu","value":20,"type":"xu","weight":10},
            {"label":"Thu lai","value":0,"type":"none","weight":15}
        ]
    },
    "ranks": [
        {"id":"bronze","name":"Dong","min_spent":0,"color":"#cd7f32","discount":0,"icon":"bronze"},
        {"id":"silver","name":"Bac","min_spent":500000,"color":"#c0c0c0","discount":3,"icon":"silver"},
        {"id":"gold","name":"Vang","min_spent":2000000,"color":"#f5a623","discount":5,"icon":"gold"},
        {"id":"diamond","name":"Kim Cuong","min_spent":5000000,"color":"#00d4ff","discount":10,"icon":"diamond"}
    ],
    "accounts": [
        {"id":"admin","username":"admin","name":"Nguyen Chi Cuong",
         "pin_hash": hashlib.sha256("admin123".encode()).hexdigest(),
         "role":"admin","balance":0,"total_spent":0,"rank":"diamond","spin_tickets":0,
         "created": datetime.now().strftime("%d/%m/%Y")}
    ],
    "prices": [
        {"id":"xu_sk","name":"Xu Su Kien","price":30000,"unit":"xu","note":"Lien he Zalo","active":True},
        {"id":"xu_th","name":"Xu Thuong","price":4000,"unit":"xu","note":"Giao nhanh","active":True}
    ],
    "cf_packages": [
        {"id":"cf1","name":"5,000 ZPoint","xu":5000,"price":50000,"bonus":"","active":True},
        {"id":"cf2","name":"10,000 ZPoint","xu":10000,"price":95000,"bonus":"Bonus 5%","active":True},
        {"id":"cf3","name":"25,000 ZPoint","xu":25000,"price":230000,"bonus":"Bonus 8%","active":True},
        {"id":"cf4","name":"50,000 ZPoint","xu":50000,"price":450000,"bonus":"Bonus 10%","active":True}
    ],
    "topups": [],
    "orders": [],
    "spin_history": []
}

AVATAR_COLORS = [
    {"color":"#f59e0b","bg":"#1a1400"},{"color":"#10b981","bg":"#001a0e"},
    {"color":"#3b82f6","bg":"#00091a"},{"color":"#f43f5e","bg":"#1a0008"},
    {"color":"#a855f7","bg":"#0e001a"},{"color":"#06b6d4","bg":"#001519"}
]

def load_data():
    if not os.path.exists(DATA_FILE):
        d = json.loads(json.dumps(DEFAULT_DATA))
        save_data(d); return d
    with open(DATA_FILE,"r",encoding="utf-8") as f: d=json.load(f)
    for k,v in DEFAULT_DATA.items():
        if k not in d: d[k]=v
    for k,v in DEFAULT_DATA["settings"].items():
        if k not in d["settings"]: d["settings"][k]=v
    return d

def save_data(data):
    with open(DATA_FILE,"w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
def safe_acc(a): return {k:v for k,v in a.items() if k!="pin_hash"}

def get_rank(ranks, total_spent):
    sranks = sorted(ranks, key=lambda r: r["min_spent"], reverse=True)
    for r in sranks:
        if total_spent >= r["min_spent"]: return r["id"]
    return "bronze"

def do_backup():
    if not os.path.exists(DATA_FILE): return
    os.makedirs(BACKUP_DIR,exist_ok=True)
    dest=os.path.join(BACKUP_DIR,"data_{}.json".format(datetime.now().strftime("%Y-%m-%d_%H-%M")))
    shutil.copy2(DATA_FILE,dest)
    files=sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".json")])
    while len(files)>MAX_BACKUPS: os.remove(os.path.join(BACKUP_DIR,files.pop(0)))

def backup_loop():
    time.sleep(5); do_backup()
    while True: time.sleep(BACKUP_INTERVAL); do_backup()

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
        p=urlparse(self.path).path
        if p in ("/","/index.html"):
            if os.path.exists("index.html"): self.sf("index.html","text/html; charset=utf-8")
            else: self.sj(404,{"error":"index.html not found"})
            return
        d=load_data()
        routes={
            "/api/settings":     lambda:d["settings"],
            "/api/prices":       lambda:d["prices"],
            "/api/topups":       lambda:d["topups"],
            "/api/orders":       lambda:d["orders"],
            "/api/ranks":        lambda:d["ranks"],
            "/api/cf_packages":  lambda:d.get("cf_packages",[]),
            "/api/spin_history": lambda:d.get("spin_history",[]),
            "/api/accounts/all": lambda:[safe_acc(a) for a in d["accounts"]]
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
                "rank":"bronze","spin_tickets":3,"color":st["color"],"bg":st["bg"],
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
            req={"id":"tp"+str(int(time.time()*1000)),"uid":uid,"amount":amt,"method":method,
                 "note":note,"status":"pending","time":datetime.now().strftime("%d/%m/%Y %H:%M")}
            d["topups"].append(req); save_data(d); self.sj(200,{"ok":True,"topup":req}); return

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
            acc=next((a for a in d["accounts"] if a["id"]==uid),None)
            price=next((pr for pr in d["prices"] if pr["id"]==pid),None)
            if not acc or not price: self.sj(400,{"ok":False,"error":"Du lieu khong hop le"}); return
            rk=next((r for r in d["ranks"] if r["id"]==acc.get("rank","bronze")),None)
            disc=rk["discount"] if rk else 0
            total=int(price["price"]*qty*(1-disc/100))
            if acc.get("balance",0)<total: self.sj(400,{"ok":False,"error":"So du khong du"}); return
            acc["balance"]-=total; acc["total_spent"]=acc.get("total_spent",0)+total
            acc["rank"]=get_rank(d["ranks"],acc["total_spent"])
            od={"id":"od"+str(int(time.time()*1000)),"uid":uid,"uname":acc["name"],
                "price_id":pid,"price_name":price["name"],"qty":qty,"total":total,
                "discount":disc,"game_id":gid,"status":"pending","time":datetime.now().strftime("%d/%m/%Y %H:%M")}
            d["orders"].append(od); save_data(d)
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
            uid=b.get("uid"); d=load_data()
            acc=next((a for a in d["accounts"] if a["id"]==uid),None)
            if not acc: self.sj(404,{"ok":False,"error":"Khong tim thay user"}); return
            cost=d["settings"].get("spin_cost",5000)
            if acc.get("balance",0)<cost: self.sj(400,{"ok":False,"error":"So du khong du de quay"}); return
            acc["balance"]-=cost
            prizes=d["settings"].get("spin_prizes",[])
            weights=[pz["weight"] for pz in prizes]
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
                if k in d["settings"]: d["settings"][k]=v
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

        self.sj(404,{"error":"not found"})

    def do_PUT(self):
        p=urlparse(self.path).path; b=self.rb(); d=load_data()
        if p.startswith("/api/prices/"):
            pid=p.split("/")[-1]
            for pr in d["prices"]:
                if pr["id"]==pid: pr.update({k:b[k] for k in ["name","price","unit","note","active"] if k in b})
            save_data(d); self.sj(200,{"ok":True}); return
        if p.startswith("/api/cf_packages/"):
            pid=p.split("/")[-1]
            for pr in d.get("cf_packages",[]):
                if pr["id"]==pid: pr.update({k:b[k] for k in ["name","xu","price","bonus","active"] if k in b})
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
        self.sj(404,{"error":"not found"})

if __name__=="__main__":
    import socket
    try: local_ip=socket.gethostbyname(socket.gethostname())
    except: local_ip="127.0.0.1"
    threading.Thread(target=backup_loop,daemon=True).start()
    server=HTTPServer(("0.0.0.0",PORT),H)
    print("="*50)
    print("  SHOP XU CFL - SERVER v2.0")
    print("  Local  : http://localhost:{}".format(PORT))
    print("  Network: http://{}:{}".format(local_ip,PORT))
    print("  Admin: username=admin  password=admin123")
    print("="*50)
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nDừng chạy.")
