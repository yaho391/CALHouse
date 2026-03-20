# CALHouse / Система управления умным домом

В проекте реализована рабочая связка C# backend + Flet UI (`CALHouse_Test.py`) для управления устройствами:

1. `GET /api/devices` — получить список устройств.
2. `GET /api/devices/{id}` — получить устройство по ID.
3. `POST /api/devices` — добавить устройство.
4. `PUT /api/devices/{id}/toggle` — переключить устройство ON/OFF.
5. `DELETE /api/devices/{id}` — удалить устройство.


## Новые функции (готово в C# и Python backend)

Реализованы полностью рабочие функции:

- **Комнаты и зоны**: CRUD комнат, назначение устройства в комнату, список устройств в комнате.
- **Сценарии (сцены)**: CRUD сценариев, ручной запуск сцены, журнал выполнений со статусом.

### Дополнительные endpoints

- `GET /api/rooms`
- `GET /api/rooms/{id}`
- `POST /api/rooms`
- `PUT /api/rooms/{id}`
- `DELETE /api/rooms/{id}`
- `GET /api/rooms/{id}/devices`
- `PUT /api/devices/{id}/room`
- `GET /api/scenes`
- `GET /api/scenes/{id}`
- `POST /api/scenes`
- `PUT /api/scenes/{id}`
- `DELETE /api/scenes/{id}`
- `POST /api/scenes/{id}/run`
- `GET /api/scenes/executions`

### Запуск Python backend (FastAPI)

```bash
cd python_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

После запуска доступны маршруты и swagger:
- `http://localhost:8000/docs`

## Структура

- `backend/CalHouse.Api` — ASP.NET Core Minimal API
- `CALHouse_Test.py` — интерфейс на Flet, подключенный к API

## Требования

- .NET SDK 8.0+
- Python 3.10+
- pip

## Запуск backend

```bash
cd backend/CalHouse.Api
dotnet restore
dotnet run --urls "http://localhost:5000"
```

После запуска доступны маршруты:

- `GET /` -> `CalHouse API is running`
- `GET /api/devices`
- `GET /api/devices/{id}`
- `POST /api/devices`
- `PUT /api/devices/{id}/toggle`
- `DELETE /api/devices/{id}`
- `GET /swagger` (только в Development)

API запускается на `http://localhost:5000`.

## Запуск frontend

Рекомендуется запускать UI в отдельном виртуальном окружении Python:

```bash
cd "/home/glavniy/Рабочий стол/CALHouse-main"
python3 -m venv .venv
source .venv/bin/activate
pip install "flet==0.80.5" requests
python CALHouse_Test.py
```

Альтернативно (без venv):

```bash
pip install "flet==0.80.5" requests
python CALHouse_Test.py
```

В UI используется:

- `API_BASE = "http://localhost:5000"`
- Требуемая версия Flet: `0.80.5`

## Проверка API (Windows PowerShell)

В PowerShell `curl` — это alias для `Invoke-WebRequest`, поэтому ключи как в Linux (`-X`) часто не работают ожидаемо.

Используйте один из вариантов ниже.

### Вариант 1: Invoke-RestMethod

```powershell
Invoke-RestMethod -Method GET -Uri http://localhost:5000/api/devices
Invoke-RestMethod -Method GET -Uri http://localhost:5000/api/devices/1
Invoke-RestMethod -Method POST -Uri http://localhost:5000/api/devices -ContentType "application/json" -Body '{"name":"Лампа IKEA","room":"Спальня","isOn":false}'
Invoke-RestMethod -Method PUT -Uri http://localhost:5000/api/devices/1/toggle
Invoke-RestMethod -Method DELETE -Uri http://localhost:5000/api/devices/1
```

### Вариант 2: настоящий curl

```powershell
curl.exe -X GET http://localhost:5000/api/devices
curl.exe -X GET http://localhost:5000/api/devices/1
curl.exe -X POST http://localhost:5000/api/devices -H "Content-Type: application/json" -d "{\"name\":\"Лампа IKEA\",\"room\":\"Спальня\",\"isOn\":false}"
curl.exe -X PUT http://localhost:5000/api/devices/1/toggle
curl.exe -X DELETE http://localhost:5000/api/devices/1
```

Пример ответа `GET /api/devices`:

```json
[
  {
    "id": 1,
    "name": "Термостат",
    "room": "Гостиная",
    "isOn": false
  }
]
```

Пример ответа `PUT /api/devices/1/toggle`:

```json
{
  "id": 1,
  "name": "Термостат",
  "room": "Гостиная",
  "isOn": true
}
```

Пример запроса `POST /api/devices`:

```json
{
  "name": "Лампа IKEA",
  "room": "Спальня",
  "isOn": false
}
```

Пример ответа `POST /api/devices` (`201 Created`):

```json
{
  "id": 4,
  "name": "Лампа IKEA",
  "room": "Спальня",
  "isOn": false
}
```

Пример ответа ошибки валидации (`400 Bad Request`):

```json
{
  "message": "Name and room are required"
}
```


## Типовые ошибки и что делать

1. **404 на `http://localhost:5000/`**
   - Если backend запущен из старой сборки, перезапустите его из папки `backend/CalHouse.Api`.
   - Проверьте в логах строку `Now listening on: http://localhost:5000`.

2. **404 на `http://localhost:5000/swagger`**
   - Swagger доступен только в окружении `Development` (`ASPNETCORE_ENVIRONMENT=Development`).
   - В `launchSettings.json` это уже настроено.

3. **`python ... can't open file C:\Windows\System32\CALHouse_Test.py`**
   - Вы запускали Python не из папки проекта.
   - Перейдите в каталог репозитория перед запуском:

```powershell
cd C:\path\to\CALHouse
python CALHouse_Test.py
```

4. **`curl -X` в PowerShell не работает как в Linux**
   - Используйте `Invoke-RestMethod` или `curl.exe`, а не alias `curl`.

5. **Кнопка “Добавить устройство” нажимается, но на backend нет `POST /api/devices`**
   - Это обычно категория **UI-логика/сценарий**, а не backend URL:
     1) форма добавления не открылась,
     2) форма открылась, но не нажали "Сохранить",
     3) поля `Название` или `Комната` пустые (валидация не отправляет POST),
     4) запущена старая копия UI из другой папки,
     5) backend недоступен по `API_BASE`.
   - Как должно быть:
     - клик "Добавить устройство" -> в консоли UI: `[CALHouse UI] Add device button clicked` + `Add device form opened`;
     - клик "Сохранить" -> `[CALHouse UI] Add device form: save clicked` + `POST http://localhost:5000/api/devices`;
     - на backend появляется `Request starting HTTP/1.1 POST http://localhost:5000/api/devices`.
   - Если в backend видны только `GET /api/devices`, значит запрос на создание не дошёл до этапа "Сохранить" или был заблокирован валидацией.

6. **Слишком много `GET /api/devices` в логах backend**
   - Это категория **частые перерисовки UI**. В текущей версии убран лишний глобальный авто-refresh из `build_root()`, чтобы уменьшить поток GET.
   - Для ручного обновления используйте кнопку "Обновить".

7. **Установился `flet 0.81.x`, и UI ведёт себя не так, как ожидается**
   - В проекте зафиксирована целевая версия `flet==0.80.5`.
   - Проверьте версию:

```bash
python -c "import flet; print(flet.__version__)"
```

   - Если версия не `0.80.5`, переустановите в активированном venv:

```bash
pip uninstall -y flet flet-desktop-light
pip install "flet==0.80.5" requests
```
