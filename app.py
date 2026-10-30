from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from pathlib import Path
import sqlite3
from datetime import datetime, date
import os, re, uuid
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('LOLLIX_DB_PATH', BASE_DIR / 'data' / 'lollix.db'))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = BASE_DIR / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR = BASE_DIR / 'exports'
PDF_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_ASSET_EXTENSIONS = {'png','jpg','jpeg','webp','gif','svg','pdf','doc','docx','xls','xlsx','ppt','pptx'}
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # Limite de upload: 20 MB

SCHEMAS = {
    'orders': {
        'table': 'orders',
        'fields': ['code', 'customer', 'channel', 'status', 'amount', 'order_date', 'notes'],
        'required': ['code', 'customer'],
        'defaults': {'channel': 'Site', 'status': 'Novo', 'amount': 0, 'order_date': lambda: date.today().isoformat(), 'notes': ''}
    },
    'campaigns': {
        'table': 'campaigns',
        'fields': ['name', 'channel', 'status', 'start_date', 'end_date', 'budget', 'goal', 'notes'],
        'required': ['name'],
        'defaults': {'channel': 'Site', 'status': 'Planejada', 'start_date': '', 'end_date': '', 'budget': 0, 'goal': '', 'notes': ''}
    },
    'tasks': {
        'table': 'tasks',
        'fields': ['title', 'area', 'responsible', 'priority', 'status', 'due_date', 'notes'],
        'required': ['title'],
        'defaults': {'area': 'E-commerce', 'responsible': '', 'priority': 'Média', 'status': 'Pendente', 'due_date': '', 'notes': ''}
    },
    'returns': {
        'table': 'returns',
        'fields': ['protocol', 'customer', 'type', 'status', 'request_date', 'order_code', 'reason', 'notes'],
        'required': ['customer'],
        'defaults': {'protocol': '', 'type': 'Troca', 'status': 'Recebida', 'request_date': lambda: date.today().isoformat(), 'order_code': '', 'reason': '', 'notes': ''}
    },
    'metrics': {
        'table': 'metrics',
        'fields': ['month', 'sales', 'orders_count', 'chargebacks', 'returns_count', 'reverse_logistics', 'target'],
        'required': ['month'],
        'defaults': {'sales': 0, 'orders_count': 0, 'chargebacks': 0, 'returns_count': 0, 'reverse_logistics': 0, 'target': 0}
    }
}


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL, customer TEXT NOT NULL,
            channel TEXT, status TEXT, amount REAL DEFAULT 0, order_date TEXT, notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, channel TEXT, status TEXT,
            start_date TEXT, end_date TEXT, budget REAL DEFAULT 0, goal TEXT, notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, area TEXT, responsible TEXT,
            priority TEXT, status TEXT, due_date TEXT, notes TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT, protocol TEXT, customer TEXT NOT NULL, type TEXT,
            status TEXT, request_date TEXT, order_code TEXT, reason TEXT, notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT, month TEXT NOT NULL UNIQUE, sales REAL DEFAULT 0,
            orders_count INTEGER DEFAULT 0, chargebacks REAL DEFAULT 0, returns_count INTEGER DEFAULT 0,
            reverse_logistics REAL DEFAULT 0, target REAL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS identity_settings (
            id INTEGER PRIMARY KEY CHECK (id=1), primary_color TEXT NOT NULL DEFAULT '#5a2b91',
            secondary_color TEXT NOT NULL DEFAULT '#35145e', accent_color TEXT NOT NULL DEFAULT '#d6b5fa',
            logo_filename TEXT DEFAULT '', font_family TEXT NOT NULL DEFAULT 'Manrope', updated_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, original_name TEXT NOT NULL, stored_name TEXT NOT NULL,
            file_type TEXT, file_size INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('''CREATE TABLE IF NOT EXISTS pdf_exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, category TEXT DEFAULT 'Planejamento',
            stored_name TEXT NOT NULL, file_size INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('INSERT OR IGNORE INTO identity_settings (id) VALUES (1)')
        count = db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
        if count == 0:
            db.execute("INSERT INTO tasks (title,area,responsible,priority,status,due_date,notes) VALUES (?,?,?,?,?,?,?)",
                       ('Revisar calendário de campanhas de novembro', 'Marketing', 'Kauê', 'Alta', 'Pendente', '', 'Planejamento inicial da operação digital.'))
            db.execute("INSERT INTO tasks (title,area,responsible,priority,status,due_date,notes) VALUES (?,?,?,?,?,?,?)",
                       ('Alinhar entregas e materiais com a agência', 'Agência', 'Kauê', 'Média', 'Em andamento', '', 'Acompanhar peças, fotos e integrações.'))


@app.route('/')
def index():
    return render_template('index.html', initial_page='dashboard')

HUB_PAGES = {'modelos': 'models', 'configuracoes': 'settings', 'assets': 'assets', 'historico-pdfs': 'pdf-history'}

@app.get('/hub/<page>')
def hub_page(page):
    page_key = HUB_PAGES.get(page)
    if not page_key:
        abort(404)
    return render_template('index.html', initial_page=page_key)


@app.get('/api/<resource>')
def list_resource(resource):
    schema = SCHEMAS.get(resource)
    if not schema:
        return jsonify(error='Módulo não encontrado.'), 404
    with connect() as db:
        rows = db.execute(f"SELECT * FROM {schema['table']} ORDER BY id DESC").fetchall()
    return jsonify([dict(row) for row in rows])


@app.post('/api/<resource>')
def create_resource(resource):
    schema = SCHEMAS.get(resource)
    if not schema:
        return jsonify(error='Módulo não encontrado.'), 404
    data = request.get_json(silent=True) or request.form.to_dict()
    missing = [f for f in schema['required'] if not str(data.get(f, '')).strip()]
    if missing:
        return jsonify(error='Preencha os campos obrigatórios: ' + ', '.join(missing)), 400
    values = {}
    for field in schema['fields']:
        value = data.get(field, schema['defaults'].get(field, ''))
        if value is None:
            value = ''
        if callable(value):
            value = value()
        if field in ('amount', 'budget', 'sales', 'chargebacks', 'reverse_logistics', 'target'):
            try: value = float(str(value).replace(',', '.') or 0)
            except ValueError: return jsonify(error=f'Valor inválido para {field}.'), 400
        if field in ('orders_count', 'returns_count'):
            try: value = int(value or 0)
            except ValueError: return jsonify(error=f'Número inválido para {field}.'), 400
        values[field] = value
    columns = ','.join(values.keys())
    placeholders = ','.join(['?'] * len(values))
    try:
        with connect() as db:
            cur = db.execute(f"INSERT INTO {schema['table']} ({columns}) VALUES ({placeholders})", list(values.values()))
            row = db.execute(f"SELECT * FROM {schema['table']} WHERE id=?", (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201
    except sqlite3.IntegrityError:
        return jsonify(error='Já existe um registro para esse mês.'), 409


@app.put('/api/<resource>/<int:item_id>')
def update_resource(resource, item_id):
    schema = SCHEMAS.get(resource)
    if not schema:
        return jsonify(error='Módulo não encontrado.'), 404
    data = request.get_json(silent=True) or {}
    if not data:
        return jsonify(error='Nenhum dado recebido.'), 400
    fields = [f for f in schema['fields'] if f in data]
    if not fields:
        return jsonify(error='Nenhum campo válido informado.'), 400
    values = []
    for field in fields:
        value = data[field]
        if field in ('amount', 'budget', 'sales', 'chargebacks', 'reverse_logistics', 'target'):
            try: value = float(str(value).replace(',', '.') or 0)
            except ValueError: return jsonify(error=f'Valor inválido para {field}.'), 400
        values.append(value)
    with connect() as db:
        cur = db.execute(f"UPDATE {schema['table']} SET " + ','.join(f'{f}=?' for f in fields) + ' WHERE id=?', values + [item_id])
        if cur.rowcount == 0:
            return jsonify(error='Registro não encontrado.'), 404
        row = db.execute(f"SELECT * FROM {schema['table']} WHERE id=?", (item_id,)).fetchone()
    return jsonify(dict(row))


@app.delete('/api/<resource>/<int:item_id>')
def delete_resource(resource, item_id):
    schema = SCHEMAS.get(resource)
    if not schema:
        return jsonify(error='Módulo não encontrado.'), 404
    with connect() as db:
        cur = db.execute(f"DELETE FROM {schema['table']} WHERE id=?", (item_id,))
    if cur.rowcount == 0:
        return jsonify(error='Registro não encontrado.'), 404
    return jsonify(ok=True)


@app.get('/api/dashboard')
def dashboard():
    with connect() as db:
        orders = db.execute('SELECT COUNT(*) n, COALESCE(SUM(amount),0) total FROM orders').fetchone()
        open_orders = db.execute("SELECT COUNT(*) FROM orders WHERE status NOT IN ('Entregue','Cancelado')").fetchone()[0]
        active_campaigns = db.execute("SELECT COUNT(*) FROM campaigns WHERE status IN ('Ativa','Em andamento')").fetchone()[0]
        pending_tasks = db.execute("SELECT COUNT(*) FROM tasks WHERE status NOT IN ('Concluída','Concluido')").fetchone()[0]
        returns_open = db.execute("SELECT COUNT(*) FROM returns WHERE status NOT IN ('Concluída','Concluido','Finalizada')").fetchone()[0]
        recent_orders = [dict(r) for r in db.execute('SELECT * FROM orders ORDER BY id DESC LIMIT 5').fetchall()]
        tasks = [dict(r) for r in db.execute("SELECT * FROM tasks WHERE status NOT IN ('Concluída','Concluido') ORDER BY CASE priority WHEN 'Alta' THEN 1 WHEN 'Média' THEN 2 ELSE 3 END, id DESC LIMIT 5").fetchall()]
        latest_metric = db.execute('SELECT * FROM metrics ORDER BY month DESC LIMIT 1').fetchone()
    metric = dict(latest_metric) if latest_metric else None
    return jsonify({'orders_count': orders['n'], 'orders_total': orders['total'], 'open_orders': open_orders,
                    'active_campaigns': active_campaigns, 'pending_tasks': pending_tasks, 'open_returns': returns_open,
                    'recent_orders': recent_orders, 'tasks': tasks, 'latest_metric': metric})




DOCUMENT_TEMPLATES = [
    {'id':'meeting','name':'Pauta de reunião','category':'Reuniões','description':'Objetivo, participantes, tópicos e decisões.','icon':'▤','color':'lavender','sections':['Objetivo da reunião','Participantes','Pauta e tópicos','Decisões e próximos passos']},
    {'id':'timeline','name':'Cronograma de projeto','category':'Projetos','description':'Etapas, responsáveis, prazos e status.','icon':'◷','color':'blue','sections':['Objetivo e escopo','Etapas do projeto','Responsáveis e prazos','Riscos e observações']},
    {'id':'campaign','name':'Planejamento de campanha','category':'Marketing','description':'Oferta, canais, calendário e indicadores.','icon':'✳','color':'pink','sections':['Objetivo da campanha','Público e oferta','Canais e peças','Calendário','Meta e indicadores']},
    {'id':'content','name':'Calendário de conteúdo','category':'Marketing','description':'Organize publicações, formatos e datas.','icon':'▦','color':'amber','sections':['Tema','Canal','Formato','Data de publicação','Responsável']},
    {'id':'briefing','name':'Briefing para agência','category':'Agência','description':'Centralize referências, entregáveis e aprovações.','icon':'✎','color':'mint','sections':['Contexto','Objetivo','Público-alvo','Entregáveis','Referências','Prazo e aprovação']},
    {'id':'monthly','name':'Fechamento mensal','category':'Relatórios','description':'Resumo de resultados e pontos de atenção.','icon':'▥','color':'lavender','sections':['Resumo do mês','Vendas e metas','Chargebacks e devoluções','Logística reversa','Próximas ações']}
]

@app.get('/api/document-templates')
def document_templates():
    return jsonify(DOCUMENT_TEMPLATES)

@app.get('/api/identity')
def get_identity():
    with connect() as db:
        row = db.execute('SELECT * FROM identity_settings WHERE id=1').fetchone()
    return jsonify(dict(row) if row else {})

@app.put('/api/identity')
def save_identity():
    data = request.get_json(silent=True) or {}
    allowed = ['primary_color','secondary_color','accent_color','font_family']
    values = {k: str(data.get(k, '')).strip() for k in allowed if k in data}
    for key in ('primary_color','secondary_color','accent_color'):
        if key in values and not re.fullmatch(r'#[0-9a-fA-F]{6}', values[key]):
            return jsonify(error=f'Cor inválida em {key}.'), 400
    if 'font_family' in values and values['font_family'] not in ['Manrope','DM Sans','Arial','Georgia','Verdana']:
        return jsonify(error='Tipografia não permitida.'), 400
    if not values:
        return jsonify(error='Nenhuma configuração recebida.'), 400
    with connect() as db:
        db.execute('UPDATE identity_settings SET '+','.join(f'{k}=?' for k in values)+", updated_at=CURRENT_TIMESTAMP WHERE id=1", list(values.values()))
        row = db.execute('SELECT * FROM identity_settings WHERE id=1').fetchone()
    return jsonify(dict(row))

@app.post('/api/identity/logo')
def upload_identity_logo():
    file = request.files.get('logo')
    if not file or not file.filename:
        return jsonify(error='Selecione um arquivo de logotipo.'), 400
    ext = file.filename.rsplit('.',1)[-1].lower() if '.' in file.filename else ''
    if ext not in {'png','jpg','jpeg','webp','svg'}:
        return jsonify(error='Formato de logotipo não permitido.'), 400
    stored = f'logo-{uuid.uuid4().hex}.{ext}'
    file.save(UPLOAD_DIR / stored)
    with connect() as db:
        db.execute('UPDATE identity_settings SET logo_filename=?, updated_at=CURRENT_TIMESTAMP WHERE id=1',(stored,))
    return jsonify(logo_url=f'/uploads/{stored}', filename=file.filename)

@app.get('/api/assets')
def list_assets():
    with connect() as db:
        rows = db.execute('SELECT * FROM assets ORDER BY id DESC').fetchall()
    return jsonify([dict(r) for r in rows])

@app.post('/api/assets')
def create_asset():
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify(error='Selecione um arquivo.'), 400
    original = secure_filename(file.filename)
    ext = original.rsplit('.',1)[-1].lower() if '.' in original else ''
    if ext not in ALLOWED_ASSET_EXTENSIONS:
        return jsonify(error='Tipo de arquivo não permitido.'), 400
    stored = f'{uuid.uuid4().hex}.{ext}'
    file.save(UPLOAD_DIR / stored)
    size = (UPLOAD_DIR / stored).stat().st_size
    with connect() as db:
        cur = db.execute('INSERT INTO assets (original_name,stored_name,file_type,file_size) VALUES (?,?,?,?)', (original,stored,ext,size))
        row = db.execute('SELECT * FROM assets WHERE id=?',(cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201

@app.delete('/api/assets/<int:asset_id>')
def delete_asset(asset_id):
    with connect() as db:
        row = db.execute('SELECT * FROM assets WHERE id=?',(asset_id,)).fetchone()
        if not row: return jsonify(error='Arquivo não encontrado.'),404
        db.execute('DELETE FROM assets WHERE id=?',(asset_id,))
    try: (UPLOAD_DIR / row['stored_name']).unlink(missing_ok=True)
    except OSError: pass
    return jsonify(ok=True)

@app.get('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=False)

@app.get('/api/pdf-exports')
def list_pdf_exports():
    with connect() as db:
        rows = db.execute('SELECT * FROM pdf_exports ORDER BY id DESC LIMIT 100').fetchall()
    return jsonify([dict(r) for r in rows])

@app.post('/api/pdf-exports')
def create_pdf_export():
    data = request.get_json(silent=True) or {}
    title = str(data.get('title','')).strip()[:120]
    category = str(data.get('category','Planejamento')).strip()[:60]
    content = str(data.get('content','')).strip()[:20000]
    if not title or not content:
        return jsonify(error='Informe o título e o conteúdo do documento.'),400
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image
        from reportlab.lib.units import mm
        from xml.sax.saxutils import escape
        with connect() as db:
            identity = dict(db.execute('SELECT * FROM identity_settings WHERE id=1').fetchone())
        primary = colors.HexColor(identity.get('primary_color') or '#5a2b91')
        secondary = colors.HexColor(identity.get('secondary_color') or '#35145e')
        accent = colors.HexColor(identity.get('accent_color') or '#d6b5fa')
        font_map = {'Manrope':'Helvetica','DM Sans':'Helvetica','Arial':'Helvetica','Georgia':'Times-Roman','Verdana':'Helvetica'}
        body_font = font_map.get(identity.get('font_family'), 'Helvetica')
        filename = f'lollix-{datetime.now().strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:6]}.pdf'
        path = PDF_DIR / filename
        doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=22*mm, leftMargin=22*mm, topMargin=22*mm, bottomMargin=20*mm)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name='LollixTitle', parent=styles['Title'], textColor=primary, fontName=body_font+'-Bold' if body_font != 'Times-Roman' else 'Times-Bold', fontSize=20, leading=25, spaceAfter=8))
        styles.add(ParagraphStyle(name='LollixBrand', parent=styles['Heading2'], textColor=secondary, fontName='Helvetica-Bold', fontSize=13, leading=17, spaceAfter=8))
        styles.add(ParagraphStyle(name='LollixBody', parent=styles['BodyText'], fontName=body_font, fontSize=10, leading=16, textColor=colors.HexColor('#39323f'), spaceAfter=7))
        story = []
        logo = identity.get('logo_filename') or ''
        if logo and Path(logo).suffix.lower() in {'.png','.jpg','.jpeg'} and (UPLOAD_DIR / logo).exists():
            logo_img = Image(str(UPLOAD_DIR / logo), width=42*mm, height=18*mm, kind='proportional')
            story.extend([logo_img, Spacer(1,6)])
        else:
            story.append(Paragraph('<b>LOLLIX</b>  GESTÃO DIGITAL', styles['LollixBrand']))
        story.extend([Paragraph(escape(title), styles['LollixTitle']), Paragraph(f'{escape(category)} · Gerado em {datetime.now().strftime("%d/%m/%Y às %H:%M")}', styles['BodyText']), Spacer(1,8), HRFlowable(width='100%', thickness=1, color=primary), Spacer(1,5), HRFlowable(width='24%', thickness=2, color=accent), Spacer(1,12)])
        for line in content.splitlines():
            clean = escape(line.strip())
            if clean:
                if clean.endswith(':') or (len(clean)<90 and clean.isupper()): story.append(Paragraph(f'<b>{clean}</b>', styles['LollixBody']))
                else: story.append(Paragraph(clean.replace('  ','&nbsp;&nbsp;'), styles['LollixBody']))
            else: story.append(Spacer(1,5))
        doc.build(story)
    except ImportError:
        return jsonify(error='Para gerar PDFs, instale as dependências com: pip install -r requirements.txt'),503
    size = path.stat().st_size
    with connect() as db:
        cur = db.execute('INSERT INTO pdf_exports (title,category,stored_name,file_size) VALUES (?,?,?,?)',(title,category,filename,size))
        row = db.execute('SELECT * FROM pdf_exports WHERE id=?',(cur.lastrowid,)).fetchone()
    return jsonify({**dict(row),'download_url':f'/pdfs/{filename}'}),201

@app.get('/pdfs/view/<path:filename>')
def view_pdf(filename):
    if not filename.endswith('.pdf'): abort(404)
    return send_from_directory(PDF_DIR, filename, as_attachment=False)

@app.get('/pdfs/<path:filename>')
def download_pdf(filename):
    if not filename.endswith('.pdf'): abort(404)
    return send_from_directory(PDF_DIR, filename, as_attachment=True)


@app.get('/api/health')
def health():
    return jsonify(status='ok', app='LOLLIX GESTÃO', database='SQLite')


init_db()
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5000)), debug=os.environ.get('FLASK_DEBUG') == '1')
