import os, sqlite3, secrets
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import quote
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename

BASE = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(BASE, 'instance', 'tienda.db'))
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE, 'static', 'uploads'))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
WHATSAPP = '5493875556515'


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT NOT NULL, price INTEGER NOT NULL, description TEXT DEFAULT '', image TEXT DEFAULT '', active INTEGER DEFAULT 1, created_by TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS news(id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL, image TEXT DEFAULT '', status TEXT DEFAULT 'borrador', created_at TEXT, created_by TEXT);
        CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, product_id INTEGER, author TEXT NOT NULL, rating INTEGER NOT NULL, comment TEXT NOT NULL, created_at TEXT, approved INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, username TEXT, action TEXT, detail TEXT, created_at TEXT);
        ''')
        if c.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
            defaults=[('Organizador',8000,'Organizador impreso en 3D',''),('Dragón',5000,'Figura de dragón',''),('Dragón con lámpara',15000,'Dragón con lámpara',''),('Lagartija',3000,'Figura de lagartija',''),('Organizador 2',15000,'Organizador',''),('Letras personalizadas',7000,'Letras a pedido','')]
            c.executemany('INSERT INTO products(name,price,description,created_by,updated_at) VALUES(?,?,?,?,?)',[(n,p,d,'Sistema',now()) for n,p,d,_ in defaults])
        for k,v in [('trial_start',''),('trial_hours','24'),('preorder_open','0'),('preorder_until',''),('preorder_delivery','')]:
            c.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))

def now(): return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
def setting(key):
    with db() as c:
        r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return r['value'] if r else ''
def set_setting(key,value):
    with db() as c: c.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(key,value))
def log(action,detail=''):
    with db() as c: c.execute('INSERT INTO audit(username,action,detail,created_at) VALUES(?,?,?,?)',(session.get('user','Sistema'),action,detail,now()))
def admins():
    # Configurar ADMIN_ARIA_PASSWORD y ADMIN_PEDRO_PASSWORD en Render.
    return {'Aria':os.environ.get('ADMIN_ARIA_PASSWORD',''), 'Pedro':os.environ.get('ADMIN_PEDRO_PASSWORD','')}
def admin_required(fn):
    @wraps(fn)
    def wrapper(*a,**kw):
        if not session.get('user'): return redirect(url_for('login'))
        return fn(*a,**kw)
    return wrapper

def wa(text): return 'https://wa.me/'+WHATSAPP+'?text='+quote(text)

@app.route('/media/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/')
def home():
    with db() as c:
        products=c.execute('SELECT * FROM products WHERE active=1 ORDER BY id').fetchall()
        news=c.execute("SELECT * FROM news WHERE status='publicada' ORDER BY id DESC").fetchall()
        reviews=c.execute('SELECT reviews.*,products.name AS product_name FROM reviews LEFT JOIN products ON products.id=reviews.product_id WHERE approved=1 ORDER BY reviews.id DESC LIMIT 12').fetchall()
    start=setting('trial_start'); hours=int(setting('trial_hours') or 24); trial_active=False
    if start:
        try: trial_active=datetime.now() < datetime.strptime(start,'%Y-%m-%d %H:%M:%S')+timedelta(hours=hours)
        except ValueError: pass
    preorder=setting('preorder_open')=='1'
    if setting('preorder_until'):
        try: preorder=preorder and datetime.now() < datetime.strptime(setting('preorder_until'),'%Y-%m-%dT%H:%M')
        except ValueError: pass
    return render_template('index.html',products=products,news=news,reviews=reviews,whatsapp=WHATSAPP,wa=wa,trial_active=trial_active,preorder=preorder,delivery=setting('preorder_delivery'))

@app.route('/review',methods=['POST'])
def review():
    try: rating=max(1,min(5,int(request.form.get('rating','5'))))
    except ValueError: rating=5
    with db() as c: c.execute('INSERT INTO reviews(product_id,author,rating,comment,created_at) VALUES(?,?,?,?,?)',(request.form.get('product_id') or None,request.form.get('author','').strip()[:60],rating,request.form.get('comment','').strip()[:1000],now()))
    flash('¡Gracias! Tu reseña quedó pendiente de aprobación.')
    return redirect(url_for('home')+'#opiniones')

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        username=request.form.get('username','')
        password=request.form.get('password','')
        valid=admins().get(username)
        if valid and password and secrets.compare_digest(valid,password):
            session['user']=username; log('Inicio de sesión'); return redirect(url_for('admin'))
        flash('Usuario o contraseña incorrectos. Revisá la configuración de Render.')
    return render_template('login.html')
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('home'))

@app.route('/admin')
@admin_required
def admin():
    with db() as c:
        products=c.execute('SELECT * FROM products ORDER BY id').fetchall()
        news=c.execute('SELECT * FROM news ORDER BY id DESC').fetchall()
        reviews=c.execute('SELECT reviews.*,products.name AS product_name FROM reviews LEFT JOIN products ON products.id=reviews.product_id ORDER BY reviews.id DESC').fetchall()
        logs=c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 12').fetchall()
    return render_template('admin.html',products=products,news=news,reviews=reviews,logs=logs,trial_start=setting('trial_start'),preorder_open=setting('preorder_open'),preorder_until=setting('preorder_until'),preorder_delivery=setting('preorder_delivery'))

def save_image(file):
    if not file or not file.filename: return ''
    if file.mimetype not in ('image/jpeg','image/png','image/webp'): raise ValueError('Usá una imagen JPG, PNG o WebP.')
    name=secrets.token_hex(8)+'_'+secure_filename(file.filename)
    file.save(os.path.join(UPLOAD_FOLDER,name))
    return name

@app.route('/admin/product',methods=['POST'])
@admin_required
def product_save():
    pid=request.form.get('id'); name=request.form.get('name','').strip(); price=int(request.form.get('price') or 0)
    if not name or price<0: flash('Completá nombre y precio válido.'); return redirect(url_for('admin'))
    try: image=save_image(request.files.get('image'))
    except ValueError as e: flash(str(e)); return redirect(url_for('admin'))
    with db() as c:
        if pid:
            old=c.execute('SELECT image FROM products WHERE id=?',(pid,)).fetchone(); image=image or (old['image'] if old else '')
            c.execute('UPDATE products SET name=?,price=?,description=?,image=?,active=?,updated_at=?,created_by=? WHERE id=?',(name,price,request.form.get('description',''),image,1 if request.form.get('active') else 0,now(),session['user'],pid))
            log('Edición de producto',name)
        else:
            c.execute('INSERT INTO products(name,price,description,image,created_by,updated_at) VALUES(?,?,?,?,?,?)',(name,price,request.form.get('description',''),image,session['user'],now())); log('Creación de producto',name)
    flash('Producto guardado.'); return redirect(url_for('admin'))
@app.route('/admin/product/delete/<int:pid>',methods=['POST'])
@admin_required
def product_delete(pid):
    with db() as c: c.execute('UPDATE products SET active=0,updated_at=? WHERE id=?',(now(),pid))
    log('Desactivación de producto',str(pid)); flash('Producto ocultado del catálogo.'); return redirect(url_for('admin'))

@app.route('/admin/news',methods=['POST'])
@admin_required
def news_save():
    title=request.form.get('title','').strip(); body=request.form.get('body','').strip(); status=request.form.get('status','borrador')
    if not title or not body: flash('Completá título y contenido.'); return redirect(url_for('admin'))
    try: image=save_image(request.files.get('image'))
    except ValueError as e: flash(str(e)); return redirect(url_for('admin'))
    with db() as c: c.execute('INSERT INTO news(title,body,image,status,created_at,created_by) VALUES(?,?,?,?,?,?)',(title,body,image,status,now(),session['user']))
    log('Publicación de noticia',title); flash('Noticia guardada.'); return redirect(url_for('admin'))
@app.route('/admin/news/status/<int:nid>',methods=['POST'])
@admin_required
def news_status(nid):
    status=request.form.get('status','borrador')
    with db() as c: c.execute('UPDATE news SET status=? WHERE id=?',(status,nid))
    log('Cambio de noticia',str(nid)+' '+status); return redirect(url_for('admin'))
@app.route('/admin/review/<int:rid>',methods=['POST'])
@admin_required
def review_approve(rid):
    with db() as c: c.execute('UPDATE reviews SET approved=? WHERE id=?',(1 if request.form.get('approved')=='1' else 0,rid))
    log('Moderación de reseña',str(rid)); return redirect(url_for('admin'))
@app.route('/admin/settings',methods=['POST'])
@admin_required
def settings_save():
    action=request.form.get('action')
    if action=='trial': set_setting('trial_start',now()); set_setting('trial_hours','24'); log('Inicio de compra de prueba','24 horas desde ahora'); flash('Compra de prueba activada por 24 horas. Es una simulación: los pedidos se consultan por WhatsApp, no se cobra en la web.')
    elif action=='preorder':
        set_setting('preorder_open','1' if request.form.get('preorder_open') else '0'); set_setting('preorder_until',request.form.get('preorder_until','')); set_setting('preorder_delivery',request.form.get('preorder_delivery','')); log('Configuración de compra anticipada'); flash('Configuración de compra anticipada guardada.')
    return redirect(url_for('admin'))

init_db()
if __name__=='__main__': app.run(debug=False)
