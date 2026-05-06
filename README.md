# Smile Record

Mobile-first Flask-проект для реєстратури стоматології Smile.

## Сторінки

- `/` або `/schedule` - графік записів із виділенням сьогоднішнього дня.
- `/patients` - база пацієнтів.
- `/doctors` - база лікарів із додаванням і редагуванням.

## Структура

```text
app/
  static/js/app.js
  templates/
    base.html
    schedule.html
    patients.html
    doctors.html
    _modals.html
  __init__.py
  routes.py
  storage.py
data/
  smile.json
run.py
requirements.txt
```

Дані зберігаються у JSON-файлі `data/smile.json` через TinyDB.

## Запуск

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Після запуску сайт буде доступний за адресою `http://127.0.0.1:5000`.
