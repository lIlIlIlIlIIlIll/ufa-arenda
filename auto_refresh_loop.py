"""Просмотрщик базы «ИС Аренда» (local).

Каждые 2 секунды обновляет data.json и data.js, сервер отдаёт dbviewer.html,
браузер открывается автоматически. Остановить: Ctrl+C в терминале или
закрыть процесс python auto_refresh_loop.py.
"""
import http.server
import os
import socketserver
import threading
import time
import webbrowser

import refresh_db

OS_BROWSER = os.environ.get('ARENDA_NO_BROWSER') != '1'


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def log_message(self, *args):
        pass


def writer():
    import json
    while True:
        try:
            refresh_db.export()
            data = json.load(open(refresh_db.OUT, encoding='utf-8'))
            with open(os.path.join(refresh_db.BASE, 'data.js'), 'w', encoding='utf-8') as f:
                f.write('window.ARENDA_DATA = ' + json.dumps(data, ensure_ascii=False, indent=1) + ';\n')
        except Exception as e:  # база занята — попробуем ещё раз
            print('refresh:', e)
        time.sleep(2)


def main():
    os.chdir(refresh_db.BASE)
    refresh_db.export()
    threading.Thread(target=writer, daemon=True).start()
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 5099), Handler)
    print('Просмотр базы: http://127.0.0.1:5099/dbviewer.html')
    if OS_BROWSER:
        threading.Timer(1.0, lambda: webbrowser.open('http://127.0.0.1:5099/dbviewer.html')).start()
    srv.serve_forever()


if __name__ == '__main__':
    main()
