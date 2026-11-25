"""Выгрузка содержимого базы ufa_arenda.db в data.json для просмотрщика dbviewer.html.

Запускать из каталога проекта:  python refresh_db.py
"""
import json
import os
import sqlite3

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, 'ufa_arenda.db')
OUT = os.path.join(BASE, 'data.json')

TABLES = ['applications', 'tenants', 'properties', 'saved_searches',
          'owners', 'districts', 'realtors', 'contracts']

# Поля, которые не показываются в просмотрщике
HIDDEN = {'passport_data', 'password_hash'}


def export():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    payload = {'tables': {}, 'columns': {}, 'counts': {}}
    for table in TABLES:
        try:
            rows = [dict(r) for r in conn.execute(f'SELECT * FROM {table}')]
        except sqlite3.Error:
            rows = []
        columns = [c for c in (rows[0].keys() if rows else []) if c not in HIDDEN]
        if not columns:  # пустая таблица — берём схему
            columns = [c['name'] for c in conn.execute(f'PRAGMA table_info({table})')
                       if c['name'] not in HIDDEN]
        payload['tables'][table] = [{c: row.get(c) for c in columns} for row in rows]
        payload['columns'][table] = columns
        payload['counts'][table] = len(rows)
    conn.close()
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, default=str)
    print('data.json обновлён:', {k: v for k, v in payload['counts'].items()})


if __name__ == '__main__':
    export()
