# tg-exporter

Ежедневная выгрузка сообщений из всех чатов Telegram за сутки в JSON, для нескольких аккаунтов.

## Установка

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env` и впишите `API_ID` и `API_HASH` (https://my.telegram.org → API development tools) и имена аккаунтов: `ACCOUNTS=work1,work2`.

## Запуск

```bash
python export.py --login work1          # вход, один раз на каждый аккаунт
python export.py                        # выгрузить вчерашний день по всем аккаунтам
python export.py --account work1        # только один аккаунт
python export.py --date 2026-10-01      # конкретный день
```

Результат: `exports/<аккаунт>/<дата>.json`.

## Автозапуск (systemd)

Каждый день в 00:30; если компьютер был выключен, выгрузка выполнится после включения.

```bash
mkdir -p ~/.config/systemd/user
cp systemd/tg-export.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now tg-export.timer
loginctl enable-linger $USER   # работать, даже когда вы не вошли в систему
```

Проверка:

```bash
systemctl --user list-timers               # когда следующий запуск
systemctl --user start tg-export.service   # запустить сейчас
journalctl --user -u tg-export             # журнал
```

Не публикуйте `.env` и `sessions/`: файл сессии даёт полный доступ к аккаунту.
