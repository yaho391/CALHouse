# CALHouse / Система управления умным домом

В проекте реализованы 2 рабочие функции через C# backend + существующий Flet UI (`CALHouse_Test.py`):

1. `GET /api/devices` — получить список устройств.
2. `PUT /api/devices/{id}/toggle` — переключить устройство ON/OFF.

## Структура

- `backend/CalHouse.Api` — ASP.NET Core Minimal API
- `CALHouse_Test.py` — существующий интерфейс на Flet, подключенный к API

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

API запускается на `http://localhost:5000`.

## Запуск frontend

```bash
pip install flet requests
python CALHouse_Test.py
```

В UI используется:

- `API_BASE = "http://localhost:5000"`

## Проверка API через curl

```bash
curl -X GET http://localhost:5000/api/devices
curl -X PUT http://localhost:5000/api/devices/1/toggle
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
