import os,sqlite3,secrets
from datetime import datetime,timedelta
from functools import wraps
from urllib.parse import quote
from flask import Flask,render_template,request,redirect,url_for,session,flash,send_from_directory,abort
from werkzeug.utils import secure_filename
BASE=os.path.abspath(os.path.dirname(__file__))
DB=os.environ.get("DATABASE_PATH",os.path.join(BASE,"instance","tienda.db"))
UPLOAD=os.environ.get("UPLOAD_FOLDER",os.path.join(BASE,"static","uploads"))
os.makedirs(os.path.dirname(DB),exist_ok=True);os.makedirs(UPLOAD,exist_ok=True)
app=Flask(__name__);app.secret_key=os.environ.get("SECRET_KEY") or secrets.token_hex(32);app.config["MAX_CONTENT_LENGTH"]=5*1024*1024
WA="5493875556515"
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def now():return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def init():
 with db() as c:
  c.executescript("""CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,name TEXT NOT NULL,price INTEGER NOT NULL,description TEXT DEFAULT '',image TEXT DEFAULT '',active INTEGER DEFAULT 1,created_by TEXT,updated_at TEXT);
  CREATE TABLE IF NOT EXISTS news(id INTEGER PRIMARY KEY,title TEXT NOT NULL,body TEXT NOT NULL,image TEXT DEFAULT '',status TEXT DEFAULT 'borrador',created_at TEXT,created_by TEXT);
  CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY,product_id INTEGER,author TEXT NOT NULL,rating INTEGER NOT NULL,comment TEXT NOT NULL,created_at TEXT,approved INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
  CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,username TEXT,action TEXT,detail TEXT,created_at TEXT);""")
  items=[("Organizador",8000,"Organizador impreso en 3D"),("Dragón",5000,"Figura de dragón"),("Dragón con lámpara",15000,"Dragón con lámpara"),("Lagartija",3000,"Figura de lagartija"),("Organizador 2",15000,"Organizador"),("Letras personalizadas",7000,"Letras a pedido")]
  if not c.execute("SELECT COUNT(*) FROM products").fetchone()[0]:c.executemany("INSERT INTO products(name,price,description,created_by,updated_at) VALUES(?,?,?,?,?)",[(n,p,d,"Sistema",now()) for n,p,d in items])
  for k,v in [("trial_start",""),("trial_hours","24"),("preorder_open","0"),("preorder_until",""),("preorder_delivery","")]:c.execute("INSERT OR IGNORE INTO settings VALUES(?,?)",(k,v))
def getset(k):
 with db() as c:
  r=c.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone();return r["value"] if r else ""
def setset(k,v):
 with db() as c:c.execute("INSERT OR REPLACE INTO settings VALUES(?,?)",(k,v))
def log(a,d=""):
 with db() as c:c.execute("INSERT INTO audit(username,action,detail,created_at) VALUES(?,?,?,?)",(session.get("user","Sistema"),a,d,now()))
def users():return {"Aria":os.environ.get("ADMIN_ARIA_PASSWORD",""),"Pedro":os.environ.get("ADMIN_PEDRO_PASSWORD","")}
def required(fn):
 @wraps(fn)
 def w(*a,**k):
  if session.get("user") not in ("Aria","Pedro"):return redirect(url_for("login"))
  return fn(*a,**k)
 return w
def creator(fn):
 @wraps(fn)
 def w(*a,**k):
  if session.get("user")!="Aria":abort(403)
  return fn(*a,**k)
 return w
def wa(t):return "https://wa.me/"+WA+"?text="+quote(t)
@app.template_filter("money")
def money(v):return "{:,}".format(int(v)).replace(",",".")
def save_image(f):
 if not f or not f.filename:return ""
 if f.mimetype not in ("image/jpeg","image/png","image/webp"):raise ValueError("Usá una imagen JPG, PNG o WebP.")
 name=secrets.token_hex(8)+"_"+secure_filename(f.filename);f.save(os.path.join(UPLOAD,name));return name
@app.route("/media/<path:filename>")
def media(filename):return send_from_directory(UPLOAD,filename)
@app.route("/")
def home():
 with db() as c:
  ps=[dict(x,symbol=["✳","🐉","💡","🦎","▤","Aa"][(x["id"]-1)%6]) for x in c.execute("SELECT * FROM products WHERE active=1 ORDER BY id").fetchall()]
  ns=c.execute("SELECT * FROM news WHERE status='publicada' ORDER BY id DESC").fetchall()
  rs=c.execute("SELECT reviews.*,products.name product_name FROM reviews LEFT JOIN products ON products.id=reviews.product_id WHERE approved=1 ORDER BY reviews.id DESC LIMIT 12").fetchall()
 trial=False
 if getset("trial_start"):
  try:trial=datetime.now()<datetime.strptime(getset("trial_start"),"%Y-%m-%d %H:%M:%S")+timedelta(hours=int(getset("trial_hours") or 24))
  except ValueError:pass
 pre=getset("preorder_open")=="1";until=getset("preorder_until")
 if pre and until:
  try:pre=datetime.now()<datetime.strptime(until,"%Y-%m-%dT%H:%M")
  except ValueError:pre=False
 return render_template("index.html",products=ps,news=ns,reviews=rs,wa=wa,trial_active=trial,preorder=pre,delivery=getset("preorder_delivery"))
@app.route("/review",methods=["POST"])
def review():
 name=request.form.get("author","").strip()[:60];comment=request.form.get("comment","").strip()[:1000]
 try:rating=max(1,min(5,int(request.form.get("rating","5"))))
 except ValueError:rating=5
 if name and comment:
  with db() as c:c.execute("INSERT INTO reviews(product_id,author,rating,comment,created_at) VALUES(?,?,?,?,?)",(request.form.get("product_id") or None,name,rating,comment,now()))
  flash("¡Gracias! Tu reseña quedó pendiente de aprobación.")
 else:flash("Completá tu nombre y comentario.")
 return redirect(url_for("home")+"#opiniones")
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  u=request.form.get("username","");p=request.form.get("password","");valid=users().get(u)
  if valid and p and secrets.compare_digest(valid,p):
   session.clear();session["user"]=u;log("Inicio de sesión");return redirect(url_for("admin"))
  flash("Usuario o contraseña incorrectos. Revisá las variables de entorno en Render.")
 return render_template("login.html")
@app.route("/logout")
def logout():session.clear();return redirect(url_for("home"))
@app.route("/admin")
@required
def admin():
 with db() as c:
  ps=c.execute("SELECT * FROM products ORDER BY id").fetchall();ns=c.execute("SELECT * FROM news ORDER BY id DESC").fetchall()
  rs=c.execute("SELECT reviews.*,products.name product_name FROM reviews LEFT JOIN products ON products.id=reviews.product_id ORDER BY reviews.id DESC").fetchall()
  logs=c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 20").fetchall()
 return render_template("admin.html",products=ps,news=ns,reviews=rs,logs=logs,user=session["user"],trial_start=getset("trial_start"),preorder_open=getset("preorder_open"),preorder_until=getset("preorder_until"),preorder_delivery=getset("preorder_delivery"))
@app.route("/admin/product",methods=["POST"])
@creator
def product_save():
 pid=request.form.get("id");name=request.form.get("name","").strip()
 try:price=int(request.form.get("price") or 0)
 except ValueError:price=-1
 if not name or price<0:flash("Completá nombre y precio válido.");return redirect(url_for("admin"))
 try:img=save_image(request.files.get("image"))
 except ValueError as e:flash(str(e));return redirect(url_for("admin"))
 with db() as c:
  if pid:
   old=c.execute("SELECT image FROM products WHERE id=?",(pid,)).fetchone();img=img or (old["image"] if old else "")
   c.execute("UPDATE products SET name=?,price=?,description=?,image=?,active=?,updated_at=?,created_by=? WHERE id=?",(name,price,request.form.get("description",""),img,1 if request.form.get("active") else 0,now(),session["user"],pid));log("Edición de producto",name)
  else:c.execute("INSERT INTO products(name,price,description,image,created_by,updated_at) VALUES(?,?,?,?,?,?)",(name,price,request.form.get("description",""),img,session["user"],now()));log("Creación de producto",name)
 flash("Producto guardado.");return redirect(url_for("admin")+"#productos")
@app.route("/admin/product/delete/<int:pid>",methods=["POST"])
@creator
def product_delete(pid):
 with db() as c:c.execute("UPDATE products SET active=0,updated_at=? WHERE id=?",(now(),pid))
 log("Producto ocultado",str(pid));return redirect(url_for("admin")+"#productos")
@app.route("/admin/news",methods=["POST"])
@required
def news_save():
 title=request.form.get("title","").strip();body=request.form.get("body","").strip();status=request.form.get("status","borrador")
 if not title or not body:flash("Completá título y contenido.");return redirect(url_for("admin"))
 try:img=save_image(request.files.get("image"))
 except ValueError as e:flash(str(e));return redirect(url_for("admin"))
 if status not in ("borrador","publicada"):status="borrador"
 with db() as c:c.execute("INSERT INTO news(title,body,image,status,created_at,created_by) VALUES(?,?,?,?,?,?)",(title,body,img,status,now(),session["user"]))
 log("Noticia guardada",title);flash("Noticia guardada.");return redirect(url_for("admin")+"#noticias")
@app.route("/admin/news/status/<int:nid>",methods=["POST"])
@required
def news_status(nid):
 st=request.form.get("status","borrador")
 if st not in ("borrador","publicada"):abort(400)
 with db() as c:c.execute("UPDATE news SET status=? WHERE id=?",(st,nid))
 log("Estado de noticia",str(nid)+" "+st);return redirect(url_for("admin")+"#noticias")
@app.route("/admin/review/<int:rid>",methods=["POST"])
@required
def review_approve(rid):
 with db() as c:c.execute("UPDATE reviews SET approved=? WHERE id=?",(1 if request.form.get("approved")=="1" else 0,rid))
 log("Moderación de reseña",str(rid));return redirect(url_for("admin")+"#resenas")
@app.route("/admin/settings",methods=["POST"])
@required
def settings_save():
 action=request.form.get("action")
 if action=="trial":
  setset("trial_start",now());setset("trial_hours","24");log("Campaña de prueba","24 horas");flash("Campaña informativa activada por 24 horas. No se cobra nada.")
 elif action=="preorder":
  setset("preorder_open","1" if request.form.get("preorder_open") else "0");setset("preorder_until",request.form.get("preorder_until",""));setset("preorder_delivery",request.form.get("preorder_delivery","")[:120]);log("Compra anticipada configurada");flash("Compra anticipada configurada. Los pedidos se coordinan por WhatsApp.")
 return redirect(url_for("admin")+"#configuracion")
@app.errorhandler(403)
def forbidden(e):return "No tenés permisos para realizar esta acción.",403
init()
if __name__=="__main__":app.run(debug=False)
