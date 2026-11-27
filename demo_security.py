"""Проверка элементов безопасности (задание 5) и работы системы (задание 6).

Работает с тестовым клиентом Flask и копией базы во временном каталоге,
рабочая база проекта не изменяется. Запуск: python demo_security.py
"""
import os
import re as _re
import tempfile

import app as app_module
import applications
import catalog
import db

PASS, FAIL = 'OK  ', 'FAIL'


def fresh_db():
    path = os.path.join(tempfile.mkdtemp(prefix='arenda_sec_'), 'test.db')
    db.DB_PATH = path
    db.init_db()
    db.migrate_db()
    return db.get_db(), path


def main():
    conn, path = fresh_db()
    app_module.app.config.update(TESTING=False)
    results = []

    def check(title, condition, detail=''):
        results.append((PASS if condition else FAIL, title, detail))

    # ---------------- проверка вводимых данных
    _, errs = applications.validate_application({
        'property_id': '', 'full_name': 'X', 'phone': 'abc',
        'email': 'mail', 'desired_district': ''})
    check('Заявка: пустые и неверные поля отклоняются', len(errs) == 5, ', '.join(errs))

    clean, errs = applications.validate_application({
        'property_id': '1', 'full_name': 'Петрова-Водкина Анна',
        'phone': '+7 (917) 555-44-22', 'desired_district': 'Кировский район'})
    check('Заявка: корректные данные проходят проверку', not errs, 'ошибок нет')

    _, errs = applications.validate_application({
        'property_id': '1', 'full_name': 'Иванов Иван',
        'phone': '+7 (917) 555-44-22', 'desired_district': 'Кировский район',
        'comment': 'а' * 501})
    check('Заявка: слишком длинный комментарий отклоняется',
          'comment' in errs, errs.get('comment', ''))

    _, errs = catalog.validate_property({'address_ufa': 'Уфа', 'district_id': '1',
                                         'owner_id': '1', 'rooms_count': '0',
                                         'area_total': '-5', 'floor_info': 'abc',
                                         'price_monthly': '0'})
    check('Объект: неверные числа и формат отклоняются', len(errs) >= 4, ', '.join(errs))

    # ---------------- защита от SQL-инъекций
    clean_inj, errs_inj = applications.validate_application({
        'property_id': '1', 'full_name': "Иванов Иван'; DROP TABLE tenants; --",
        'phone': '+7 (917) 555-44-22',
        'desired_district': 'Кировский); DROP TABLE applications; --'})
    check('SQL-инъекция во ФИО отклоняется валидацией',
          'full_name' in errs_inj, errs_inj.get('full_name', ''))

    client = app_module.app.test_client()
    page = client.get("/objects?q=' OR 1=1 --")
    check('SQL-инъекция в поиске не ломает запрос', page.status_code == 200,
          f'HTTP {page.status_code}')
    page = client.get("/applications?phone=' OR '1'='1")
    leaked = _re.search(r'ЗАЯ-\d{4}-\d{4}', page.get_data(as_text=True))
    check('SQL-инъекция в поиске заявок не раскрывает данные',
          page.status_code == 200 and not leaked,
          f'HTTP {page.status_code}, найдено заявок: {1 if leaked else 0}')

    # ---------------- защита доступа к функциям персонала
    for url, method in [('/objects/new', 'get'), ('/objects/1/edit', 'get'),
                        ('/owners', 'get'), ('/manage/applications', 'get'),
                        ('/objects/1/delete', 'post')]:
        resp = getattr(client, method)(url)
        check(f'Гость не получает доступ: {method.upper()} {url}',
              resp.status_code == 302 and '/manage/login' in resp.headers['Location'],
              f'HTTP {resp.status_code} → переадресация')

    # ---------------- вход и разграничение доступа
    resp = client.post('/manage/login', data={'login': 'kapustin', 'password': 'ufa2026'})
    check('Риелтор входит с верным паролем', resp.status_code == 302, resp.headers.get('Location', ''))
    check('Риелтор получает доступ к заявкам',
          client.get('/manage/applications').status_code == 200, 'HTTP 200')
    check('Риелтор получает доступ к управлению объектами',
          client.get('/objects/new').status_code == 200, 'HTTP 200')

    # ---------------- блокировка после серии неудачных попыток
    bad = app_module.app.test_client()
    last = None
    for _ in range(6):
        last = bad.post('/manage/login', data={'login': 'kapustin', 'password': 'wrong'})
    body = last.get_data(as_text=True)
    check('Подбор пароля блокируется после 5 попыток',
          'Слишком много неудачных попыток' in body, 'сообщение о блокировке')
    check('Заблокированный вход не открывает кабинет',
          bad.get('/manage/applications').status_code == 302, 'доступа нет')

    # ---------------- недопустимые действия
    app_module.FAILED_LOGINS.clear()   # блокировка не должна мешать следующему шагу
    ok_login = app_module.app.test_client()
    ok_login.post('/manage/login', data={'login': 'kapustin', 'password': 'ufa2026'})
    ok_login.post('/manage/logout')
    fresh = app_module.app.test_client()
    resp = fresh.post('/manage/login', data={'login': 'kapustin', 'password': 'ufa2026'})
    check('Повторный вход после выхода работает',
          resp.status_code == 302 and fresh.get('/manage/applications').status_code == 200,
          f'HTTP {resp.status_code}')

    conn = db.get_db()
    clean, _ = applications.validate_application({'property_id': '1', 'full_name': 'Петров Петр',
                                                  'phone': '+79175550011',
                                                  'desired_district': 'Кировский район'})
    res = applications.create_application(conn, clean, 1)
    ok, message = catalog.delete_property(conn, 1)
    check('Недопустимое действие: удаление объекта с заявками запрещено',
          not ok, message)

    ok, message = applications.change_status(conn, res['application_id'], 'Закрыта')
    check('Недопустимый переход статуса отклоняется', not ok, message)

    page = client.get('/applications?phone=5550011')
    check('Поиск заявки по номеру телефона работает',
          _re.search(r'ЗАЯ-\d{4}-\d{4}', page.get_data(as_text=True)) is not None,
          'заявка найдена')
    page = client.get('/applications?phone=5550012')
    check('Поиск заявки по чужому номеру ничего не находит',
          _re.search(r'ЗАЯ-\d{4}-\d{4}', page.get_data(as_text=True)) is None,
          'данные не раскрыты')

    resp = client.get('/apply/success/НЕ-СУЩЕСТВУЕТ-0000')
    check('Неверный номер заявки обрабатывается, а не даёт ошибку 500',
          resp.status_code == 302, f'HTTP {resp.status_code}')

    # ---------------- переадресация после входа
    app_module.FAILED_LOGINS.clear()
    redir = app_module.app.test_client()
    resp = redir.post('/manage/login?next=https://evil.example.com',
                      data={'login': 'kapustin', 'password': 'ufa2026'})
    location = resp.headers.get('Location', '') or redir.get('/manage/applications').request.path
    check('Переход на внешний адрес после входа заблокирован',
          'evil.example.com' not in location and redir.get('/manage/applications').status_code == 200,
          f'переход на: {location}')

    # ---------------- корректные данные на реальном сайте
    site = app_module.app.test_client()
    resp = site.get("/objects?q=' OR 1=1 --")
    check('Поиск объектов с SQL-инъекцией: страница открывается без ошибки',
          resp.status_code == 200 and 'Записи не найдены' in resp.get_data(as_text=True),
          'нет утечки данных')

    # ---------------- проверка работы модуля в составе проекта
    for url in ['/', '/property/1', '/apply?property_id=1', '/applications', '/objects']:
        resp = app_module.app.test_client().get(url)
        check(f'Страница работает: GET {url}', resp.status_code == 200, f'HTTP {resp.status_code}')

    width = max(len(r[1]) for r in results)
    for status, title, detail in results:
        print(f'{status} {title:<{width}}  {detail}')
    failed = sum(1 for r in results if r[0] == FAIL)
    print(f'\nВсего проверок: {len(results)}, пройдено: {len(results) - failed}, не пройдено: {failed}')
    conn.close()


if __name__ == '__main__':
    main()
