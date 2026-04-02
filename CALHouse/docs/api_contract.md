# CALHouse / Система управления умным домом

В проекте теперь есть полноценная связка:

- **backend**: `backend/CalHouse.Api` — ASP.NET Core Minimal API (`net8.0`)
- **frontend**: `CALHouse_Test.py` — рабочий интерфейс на **Flet 0.80.5**
- **хранилище**: локальная **SQLite** БД `backend/CalHouse.Api/App_Data/calhouse.db`
- **совместимость**: файл `backend/CalHouse.Api/App_Data/devices.json` сохраняется и автоматически синхронизируется как legacy-слой

Также в архив добавлена папка `legacy_snapshots/` с копиями исходных ключевых файлов до расширения проекта.

---

## Что реализовано

### Устройства
- `GET /api/devices`
- `GET /api/devices/{id}`
- `POST /api/devices`
- `PUT /api/devices/{id}`
- `PUT /api/devices/{id}/toggle`
- `PUT /api/devices/{id}/room`
- `DELETE /api/devices/{id}`
- `POST /api/devices/validate-connection`

### Комнаты и зоны
- `GET /api/rooms`
- `GET /api/rooms/{id}`
- `GET /api/rooms/{id}/devices`
- `POST /api/rooms`
- `PUT /api/rooms/{id}`
- `DELETE /api/rooms/{id}`

### Сценарии (сцены)
- `GET /api/scenes`
- `GET /api/scenes/{id}`
- `GET /api/scenes/{id}/runs`
- `POST /api/scenes`
- `PUT /api/scenes/{id}`
- `DELETE /api/scenes/{id}`
- `POST /api/scenes/{id}/run`

### Логи
- `GET /api/logs?limit=50`

---

## Как работает хранение данных

Вместо тестового JSON-only слоя backend теперь использует локальную SQLite БД.

Таблицы:
- `Rooms`
- `Devices`
- `Scenes`
- `SceneActions`
- `SceneRuns`
- `EventLogs`

При первом запуске backend автоматически:
1. создаёт `calhouse.db`,
2. переносит стартовые устройства из старого `devices.json`,
3. дальше работает уже через SQLite.

После операций с устройствами legacy-файл `devices.json` автоматически обновляется, чтобы совместимость с предыдущей структурой не потерялась.

---

## Требования

- **.NET SDK 8.0+**
- **Python 3.10+**
- `pip`

---

## Запуск backend

```bash
cd backend/CalHouse.Api
dotnet restore
dotnet run --urls "http://localhost:5000"
```

После запуска доступны:
- `GET /`
- `GET /swagger` (в Development)
- все маршруты из `/api/...`

---

## Запуск frontend

```bash
pip install "flet==0.80.5" requests
python CALHouse_Test.py
```

Или через виртуальное окружение:

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install "flet==0.80.5" requests
python CALHouse_Test.py
```

В UI доступны вкладки:
- Главная
- Устройства
- Комнаты
- Сценарии
- История
- Настройки

---

## Примеры запросов

### Создать комнату
```json
POST /api/rooms
{
  "name": "Спальня",
  "zone": "Второй этаж"
}
```

### Создать устройство
```json
POST /api/devices
{
  "name": "Лампа у кровати",
  "room": "Спальня",
  "isOn": false,
  "type": "Свет",
  "provider": "mock",
  "connection": {}
}
```

### Перенести устройство в другую комнату
```json
PUT /api/devices/5/room
{
  "roomId": 2
}
```

### Создать сцену
```json
POST /api/scenes
{
  "name": "Уйти из дома",
  "description": "Выключить свет и включить охранные устройства",
  "actions": [
    { "deviceId": 1, "targetIsOn": false, "sortOrder": 1 },
    { "deviceId": 3, "targetIsOn": true, "sortOrder": 2 }
  ]
}
```

### Запустить сцену
```bash
curl -X POST http://localhost:5000/api/scenes/1/run
```

---

## Поведение ошибок

Backend возвращает ошибки в формате:

```json
{
  "error": "Текст ошибки",
  "code": "ERROR_CODE",
  "message": "Текст ошибки"
}
```

Примеры:
- `ROOM_NOT_EMPTY`
- `ROOM_NOT_FOUND`
- `DEVICE_NOT_FOUND`
- `SCENE_NOT_FOUND`
- `SCENE_ACTIONS_REQUIRED`
- `SCENE_NAME_EXISTS`

---

## Что важно для отчёта / демонстрации

1. Комнаты теперь создаются и редактируются отдельно.
2. Устройства можно перепривязывать между комнатами.
3. Сцены сохраняются в БД и запускаются вручную.
4. Выполнение сцен логируется.
5. История доступна через `GET /api/logs` и показывается в Flet UI.
