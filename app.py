"""ИС «ИС Аренда» — сайт агентства по аренде недвижимости в г. Уфа.

Маршруты публичной части:
  /                        каталог объектов с фильтрами и поиском
  /property/<id>           карточка объекта
  /apply?property_id=..    форма заявки на подбор жилья (GET)
  /apply                   сохранение заявки в базе (POST)
  /apply/success/<num>     подтверждение с номером заявки
  /applications            поиск заявки по номеру или телефону

Маршруты учёта данных (задание 3):
  /objects                 список объектов, поиск
  /objects/new             добавление объекта
  /objects/<id>/edit       изменение объекта
  /objects/<id>/delete     удаление объекта (POST)

Локальный вход в систему управления заявками:
  /manage/login, /manage/logout, /manage/applications, /manage/applications/<id>/status
"""
import datetime
import os

from flask import (Flask, flash, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash

import applications
import catalog
import db as database

app = Flask(__name__)
app.secret_key = os.environ.get('ARENDA_SECRET', 'ufa-arenda-practice-key')

# Попытки входа: не больше 5 неудач за 10 минут на один логин
FAILED_LOGINS = {}
MAX_FAILS = 5
LOCK_MINUTES = 10
app.jinja_env.filters['money'] = lambda v: f'{int(v):,}'.replace(',', ' ') if v is not None else '—'


@app.template_filter('ru_date')
def ru_date(value):
    if not value:
        return '—'
    return value[8:10] + '.' + value[5:7] + '.' + value[0:4] + ' ' + value[11:16]


@app.context_processor
def inject_globals():
    return {'current_year': datetime.date.today().year,
            'manager': session.get('manager'),
            'staff': bool(session.get('manager'))}


# ------------------------------------------------------------- служебные

def _int_arg(name):
    value = (request.args.get(name) or '').strip()
    return int(value) if value.isdigit() else None


def _int_arg_from_form(name):
    value = (request.form.get(name) or '').strip()
    return int(value) if value.isdigit() else None


def login_required(view):
    from functools import wraps

    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get('manager'):
            flash('Для работы с заявками войдите в систему', 'warning')
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapper


# ------------------------------------------------------------- каталог

@app.route('/')
def index():
    district_id = _int_arg('district_id')
    rooms = _int_arg('rooms')
    price_max = _int_arg('price_max')
    conn = database.get_db()
    try:
        items = applications.list_active_properties(conn, district_id, rooms, price_max)
        districts = applications.list_districts(conn)
        saved = catalog.list_saved_searches(conn)
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM properties WHERE status = 'Активен'").fetchone()['n']
    finally:
        conn.close()
    return render_template('index.html', properties=items, districts=districts,
                           saved_searches=saved, total=total,
                           selected_district=district_id, rooms=rooms,
                           price_max=price_max)


@app.route('/property/<int:property_id>')
def property_card(property_id):
    conn = database.get_db()
    try:
        item = applications.get_property(conn, property_id)
    finally:
        conn.close()
    if item is None:
        flash('Объект не найден', 'error')
        return redirect(url_for('index'))
    return render_template('property.html', prop=item)


@app.route('/search/save', methods=['POST'])
def save_search():
    district_id = _int_arg_from_form('district_id')
    rooms = _int_arg_from_form('rooms')
    price_max = _int_arg_from_form('price_max')
    name = ' '.join((request.form.get('search_name') or '').split()) or 'Мой поиск'
    if len(name) > 100 or '<' in name or '>' in name:
        flash('Название поиска: до 100 символов, без символов < и >', 'error')
        return redirect(url_for('index'))
    conn = database.get_db()
    try:
        catalog.save_search(conn, name, district_id, rooms, price_max)
    finally:
        conn.close()
    flash(f'Поиск «{name}» сохранён', 'success')
    args = {k: v for k, v in (('district_id', district_id), ('rooms', rooms),
                              ('price_max', price_max)) if v}
    return redirect(url_for('index', **args))


@app.route('/search/<int:search_id>/delete', methods=['POST'])
def delete_search(search_id):
    conn = database.get_db()
    try:
        catalog.delete_saved_search(conn, search_id)
    finally:
        conn.close()
    flash('Сохранённый поиск удалён', 'success')
    return redirect(url_for('index'))


# ------------------------------------------------------------- заявка

@app.route('/apply', methods=['GET'])
def apply_form():
    property_id = request.args.get('property_id', '').strip()
    conn = database.get_db()
    try:
        districts = applications.list_districts(conn)
        prop = applications.get_property(conn, int(property_id)) if property_id.isdigit() else None
        if prop is None:
            items = applications.list_active_properties(conn)
            prop = items[0] if items else None
        items = applications.list_active_properties(conn)
    finally:
        conn.close()
    return render_template('apply.html', prop=prop, properties=items,
                           districts=districts, form={}, errors={})


@app.route('/apply', methods=['POST'])
def apply_submit():
    form = request.form.to_dict()
    if any(len(v) > 500 for v in form.values()):
        flash('Слишком длинный текст в поле формы', 'error')
        return redirect(url_for('apply_form'))
    clean, errors = applications.validate_application(form)
    conn = database.get_db()
    try:
        prop = (applications.get_property(conn, int(clean['property_id']))
                if clean['property_id'].isdigit() else None)
        if prop is None:
            errors['property_id'] = 'Выберите объект из каталога'
        if not errors:
            duplicate = applications.find_recent_duplicate(
                conn, clean['phone'], clean['property_id'])
            if duplicate:
                errors['form'] = f'Заявка на этот объект уже принята сегодня (№{duplicate}). Мы свяжемся с вами.'
        if errors:
            districts = applications.list_districts(conn)
            items = applications.list_active_properties(conn)
            return render_template('apply.html', prop=prop, properties=items,
                                   districts=districts, form=form, errors=errors), 400
        realtor_id = applications.pick_realtor(conn, clean['property_id'])
        result = applications.create_application(conn, clean, realtor_id)
    finally:
        conn.close()
    return redirect(url_for('apply_success', num=result['application_num']))


@app.route('/apply/success/<num>')
def apply_success(num):
    conn = database.get_db()
    try:
        row = conn.execute('''
            SELECT a.*, t.full_name, t.phone, t.email, p.address_ufa, p.price_monthly,
                   d.name AS district_name
            FROM applications a
            JOIN tenants t ON a.tenant_id = t.tenant_id
            LEFT JOIN properties p ON a.property_id = p.property_id
            LEFT JOIN districts d ON p.district_id = d.district_id
            WHERE a.application_num = ?
        ''', (num,)).fetchone()
    finally:
        conn.close()
    if row is None:
        flash('Заявка не найдена', 'error')
        return redirect(url_for('index'))
    return render_template('apply_success.html', app_row=row)


@app.route('/applications')
def applications_search():
    num = (request.args.get('num') or '').strip()
    phone = (request.args.get('phone') or '').strip()
    results = None
    conn = database.get_db()
    try:
        if num or phone:
            rows = applications.search_applications(conn, phone=phone or None)
            if num:
                rows = [r for r in rows if r['application_num'] == num]
            results = rows
    finally:
        conn.close()
    return render_template('applications_search.html', results=results,
                           num=num, phone=phone)


# ------------------------------------------------------------- учёт объектов

@app.route('/objects')
def objects_list():
    query = (request.args.get('q') or '').strip()
    district_id = _int_arg('district_id')
    rooms = _int_arg('rooms')
    price_max = _int_arg('price_max')
    status = (request.args.get('status') or '').strip() or None
    conn = database.get_db()
    try:
        items = catalog.list_properties(conn, query, district_id, status, rooms, price_max)
        districts = applications.list_districts(conn)
    finally:
        conn.close()
    return render_template('objects_list.html', properties=items, districts=districts,
                           q=query, selected_district=district_id, rooms=rooms,
                           price_max=price_max, status=status,
                           statuses=catalog.PROPERTY_STATUSES)


@app.route('/objects/new', methods=['GET', 'POST'])
@login_required
def objects_create():
    errors, form = {}, {}
    conn = database.get_db()
    try:
        districts = applications.list_districts(conn)
        owners = catalog.list_owners(conn)
        if request.method == 'POST':
            form = request.form.to_dict()
            clean, errors = catalog.validate_property(form)
            if not errors:
                new_id = catalog.create_property(conn, clean)
                flash(f'Объект №{new_id} добавлен в базу', 'success')
                return redirect(url_for('objects_list'))
    finally:
        conn.close()
    return render_template('object_form.html', form=form, errors=errors,
                           districts=districts, owners=owners,
                           statuses=catalog.PROPERTY_STATUSES, action='create',
                           title='Добавление объекта')


@app.route('/objects/<int:property_id>/edit', methods=['GET', 'POST'])
@login_required
def objects_edit(property_id):
    errors = {}
    conn = database.get_db()
    try:
        districts = applications.list_districts(conn)
        owners = catalog.list_owners(conn)
        row = catalog.get_property(conn, property_id)
        if row is None:
            flash('Объект не найден', 'error')
            return redirect(url_for('objects_list'))
        form = dict(row)
        if request.method == 'POST':
            form = request.form.to_dict()
            clean, errors = catalog.validate_property(form)
            if not errors:
                catalog.update_property(conn, property_id, clean)
                flash(f'Изменения объекта №{property_id} сохранены', 'success')
                return redirect(url_for('objects_list'))
        return render_template('object_form.html', form=form, errors=errors,
                               districts=districts, owners=owners,
                               statuses=catalog.PROPERTY_STATUSES, action='edit',
                               title=f'Изменение объекта №{property_id}')
    finally:
        conn.close()


@app.route('/objects/<int:property_id>/delete', methods=['POST'])
@login_required
def objects_delete(property_id):
    conn = database.get_db()
    try:
        ok, message = catalog.delete_property(conn, property_id)
    finally:
        conn.close()
    flash(message, 'success' if ok else 'error')
    return redirect(url_for('objects_list'))


@app.route('/owners', methods=['GET', 'POST'])
@login_required
def owners_list():
    errors = {}
    conn = database.get_db()
    try:
        if request.method == 'POST':
            full_name = (request.form.get('full_name') or '').strip()
            phone = applications.normalize_phone(request.form.get('phone'))
            passport = (request.form.get('passport_data') or '').strip()
            egrn = (request.form.get('egrn_number') or '').strip()
            if len(full_name.split()) < 2:
                errors['full_name'] = 'Укажите ФИО полностью'
            if len(phone) != 11:
                errors['phone'] = 'Телефон: 11 цифр'
            if not passport:
                errors['passport_data'] = 'Укажите серию и номер паспорта'
            if not egrn:
                errors['egrn_number'] = 'Укажите номер ЕГРН'
            if not errors:
                catalog.create_owner(conn, full_name, phone, passport, egrn)
                flash('Собственник добавлен', 'success')
                return redirect(url_for('owners_list'))
        owners = [
            dict(o) | {'objects': conn.execute(
                'SELECT COUNT(*) AS n FROM properties WHERE owner_id = ?',
                (o['owner_id'],)).fetchone()['n']}
            for o in catalog.list_owners(conn)
        ]
    finally:
        conn.close()
    return render_template('owners.html', owners=owners, errors=errors,
                           form=request.form if request.method == 'POST' else {})


# ------------------------------------------------------------- вход риелтора

@app.route('/manage/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        login_name = (request.form.get('login') or '').strip()
        password = request.form.get('password') or ''
        attempts = [t for t in FAILED_LOGINS.get(login_name, [])
                    if datetime.datetime.now() - t < datetime.timedelta(minutes=LOCK_MINUTES)]
        FAILED_LOGINS[login_name] = attempts
        if len(attempts) >= MAX_FAILS:
            error = (f'Слишком много неудачных попыток входа. '
                     f'Повторите через {LOCK_MINUTES} минут.')
            flash('Вход временно заблокирован', 'error')
            return render_template('login.html', error=error,
                                   next_url=request.args.get('next', ''))
        conn = database.get_db()
        try:
            user = conn.execute('SELECT * FROM realtors WHERE login = ?',
                                (login_name,)).fetchone()
        finally:
            conn.close()
        if user and _check_password(user['password_hash'], password):
            session['manager'] = {'id': user['realtor_id'], 'name': user['full_name']}
            flash(f'Здравствуйте, {user["full_name"]}', 'success')
            next_url = request.args.get('next', '')
            if not next_url.startswith('/') or next_url.startswith('//'):
                next_url = url_for('manage_applications')
            FAILED_LOGINS.pop(login_name, None)
            return redirect(next_url)
        attempts.append(datetime.datetime.now())
        FAILED_LOGINS[login_name] = attempts
        left = MAX_FAILS - len(attempts)
        error = f'Неверный логин или пароль. Осталось попыток: {left}'
    return render_template('login.html', error=error, next_url=request.args.get('next', ''))


def _check_password(stored, password):
    """Пароль хранится как хеш werkzeug; старые записи — в открытом виде."""
    if stored and stored.startswith(('scrypt:', 'pbkdf2:')):
        return check_password_hash(stored, password)
    return stored == password


@app.route('/__reset_lock')
def _reset_lock_for_demo():
    """Сброс блокировки входа для демонстрации (только локальный запуск)."""
    FAILED_LOGINS.clear()
    return 'lock reset'


@app.route('/manage/logout', methods=['POST'])
def logout():
    session.pop('manager', None)
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))


@app.route('/manage/applications')
@login_required
def manage_applications():
    status_filter = (request.args.get('filter') or 'all')
    targets = applications.STATUS_FILTER.get(status_filter, 'all')
    phone = (request.args.get('phone') or '').strip()
    conn = database.get_db()
    try:
        rows = applications.search_applications(conn, phone=phone or None)
        if targets is not None:
            rows = [r for r in rows if r['status'] == targets]
        counts = {s: 0 for s in applications.STATUSES}
        for r in applications.search_applications(conn):
            counts[r['status']] = counts.get(r['status'], 0) + 1
    finally:
        conn.close()
    return render_template('manage_applications.html', rows=rows, filter=status_filter,
                           counts=counts, total=sum(counts.values()), phone=phone,
                           transitions=applications.STATUS_TRANSITIONS,
                           statuses=applications.STATUSES)


@app.route('/manage/applications/<int:application_id>/status', methods=['POST'])
@login_required
def manage_status(application_id):
    new_status = request.form.get('status') or ''
    conn = database.get_db()
    try:
        ok, message = applications.change_status(conn, application_id, new_status)
    finally:
        conn.close()
    flash(message, 'success' if ok else 'error')
    return redirect(url_for('manage_applications', filter=request.form.get('filter', 'all')))


@app.route('/manage/applications/<int:application_id>/delete', methods=['POST'])
@login_required
def manage_delete(application_id):
    conn = database.get_db()
    try:
        ok, message = applications.delete_application(conn, application_id)
    finally:
        conn.close()
    flash(message, 'success' if ok else 'error')
    return redirect(url_for('manage_applications'))


@app.route('/manage/applications/<int:application_id>')
@login_required
def manage_detail(application_id):
    conn = database.get_db()
    try:
        row = conn.execute('''
            SELECT a.*, t.full_name, t.phone, t.email, p.address_ufa, p.price_monthly,
                   p.rooms_count, p.area_total, d.name AS district_name,
                   r.full_name AS realtor_name
            FROM applications a
            JOIN tenants t ON a.tenant_id = t.tenant_id
            LEFT JOIN properties p ON a.property_id = p.property_id
            LEFT JOIN districts d ON p.district_id = d.district_id
            LEFT JOIN realtors r ON a.realtor_id = r.realtor_id
            WHERE a.application_id = ?
        ''', (application_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        flash('Заявка не найдена', 'error')
        return redirect(url_for('manage_applications'))
    return render_template('application_detail.html', app_row=row,
                           transitions=applications.STATUS_TRANSITIONS)


@app.errorhandler(404)
def not_found(_e):
    return render_template('error.html', code=404,
                           text='Страница не найдена'), 404


@app.errorhandler(500)
def server_error(_e):
    return render_template('error.html', code=500,
                           text='Внутренняя ошибка приложения'), 500


if __name__ == '__main__':
    database.init_db()
    database.migrate_db()
    # Сеть: доступ с телефона по адресу Мака, локально — http://127.0.0.1:5000/
    app.run(host='0.0.0.0', debug=True, port=8090)
