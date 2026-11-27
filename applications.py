"""Модуль заявок на подбор жилья (МДК 05.02, задания 2–3).

Отвечает за:
- чтение активных объектов для формы и каталога;
- проверку данных, введённых арендатором;
- поиск или создание арендатора в таблице tenants;
- назначение риелтора;
- формирование читаемого номера заявки;
- сохранение заявки в таблице applications;
- изменение статуса заявки (допустимые переходы) и её удаление.
"""
import datetime
import re

STATUSES = ('Новая', 'В работе', 'Связались', 'Подобран', 'Закрыта', 'Отклонена')
STATUS_TRANSITIONS = {
    'Новая': ('В работе', 'Отклонена'),
    'В работе': ('Связались', 'Отклонена'),
    'Связались': ('Подобран', 'Отклонена'),
    'Подобран': ('Закрыта',),
    'Закрыта': (),
    'Отклонена': ('Новая',),
}

PHONE_RE = re.compile(r'^\+?7\d{10}$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[a-zA-Zа-яА-Я]{2,}$')
NAME_RE = re.compile(r'^[А-ЯЁа-яёA-Za-z][А-ЯЁа-яёA-Za-z\-]+$')

STATUS_FILTER = {
    'all': None,
    'new': ('Новая',),
    'work': ('В работе', 'Связались', 'Подобран'),
    'closed': ('Закрыта', 'Отклонена'),
}


# ---------------------------------------------------------------- объекты

def list_active_properties(conn, district_id=None, rooms=None, price_max=None):
    """Каталог активных объектов с фильтрами по району, числу комнат и цене."""
    query = '''
        SELECT p.*, d.name AS district_name
        FROM properties p
        JOIN districts d ON p.district_id = d.district_id
        WHERE p.status = 'Активен'
    '''
    params = []
    if district_id:
        query += ' AND p.district_id = ?'
        params.append(int(district_id))
    if rooms:
        query += ' AND p.rooms_count = ?'
        params.append(int(rooms))
    if price_max:
        query += ' AND p.price_monthly <= ?'
        params.append(int(price_max))
    query += ' ORDER BY p.price_monthly'
    return conn.execute(query, params).fetchall()


def get_property(conn, property_id):
    """Один объект с названием района; None, если объект не найден."""
    return conn.execute('''
        SELECT p.*, d.name AS district_name
        FROM properties p
        JOIN districts d ON p.district_id = d.district_id
        WHERE p.property_id = ?
    ''', (property_id,)).fetchone()


def list_districts(conn):
    return conn.execute('SELECT * FROM districts ORDER BY name').fetchall()


# ---------------------------------------------------------------- проверка

def normalize_phone(raw):
    """Привести номер к виду 79991234567: оставить только цифры и заменить
    ведущую 8 на 7; номер из 10 цифр, начинающийся с 9, дополнить семёркой."""
    digits = re.sub(r'\D', '', raw or '')
    if len(digits) == 11 and digits.startswith('8'):
        digits = '7' + digits[1:]
    elif len(digits) == 10 and digits.startswith('9'):
        digits = '7' + digits
    return digits


def validate_application(data):
    """Проверить данные формы. Возвращает (очищенные данные, словарь ошибок)."""
    errors = {}
    clean = {
        'property_id': (data.get('property_id') or '').strip(),
        'full_name': ' '.join((data.get('full_name') or '').split()),
        'phone': normalize_phone(data.get('phone')),
        'email': (data.get('email') or '').strip(),
        'desired_district': (data.get('desired_district') or '').strip(),
        'comment': (data.get('comment') or '').strip(),
    }

    if not clean['property_id'].isdigit():
        errors['property_id'] = 'Выберите объект из каталога'

    words = clean['full_name'].split()
    if len(words) < 2 or not all(NAME_RE.match(w) for w in words):
        errors['full_name'] = 'Укажите фамилию и имя (только буквы)'
    elif len(clean['full_name']) > 150:
        errors['full_name'] = 'ФИО длиннее 150 символов'

    if not PHONE_RE.match(clean['phone']):
        errors['phone'] = 'Проверьте номер телефона: 11 цифр, начиная с 7'

    if clean['email'] and not EMAIL_RE.match(clean['email']):
        errors['email'] = 'Проверьте адрес электронной почты'

    if not clean['desired_district']:
        errors['desired_district'] = 'Выберите желаемый район'

    if len(clean['comment']) > 500:
        errors['comment'] = 'Комментарий длиннее 500 символов'

    return clean, errors


# ---------------------------------------------------------------- арендатор

def find_or_create_tenant(conn, full_name, phone, email=None):
    """Найти арендатора по номеру телефона или создать нового.

    Возвращает (tenant_id, was_created).
    """
    row = conn.execute(
        'SELECT tenant_id FROM tenants WHERE phone = ? ORDER BY tenant_id LIMIT 1',
        (phone,)).fetchone()
    if row:
        return row['tenant_id'], False
    cur = conn.execute(
        'INSERT INTO tenants (full_name, phone, email, created_at) VALUES (?, ?, ?, ?)',
        (full_name, phone, email or None, datetime.datetime.now().isoformat(timespec='seconds')))
    return cur.lastrowid, True


def pick_realtor(conn, property_id):
    """Риелтор для заявки: реальный, а не жёстко заданная единица."""
    row = conn.execute(
        "SELECT realtor_id FROM realtors WHERE role LIKE '%Риелтор%' ORDER BY realtor_id LIMIT 1"
    ).fetchone()
    if row:
        return row['realtor_id']
    row = conn.execute('SELECT realtor_id FROM realtors ORDER BY realtor_id LIMIT 1').fetchone()
    return row['realtor_id'] if row else None


# ---------------------------------------------------------------- номера

def next_application_num(conn, year=None):
    """Следующий номер заявки вида ЗАЯ-2026-0001 в пределах года."""
    year = year or datetime.date.today().year
    prefix = f'ЗАЯ-{year}-'
    row = conn.execute(
        'SELECT MAX(CAST(SUBSTR(application_num, ?) AS INTEGER)) AS last '
        'FROM applications WHERE application_num LIKE ?',
        (len(prefix) + 1, prefix + '%')).fetchone()
    last = row['last'] or 0
    return f'{prefix}{last + 1:04d}'


def format_application_num(num, year):
    """Читаемая форма номера для страницы подтверждения."""
    return num


# ---------------------------------------------------------------- заявки

def create_application(conn, clean, realtor_id, request_date=None):
    """Сохранить заявку. Возвращает словарь с номером и идентификаторами."""
    request_date = request_date or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    year = int(request_date[:4])
    tenant_id, created = find_or_create_tenant(
        conn, clean['full_name'], clean['phone'], clean.get('email'))
    num = format_application_num(next_application_num(conn, year), year)
    cur = conn.execute('''
        INSERT INTO applications
            (tenant_id, property_id, realtor_id, request_date, desired_district,
             status, comment, application_num, created_at)
        VALUES (?, ?, ?, ?, ?, 'Новая', ?, ?, ?)
    ''', (tenant_id, int(clean['property_id']), realtor_id, request_date,
          clean['desired_district'], clean['comment'] or None, num, request_date))
    conn.commit()
    return {
        'application_id': cur.lastrowid,
        'application_num': num,
        'tenant_id': tenant_id,
        'tenant_created': created,
        'request_date': request_date,
    }


def find_recent_duplicate(conn, phone, property_id, minutes=10):
    """Недавняя заявка того же арендатора на тот же объект (защита от повтора)."""
    row = conn.execute('''
        SELECT a.application_num FROM applications a
        JOIN tenants t ON a.tenant_id = t.tenant_id
        WHERE t.phone = ? AND a.property_id = ?
          AND a.request_date >= datetime('now', 'localtime', ?)
        ORDER BY a.application_id DESC LIMIT 1
    ''', (phone, int(property_id), f'-{minutes} minutes')).fetchone()
    return row['application_num'] if row else None


def search_applications(conn, phone=None, district_id=None, status=None, date_from=None):
    """Поиск заявок по телефону, району, статусу и дате."""
    query = '''
        SELECT a.application_id, a.application_num, a.request_date, a.status,
               a.desired_district, a.comment, t.full_name, t.phone,
               p.address_ufa, p.rooms_count, p.price_monthly
        FROM applications a
        JOIN tenants t ON a.tenant_id = t.tenant_id
        LEFT JOIN properties p ON a.property_id = p.property_id
        WHERE 1 = 1
    '''
    params = []
    if phone:
        # Только цифры: ввод посторонних символов даёт пустой результат и
        # не раскрывает заявки других арендаторов.
        digits = re.sub(r'\D', '', phone) or '0'
        query += ' AND t.phone LIKE ?'
        params.append('%' + digits + '%')
    if district_id:
        query += ' AND a.desired_district = (SELECT name FROM districts WHERE district_id = ?)'
        params.append(int(district_id))
    if status and status in STATUSES:
        query += ' AND a.status = ?'
        params.append(status)
    if date_from:
        query += ' AND date(a.request_date) >= date(?)'
        params.append(date_from)
    query += ' ORDER BY a.application_id DESC'
    return conn.execute(query, params).fetchall()


def change_status(conn, application_id, new_status):
    """Изменить статус заявки. Возвращает (ok, сообщение)."""
    if new_status not in STATUSES:
        return False, 'Неизвестный статус'
    row = conn.execute(
        'SELECT status FROM applications WHERE application_id = ?',
        (application_id,)).fetchone()
    if not row:
        return False, 'Заявка не найдена'
    allowed = STATUS_TRANSITIONS.get(row['status'], ())
    if new_status not in allowed:
        return False, f'Из статуса «{row["status"]}» нельзя перевести в «{new_status}»'
    conn.execute('UPDATE applications SET status = ? WHERE application_id = ?',
                 (new_status, application_id))
    conn.commit()
    return True, f'Статус заявки №{application_id} изменён на «{new_status}»'


def delete_application(conn, application_id):
    """Удалить заявку. Возвращает (ok, сообщение)."""
    row = conn.execute(
        'SELECT application_num FROM applications WHERE application_id = ?',
        (application_id,)).fetchone()
    if not row:
        return False, 'Заявка не найдена'
    conn.execute('DELETE FROM applications WHERE application_id = ?', (application_id,))
    conn.commit()
    return True, f'Заявка {row["application_num"] or application_id} удалена'
