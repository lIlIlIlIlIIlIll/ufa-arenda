#!/bin/bash
# Открывает phpLiteAdmin — админку базы ИС «Аренда» (как phpMyAdmin).
# Админка показывает копию базы сайта, которая обновляется автоматически
# каждые 2 секунды из ufa-arenda-app/ufa_arenda.db.
cd "$(dirname "$0")" || exit 1
PHP="/Applications/XAMPP/xamppfiles/bin/php"

start() { nohup "$1" > /tmp/pla_php.log 2>&1 & }

if ! lsof -ti tcp:5098 >/dev/null 2>&1; then
  start "$PHP -S 0.0.0.0:5098 -t ."
  sleep 1
fi
if ! pgrep -f "sync_db.sh" >/dev/null 2>&1; then
  nohup ./sync_db.sh > /tmp/sync_db.log 2>&1 &
fi
sleep 1
open "http://127.0.0.1:5098/pla/index.php"
echo "Открыто: http://127.0.0.1:5098/pla/index.php"
echo "Пароль: arenda"
echo "С телефона в той же сети: http://$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1):5098/pla/index.php"
read -r -p "Enter — закрыть окно" _
