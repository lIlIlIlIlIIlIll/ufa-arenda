import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), 'ufa_arenda.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_PATH):
        conn = get_db()
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()

@app.route('/')
def index():
    district_id = request.args.get('district_id', '')
    conn = get_db()
    districts = conn.execute('SELECT * FROM districts ORDER BY district_id').fetchall()
    
    query = '''
        SELECT p.*, d.name AS district_name, o.full_name AS owner_name
        FROM properties p
        JOIN districts d ON p.district_id = d.district_id
        JOIN owners o ON p.owner_id = o.owner_id
        WHERE p.status = 'Активен'
    '''
    params = []
    if district_id:
        query += ' AND p.district_id = ?'
        params.append(district_id)
        
    properties = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('index.html', properties=properties, districts=districts, selected_district=district_id)

@app.route('/apply', methods=['POST'])
def apply():
    full_name = request.form.get('full_name', '').strip()
    phone = request.form.get('phone', '').strip()
    district = request.form.get('desired_district', 'Уфа')
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute('INSERT INTO tenants (full_name, phone) VALUES (?, ?)', (full_name, phone))
    tenant_id = cur.lastrowid
    cur.execute('INSERT INTO applications (tenant_id, property_id, realtor_id, desired_district, status) VALUES (?, 1, 1, ?, "Новая")', (tenant_id, district))
    conn.commit()
    conn.close()
    return redirect(url_for('index', success='1'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
