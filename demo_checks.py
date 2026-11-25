"""Проверка модуля на нескольких примерах (задания 2–4).

Скрипт работает с копией базы в памяти и с тестовым клиентом Flask:
база приложения не изменяется, поэтому проверку можно повторять.
Использование:  python demo_checks.py
"""
import datetime
import sqlite3

import applications
import app as app_module
import catalog
import db

PASS, FAIL = 'OK  ', 'FAIL'


def fresh_db():
    """Создать базу во временном файле и вернуть соединение."""
    import os
    import tempfile
    path = os.path.join(tempfile.mkdtemp(prefix='arenda_test_'), 'test.db')
    db.DB_PATH = path
    db.init_db()
    db.migrate_db()
    return db.get_db(), path


def main():
    conn, path = fresh_db()
    results = []

    def check(title, condition, detail=''):
        results.append((PASS if condition else FAIL, title, detail))

    # --- 1. Подключение и схема
    tables = [r['name'] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    check('База создаётся и содержит таблицы', 'applications' in tables and 'saved_searches' in tables,
          ', '.join(tables))

    # --- 2. Каталог и фильтр
    all_objects = applications.list_active_properties(conn)
    kirovsky = applications.list_active_properties(conn, district_id=1)
    check('Каталог: вывод активных объектов', len(all_objects) == 2, f'{len(all_objects)} объекта')
    check('Фильтр по району возвращает 1 объект', len(kirovsky) == 1,
          kirovsky[0]['address_ufa'] if kirovsky else '—')

    # --- 3. Валидация
    _, errs = applications.validate_application({
        'property_id': '1', 'full_name': 'Иван', 'phone': '12345',
        'desired_district': '', 'email': 'mail'})
    check('Валидация находит 4 ошибки в неполной форме', len(errs) == 4, ', '.join(errs))

    clean, errs = applications.validate_application({
        'property_id': '1', 'full_name': '  Ахметова   Лилия ',
        'phone': '+7 (917) 555-44-22', 'email': 'li@mail.ru',
        'desired_district': 'Кировский район', 'comment': 'Нужен дом с лифтом'})
    check('Корректные данные проходят проверку и нормализуются', not errs and clean['phone'] == '79175554422',
          f"телефон {clean['phone']}, ФИО «{clean['full_name']}»")

    # --- 4. Сохранение заявки
    realtor = applications.pick_realtor(conn, 1)
    res = applications.create_application(conn, clean, realtor)
    row = conn.execute('SELECT * FROM applications WHERE application_id = ?',
                       (res['application_id'],)).fetchone()
    check('Заявка сохраняется в applications', row is not None and row['status'] == 'Новая',
          f"№{row['application_num']}, property_id={row['property_id']}")
    check('Арендатор сохраняется в tenants', res['tenant_created'] is True,
          f"tenant_id={res['tenant_id']}")
    check('Номер заявки читаемый', res['application_num'] == f'ЗАЯ-{datetime.date.today().year}-0001',
          res['application_num'])

    # --- 5. Нумерация и повторный арендатор
    clean2 = dict(clean, property_id='2', desired_district='Октябрьский район')
    res2 = applications.create_application(conn, clean2, realtor)
    check('Вторая заявка получает следующий номер', res2['application_num'].endswith('-0002'),
          res2['application_num'])
    check('Повторный арендатор не дублируется', res2['tenant_id'] == res['tenant_id']
          and conn.execute('SELECT COUNT(*) AS n FROM tenants').fetchone()['n'] == 1,
          f"tenant_id={res2['tenant_id']}")

    # --- 6. Защита от повтора
    dup = applications.find_recent_duplicate(conn, clean2['phone'], 2)
    check('Обнаружен повтор заявки за 10 минут', dup == res2['application_num'], dup or '—')

    # --- 7. Поиск
    found = applications.search_applications(conn, phone='5554422')
    check('Поиск заявок по телефону', len(found) == 2, f'{len(found)} заявки')

    # --- 8. Изменение статуса
    ok, msg = applications.change_status(conn, res['application_id'], 'В работе')
    ok2, msg2 = applications.change_status(conn, res['application_id'], 'Закрыта')
    status = conn.execute('SELECT status FROM applications WHERE application_id = ?',
                          (res['application_id'],)).fetchone()['status']
    check('Разрешённый переход статуса выполняется', ok and status == 'В работе', msg)
    check('Запрещённый переход отклоняется', not ok2, msg2)

    # --- 9. CRUD объектов
    clean_prop, perr = catalog.validate_property({
        'address_ufa': 'г. Уфа, ул. Коммунистическая, д. 15', 'district_id': '1', 'owner_id': '1',
        'rooms_count': '1', 'area_total': '36,5', 'floor_info': '3/5', 'price_monthly': '30000',
        'status': 'Активен', 'description': '1-к квартира рядом с Гостиным двором'})
    new_id = catalog.create_property(conn, clean_prop)
    created = catalog.get_property(conn, new_id)
    check('Добавление объекта', created is not None and float(created['area_total']) == 36.5,
          f'id={new_id}, площадь {created["area_total"]}')

    upd = dict(clean_prop, price_monthly='28000', status='Сдан')
    catalog.update_property(conn, new_id, upd)
    after = catalog.get_property(conn, new_id)
    check('Изменение объекта', after['price_monthly'] == 28000 and after['status'] == 'Сдан',
          f"{after['price_monthly']} ₽, {after['status']}")

    reserved = catalog.delete_property(conn, 1)
    check('Удаление связанного объекта запрещено', reserved[0] is False, reserved[1])

    deleted = catalog.delete_property(conn, new_id)
    check('Удаление свободного объекта', deleted[0] and catalog.get_property(conn, new_id) is None,
          deleted[1])

    bad, berr = catalog.validate_property({'address_ufa': 'Уфа', 'district_id': '', 'owner_id': '',
                                           'rooms_count': '0', 'area_total': 'abc',
                                           'floor_info': 'этаж', 'price_monthly': '1'})
    check('Валидация объекта находит ошибки', len(berr) >= 6, ', '.join(berr))

    # --- 10. Сохранённые поиски
    sid = catalog.save_search(conn, '2-комн. до 30 000', 3, 2, 30000)
    saved = catalog.list_saved_searches(conn)
    catalog.delete_saved_search(conn, sid)
    check('Сохранение и удаление поиска', len(saved) == 1 and not catalog.list_saved_searches(conn),
          f'{len(saved)} запись')

    # --- 11. HTTP-сценарии через тестовый клиент
    app_module.app.config['TESTING'] = True
    client = app_module.app.test_client()
    page = client.get('/')
    check('Страница каталога отдаёт 200 и содержит объект', page.status_code == 200
          and 'ул. Ленина' in page.get_data(as_text=True), f'HTTP {page.status_code}')

    post = client.post('/apply', data={
        'property_id': '2', 'full_name': 'Тестов Тест', 'phone': '+79170000000',
        'email': 'test@mail.ru', 'desired_district': 'Кировский район', 'comment': 'тест'})
    check('POST /apply перенаправляет на подтверждение', post.status_code == 302
          and '/apply/success/' in post.headers['Location'], post.headers.get('Location', ''))

    bad_post = client.post('/apply', data={'property_id': '2', 'full_name': 'X', 'phone': '1'})
    check('Ошибочная форма возвращает 400 и сообщения', bad_post.status_code == 400
          and 'Укажите фамилию и имя' in bad_post.get_data(as_text=True), f'HTTP {bad_post.status_code}')

    login = client.post('/manage/login', data={'login': 'kapustin', 'password': 'ufa2026'})
    manage = client.get('/manage/applications')
    check('Вход риелтора и доступ к заявкам', login.status_code == 302 and manage.status_code == 200,
          f'HTTP {manage.status_code}')

    no_auth = app_module.app.test_client().get('/manage/applications')
    check('Без входа кабинет недоступен (редирект)', no_auth.status_code == 302, f'HTTP {no_auth.status_code}')

    # --- итог
    width = max(len(r[1]) for r in results)
    for status, title, detail in results:
        print(f'{status} {title:<{width}}  {detail}')
    failed = sum(1 for r in results if r[0] == FAIL)
    print(f'\nВсего проверок: {len(results)}, пройдено: {len(results) - failed}, не пройдено: {failed}')
    conn.close()


if __name__ == '__main__':
    main()
