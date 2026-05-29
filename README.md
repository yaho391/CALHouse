# CALHouse / Система управления умным домом
# C - Calm
# A - Adaptive
# L - Live
Проект состоит из двух основных частей:

- **backend**: `backend/CalHouse.Api` — ASP.NET Core Minimal API (`net8.0`)
- **frontend**: `CALHouse_Test.py` — интерфейс на **Flet 0.80.5**

Хранилище данных:

- **SQLite**: `backend/CalHouse.Api/App_Data/calhouse.db`
- **legacy JSON**: `backend/CalHouse.Api/App_Data/devices.json` синхронизируется автоматически

## Что теперь реализовано

### 1. Подключение устройств
Поддерживается полноценное добавление устройств с параметрами:

- название
- уникальный `externalId`
- тип устройства
- provider
- протокол
- канал
- привязка к комнате
- производитель / модель
- connection-параметры

При создании и обновлении устройства backend:

- проверяет уникальность идентификатора
- валидирует обязательные connection-поля
- выполняет тест связи
- сохраняет статус подключения: `connected` / `no_connection` / `unknown`

Подготовлены provider-модели для реальных устройств и интеграций:

- `Shelly`
- `Tasmota`
- `MQTT`
- `Zigbee2MQTT`
- `Home Assistant entity`
- `IP Camera`
- `Custom HTTP`
- `Custom TCP`
- `mock`

### 2. Автоматизация по событиям
Добавлены правила вида:

- если событие датчика подходит под условие,
- то выполняется действие над устройством **или** запускается сценарий

Поддерживается:

- хранение правил в БД
- включение / выключение правил
- приём событий через API
- автоматическая проверка условий
- журналирование срабатываний
- история запусков правил

### 3. Расписание
Добавлено расписание по времени:

- запуск по `HH:mm`
- выбор дней недели
- действие над устройством **или** запуск сценария
- логирование запусков
- история выполнения
- фоновая проверка расписаний через hosted service

## Основные эндпоины

### Каталог и устройства
- `GET /api/device-catalog`
- `GET /api/devices`
- `GET /api/devices/{id}`
- `POST /api/devices`
- `PUT /api/devices/{id}`
- `PUT /api/devices/{id}/toggle`
- `PUT /api/devices/{id}/room`
- `DELETE /api/devices/{id}`
- `POST /api/devices/validate-connection`
- `POST /api/events`

### Комнаты
- `GET /api/rooms`
- `GET /api/rooms/{id}`
- `GET /api/rooms/{id}/devices`
- `POST /api/rooms`
- `PUT /api/rooms/{id}`
- `DELETE /api/rooms/{id}`

### Сценарии
- `GET /api/scenes`
- `GET /api/scenes/{id}`
- `GET /api/scenes/{id}/runs`
- `POST /api/scenes`
- `PUT /api/scenes/{id}`
- `DELETE /api/scenes/{id}`
- `POST /api/scenes/{id}/run`

### Правила
- `GET /api/rules`
- `GET /api/rules/{id}`
- `GET /api/rules/{id}/runs`
- `POST /api/rules`
- `PUT /api/rules/{id}`
- `PUT /api/rules/{id}/enabled`
- `DELETE /api/rules/{id}`

### Расписание
- `GET /api/schedules`
- `GET /api/schedules/{id}`
- `GET /api/schedules/{id}/runs`
- `POST /api/schedules`
- `PUT /api/schedules/{id}`
- `PUT /api/schedules/{id}/enabled`
- `POST /api/schedules/run-due`
- `DELETE /api/schedules/{id}`

### Логи
- `GET /api/logs?limit=80`

## Запуск backend

```bash
cd backend/CalHouse.Api
dotnet restore
dotnet run --urls "http://localhost:5000"
```

## Запуск frontend

```bash
pip install "flet==0.80.5" requests
python CALHouse_Test.py
```

## Вкладки в Flet UI

- Главная
- Устройства
- Комнаты
- Сценарии
- Правила
- Расписание
- История
- Настройки

## Что важно для демонстрации

1. Добавить реальное устройство с `externalId` и тестом связи.
2. Показать карточку устройства со статусом подключения.
3. Создать правило и отправить событие через UI.
4. Показать, что правило выполнило действие или запустило сценарий.
5. Создать расписание и проверить запуск вручную через `Проверить сейчас`.
6. Открыть историю и показать соответствующие логи.
