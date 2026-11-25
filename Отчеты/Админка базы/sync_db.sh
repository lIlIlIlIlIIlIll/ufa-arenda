#!/bin/bash
# Раз в 2 секунды обновляет копию рабочей базы для админки (data/site.db)
# из базы сайта (ufa-arenda-app/ufa_arenda.db).
cd "$(dirname "$0")" || exit 1
mkdir -p data
while true; do
  if sqlite3 "../ufa-arenda-app/ufa_arenda.db" ".backup 'data/site.db.tmp'" 2>/dev/null; then
    mv -f data/site.db.tmp data/site.db
  fi
  sleep 2
done
