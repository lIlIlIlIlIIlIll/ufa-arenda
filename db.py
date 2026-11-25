"""Подключение к базе данных SQLite, создание и обновление схемы."""
import os
import sqlite3

from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'ufa_arenda.db')
SCHEMA_PATH = os.path.join(BASE_DIR, 'schema.sql')


def get_db():
    """Соединение с базой: строки доступны по именам полей, FK включены."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    """Создать базу из schema.sql, если файла базы ещё нет."""
    if not os.path.exists(DB_PATH):
        conn = get_db()
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()


def _columns(conn, table):
    return [row['name'] for row in conn.execute(f'PRAGMA table_info({table})')]


def migrate_db():
    """Довести существующую базу до актуальной схемы без потери данных.

    Добавляет столбцы и таблицы, которых нет в старой базе. Каждый шаг
    идемпотентен, поэтому миграцию можно запускать при каждом старте.
    """
    conn = get_db()
    try:
        # WAL — режим журнала: чтение не блокирует запись, запись не блокирует чтение.
        conn.execute('PRAGMA journal_mode=WAL')
        cols = _columns(conn, 'applications')
        if 'application_num' not in cols:
            conn.execute('ALTER TABLE applications ADD COLUMN application_num VARCHAR(20)')
        if 'created_at' not in cols:
            conn.execute('ALTER TABLE applications ADD COLUMN created_at TIMESTAMP')
        conn.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS ux_applications_num '
            'ON applications(application_num)')

        cols = _columns(conn, 'tenants')
        if 'created_at' not in cols:
            conn.execute('ALTER TABLE tenants ADD COLUMN created_at TIMESTAMP')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS saved_searches (
                search_id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_name VARCHAR(100) NOT NULL,
                district_id INTEGER,
                rooms_count INTEGER,
                price_max INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (district_id) REFERENCES districts(district_id)
            )''')
        conn.execute(
            'CREATE INDEX IF NOT EXISTS ix_applications_status '
            'ON applications(status)')

        # Пароли новых учётных записей хранятся хешем (werkzeug), старые записи
        # остаются как есть и будут перехешированы при следующем изменении.
        for row in conn.execute('SELECT realtor_id, password_hash FROM realtors').fetchall():
            if not row['password_hash'].startswith(('scrypt:', 'pbkdf2:')):
                conn.execute('UPDATE realtors SET password_hash = ? WHERE realtor_id = ?',
                             (generate_password_hash(row['password_hash']), row['realtor_id']))
        conn.commit()
        return True
    finally:
        conn.close()


def schema_dump():
    """Текст DDL всех объектов базы — используется в отчёте и для проверки."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type DESC, name").fetchall()
        return '\n\n'.join(r['sql'] + ';' for r in rows if r['sql'])
    finally:
        conn.close()
