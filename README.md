# CALHouse / Система управления умным домом

В проекте реализованы 2 рабочие функции через C# backend + существующий Flet UI (`CALHouse_Test.py`):

1. `GET /api/devices` — получить список устройств.
2. `PUT /api/devices/{id}/toggle` — переключить устройство ON/OFF.

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
- `PUT /api/devices/{id}/toggle`
- `GET /swagger` (только в Development)

API запускается на `http://localhost:5000`.

## Запуск frontend

```bash
pip install flet requests
python CALHouse_Test.py
```

В UI используется:

- `API_BASE = "http://localhost:5000"`

## Проверка API (Windows PowerShell)

В PowerShell `curl` — это alias для `Invoke-WebRequest`, поэтому ключи как в Linux (`-X`) часто не работают ожидаемо.

Используйте один из вариантов ниже.

### Вариант 1: Invoke-RestMethod

```powershell
Invoke-RestMethod -Method GET -Uri http://localhost:5000/api/devices
Invoke-RestMethod -Method PUT -Uri http://localhost:5000/api/devices/1/toggle
```

### Вариант 2: настоящий curl

```powershell
curl.exe -X GET http://localhost:5000/api/devices
curl.exe -X PUT http://localhost:5000/api/devices/1/toggle
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
