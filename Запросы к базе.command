#!/bin/bash
# Разовые SQL-запросы к ufa_arenda.db (SQLite). Запуск двойным щелчком.
cd "$(dirname "$0")" || exit 1
echo "=== Заявки ==="
sqlite3 -header -column ufa_arenda.db "SELECT a.application_num AS Номер, t.full_name AS Арендатор, t.phone AS Телефон, p.address_ufa AS Объект, a.status AS Статус FROM applications a JOIN tenants t ON t.tenant_id=a.tenant_id LEFT JOIN properties p ON p.property_id=a.property_id ORDER BY a.application_id;"
echo
echo "=== Арендаторы ==="
sqlite3 -header -column ufa_arenda.db "SELECT tenant_id AS id, full_name AS ФИО, phone AS Телефон, email AS Почта FROM tenants ORDER BY tenant_id;"
echo
echo "=== Объекты ==="
sqlite3 -header -column ufa_arenda.db "SELECT property_id AS id, address_ufa AS Адрес, price_monthly AS Цена, status AS Статус FROM properties ORDER BY property_id;"
echo
echo "Нажмите Enter, чтобы закрыть."
read
