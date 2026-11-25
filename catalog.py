"""Учёт объектов аренды: добавление, просмотр, изменение, удаление
и поиск записей в базе (МДК 05.02, задание 3).

Все изменения сохраняются в таблицах properties, owners, districts и
saved_searches, поэтому после перезапуска приложения результат остаётся.
"""
import re


PROPERTY_STATUSES = ('Активен', 'Снят с публикации', 'Сдан')


def validate_property(data):
    """Проверить данные формы объекта. Возвращает (clean, errors)."""
    errors = {}
    clean = {
        'address_ufa': ' '.join((data.get('address_ufa') or '').split()),
        'district_id': (data.get('district_id') or '').strip(),
        'owner_id': (data.get('owner_id') or '').strip(),
        'property_type': (data.get('property_type') or 'Квартира').strip(),
        'rooms_count': (data.get('rooms_count') or '').strip(),
        'area_total': (data.get('area_total') or '').replace(',', '.').strip(),
        'floor_info': (data.get('floor_info') or '').strip(),
        'price_monthly': (data.get('price_monthly') or '').strip(),
        'status': (data.get('status') or 'Активен').strip(),
        'description': (data.get('description') or '').strip(),
    }
    if len(clean['address_ufa']) < 8 or len(clean['address_ufa']) > 255:
        errors['address_ufa'] = 'Укажите адрес: «г. Уфа, ул. …» (от 8 до 255 символов)'
    if not clean['district_id'].isdigit():
        errors['district_id'] = 'Выберите район'
    if not clean['owner_id'].isdigit():
        errors['owner_id'] = 'Выберите собственника'
    if not clean['rooms_count'].isdigit() or not 1 <= int(clean['rooms_count']) <= 9:
        errors['rooms_count'] = 'Число комнат — целое число от 1 до 9'
    try:
        area = float(clean['area_total'])
        if not 10 <= area <= 1000:
            errors['area_total'] = 'Площадь должна быть от 10 до 1000 м²'
    except ValueError:
        errors['area_total'] = 'Площадь — число, например 58.5'
    try:
        price = int(clean['price_monthly'])
        if not 5000 <= price <= 1000000:
            errors['price_monthly'] = 'Цена — целое число от 5 000 до 1 000 000 ₽'
    except ValueError:
        errors['price_monthly'] = 'Цена — целое число, например 32000'
    if not re.match(r'^\d{1,2}/\d{1,2}$', clean['floor_info']):
        errors['floor_info'] = 'Этаж в формате «этаж/этажность», например 5/9'
    if clean['status'] not in PROPERTY_STATUSES:
        errors['status'] = 'Недопустимый статус'
    if len(clean['description']) > 1000:
        errors['description'] = 'Описание длиннее 1000 символов'
    return clean, errors


def list_properties(conn, query=None, district_id=None, status=None,
                    rooms=None, price_max=None):
    """Поиск объектов по тексту, району, статусу, числу комнат и цене."""
    sql = '''
        SELECT p.*, d.name AS district_name, o.full_name AS owner_name
        FROM properties p
        JOIN districts d ON p.district_id = d.district_id
        JOIN owners o ON p.owner_id = o.owner_id
        WHERE 1 = 1
    '''
    params = []
    if query:
        sql += ' AND (lower(p.address_ufa) LIKE lower(?) OR lower(p.description) LIKE lower(?))'
        params += [f'%{query}%', f'%{query}%']
    if district_id:
        sql += ' AND p.district_id = ?'
        params.append(int(district_id))
    if status:
        sql += ' AND p.status = ?'
        params.append(status)
    if rooms:
        sql += ' AND p.rooms_count = ?'
        params.append(int(rooms))
    if price_max:
        sql += ' AND p.price_monthly <= ?'
        params.append(int(price_max))
    sql += ' ORDER BY p.property_id DESC'
    return conn.execute(sql, params).fetchall()


def get_property(conn, property_id):
    return conn.execute('''
        SELECT p.*, d.name AS district_name, o.full_name AS owner_name
        FROM properties p
        JOIN districts d ON p.district_id = d.district_id
        JOIN owners o ON p.owner_id = o.owner_id
        WHERE p.property_id = ?
    ''', (property_id,)).fetchone()


def create_property(conn, clean):
    cur = conn.execute('''
        INSERT INTO properties
            (owner_id, district_id, property_type, address_ufa, rooms_count,
             area_total, floor_info, price_monthly, status, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (int(clean['owner_id']), int(clean['district_id']), clean['property_type'],
          clean['address_ufa'], int(clean['rooms_count']), float(clean['area_total']),
          clean['floor_info'], int(clean['price_monthly']), clean['status'],
          clean['description'] or None))
    conn.commit()
    return cur.lastrowid


def update_property(conn, property_id, clean):
    cur = conn.execute('''
        UPDATE properties SET
            owner_id = ?, district_id = ?, property_type = ?, address_ufa = ?,
            rooms_count = ?, area_total = ?, floor_info = ?, price_monthly = ?,
            status = ?, description = ?
        WHERE property_id = ?
    ''', (int(clean['owner_id']), int(clean['district_id']), clean['property_type'],
          clean['address_ufa'], int(clean['rooms_count']), float(clean['area_total']),
          clean['floor_info'], int(clean['price_monthly']), clean['status'],
          clean['description'] or None, property_id))
    conn.commit()
    return cur.rowcount > 0


def delete_property(conn, property_id):
    """Удалить объект. Возвращает (ok, сообщение)."""
    linked = conn.execute(
        'SELECT COUNT(*) AS n FROM applications WHERE property_id = ?',
        (property_id,)).fetchone()['n']
    if linked:
        return False, f'Объект связан с {linked} заявками: удаление запрещено, измените статус на «Снят с публикации»'
    conn.execute('DELETE FROM properties WHERE property_id = ?', (property_id,))
    conn.commit()
    return True, 'Объект удалён из базы'


def list_owners(conn):
    return conn.execute('SELECT * FROM owners ORDER BY full_name').fetchall()


def create_owner(conn, full_name, phone, passport_data, egrn_number):
    cur = conn.execute('''
        INSERT INTO owners (full_name, phone, passport_data, egrn_number)
        VALUES (?, ?, ?, ?)
    ''', (full_name.strip(), phone.strip(), passport_data.strip(), egrn_number.strip()))
    conn.commit()
    return cur.lastrowid


# ------------------------------------------------------------ сохранённые поиски

def list_saved_searches(conn):
    return conn.execute('''
        SELECT s.*, d.name AS district_name
        FROM saved_searches s
        LEFT JOIN districts d ON s.district_id = d.district_id
        ORDER BY s.search_id DESC
    ''').fetchall()


def save_search(conn, search_name, district_id=None, rooms_count=None, price_max=None):
    cur = conn.execute('''
        INSERT INTO saved_searches (search_name, district_id, rooms_count, price_max)
        VALUES (?, ?, ?, ?)
    ''', (search_name.strip()[:100], district_id or None,
          rooms_count or None, price_max or None))
    conn.commit()
    return cur.lastrowid


def delete_saved_search(conn, search_id):
    conn.execute('DELETE FROM saved_searches WHERE search_id = ?', (search_id,))
    conn.commit()
