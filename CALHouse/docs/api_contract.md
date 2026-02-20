# SmartHome (CALHouse) — API контракт (MVP)

Этот документ — **договор** между двумя частями проекта:

- **Backend (C# Web API)**: хранит данные, меняет состояния устройств, пишет логи.
- **UI (Python)**: показывает экраны и отправляет команды в backend.

Пока **авторизация — заглушка** (не используем токены). Позже добавим `/auth/login`.

---

## 0) Общие правила

**Base URL:** `http://localhost:5000/api`  
**Формат:** JSON (`application/json`)  
**Время:** ISO 8601 (например: `2026-01-30T12:00:00Z`)

### Ошибки (единый формат)
Backend возвращает ошибки так:

```json
{ "error": "text", "code": "SOME_CODE" }
```

Рекомендуемые HTTP-коды:
- `200 OK` — успешный ответ
- `201 Created` — создано
- `204 No Content` — удалено/без тела
- `400 Bad Request` — неверные данные
- `404 Not Found` — не найдено
- `409 Conflict` — конфликт (например, комнату нельзя удалить, если в ней есть устройства)
- `500 Internal Server Error` — ошибка сервера

---

## 1) Rooms (Комнаты)

### 1.1 Получить список комнат
`GET /rooms`

**Response 200**
```json
[
  { "id": 1, "name": "Гостиная" },
  { "id": 2, "name": "Спальня" }
]
```

### 1.2 Создать комнату
`POST /rooms`

**Request**
```json
{ "name": "Кухня" }
```

**Response 201**
```json
{ "id": 3, "name": "Кухня" }
```

### 1.3 Переименовать комнату
`PUT /rooms/{roomId}`

**Request**
```json
{ "name": "Кухня (1 этаж)" }
```

**Response 200**
```json
{ "id": 3, "name": "Кухня (1 этаж)" }
```

### 1.4 Удалить комнату
`DELETE /rooms/{roomId}`

**Response 204** (тело пустое)

**Response 409** (если в комнате есть устройства)
```json
{ "error": "Room has devices", "code": "ROOM_NOT_EMPTY" }
```

---

## 2) Devices (Устройства)

### 2.1 Получить список устройств (с фильтром по комнате)
`GET /devices?roomId=1`

**Response 200**
```json
[
  {
    "id": 10,
    "roomId": 1,
    "name": "Люстра",
    "type": "light",
    "protocol": "emulator",
    "address": "home/living/light1",
    "isOnline": true,
    "state": { "power": true, "brightness": 70 },
    "updatedAt": "2026-01-30T12:00:00Z"
  }
]
```

> `state` — универсальный JSON. Для лампы: `power/brightness`, для термостата: `temperature/mode` и т.д.

### 2.2 Создать устройство
`POST /devices`

**Request**
```json
{
  "roomId": 1,
  "name": "Розетка TV",
  "type": "socket",
  "protocol": "mqtt",
  "address": "home/living/socket_tv"
}
```

**Response 201**
```json
{
  "id": 11,
  "roomId": 1,
  "name": "Розетка TV",
  "type": "socket",
  "protocol": "mqtt",
  "address": "home/living/socket_tv",
  "isOnline": false,
  "state": { "power": false },
  "updatedAt": "2026-01-30T12:00:00Z"
}
```

### 2.3 Обновить устройство (имя/комната/адрес)
`PUT /devices/{deviceId}`

**Request**
```json
{ "name": "TV Socket", "roomId": 2, "address": "home/bed/socket_tv" }
```

**Response 200**
```json
{
  "id": 11,
  "roomId": 2,
  "name": "TV Socket",
  "type": "socket",
  "protocol": "mqtt",
  "address": "home/bed/socket_tv",
  "isOnline": false,
  "state": { "power": false },
  "updatedAt": "2026-01-30T12:10:00Z"
}
```

### 2.4 Удалить устройство
`DELETE /devices/{deviceId}`

**Response 204**

### 2.5 Toggle (переключить power) — MVP
`POST /devices/{deviceId}/toggle`

**Response 200**
```json
{
  "id": 10,
  "state": { "power": false, "brightness": 70 },
  "updatedAt": "2026-01-30T12:01:00Z"
}
```

### 2.6 Установить состояние (универсально)
`POST /devices/{deviceId}/state`

**Request**
```json
{ "power": true, "brightness": 40 }
```

**Response 200**
```json
{
  "id": 10,
  "state": { "power": true, "brightness": 40 },
  "updatedAt": "2026-01-30T12:02:00Z"
}
```

---

## 3) Logs (Журнал событий)

### 3.1 Получить логи
`GET /logs?severity=info&limit=50`

**Response 200**
```json
[
  {
    "id": 500,
    "ts": "2026-01-30T12:02:10Z",
    "severity": "info",
    "source": "ui",
    "eventType": "DEVICE_STATE_CHANGED",
    "message": "User toggled device",
    "userId": null,
    "deviceId": 10
  }
]
```

> Пока `userId` может быть `null` (потому что auth заглушка). Позже подставим реального пользователя.

---

## 4) Auth (пока заглушка — НЕ делаем)

Когда дойдёшь до авторизации, добавим:

- `POST /auth/login` → вернёт `token`
- все остальные запросы будут требовать заголовок:  
  `Authorization: Bearer <token>`

---

## 5) Как использовать этот контракт (для новичка)

### Что ты делаешь первым
1. **Делаешь backend (C#)** так, чтобы эндпоинты из этого документа реально работали.  
2. Проверяешь их через **Swagger** или **curl**.  
3. Только потом подключаешь **Python UI**, который вызывает эти URL.

### Мини-проверка через браузер/Swagger
- Запусти backend: `dotnet run`
- Открой Swagger: `http://localhost:5000/swagger`
- Попробуй:
  - `GET /api/rooms`
  - `POST /api/rooms` (создать)
  - `GET /api/devices?roomId=1`
  - `POST /api/devices/{id}/toggle`
  - `GET /api/logs?limit=50`

### Мини-проверка через curl (если надо)
```bash
curl -s http://localhost:5000/api/rooms
```

---

## 6) MVP-цель (минимум, который должен заработать)

Считай, что MVP готов, когда ты можешь:

- Создать комнату
- Добавить устройство в комнату
- Нажать Toggle (устройство меняет `power`)
- Увидеть запись в логах о действии

