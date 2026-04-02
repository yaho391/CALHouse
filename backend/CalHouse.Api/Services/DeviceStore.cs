using System.Data;
using System.Globalization;
using System.Net.Http;
using System.Net.Sockets;
using System.Text.Json;
using CalHouse.Api.Infrastructure;
using CalHouse.Api.Models;
using Microsoft.Data.Sqlite;

namespace CalHouse.Api.Services;

public class DeviceStore
{
    private readonly string _databasePath;
    private readonly string _legacyDevicesPath;
    private readonly ILogger<DeviceStore> _logger;
    private readonly object _sync = new();
    private readonly JsonSerializerOptions _jsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
    };

    public DeviceStore(IWebHostEnvironment environment, ILogger<DeviceStore> logger)
    {
        _logger = logger;

        var appDataDirectory = Path.Combine(environment.ContentRootPath, "App_Data");
        Directory.CreateDirectory(appDataDirectory);

        _databasePath = Path.Combine(appDataDirectory, "calhouse.db");
        _legacyDevicesPath = Path.Combine(appDataDirectory, "devices.json");

        lock (_sync)
        {
            using var connection = OpenConnection();
            InitializeDatabase(connection);
            SeedIfNeeded(connection);
            SyncLegacyDevicesJson(connection);
        }
    }

    public IReadOnlyList<Device> GetAllDevices(int? roomId = null)
    {
        lock (_sync)
        {
            using var connection = OpenConnection();
            return ReadDevices(connection, roomId);
        }
    }

    public Device GetDevice(int id)
    {
        lock (_sync)
        {
            using var connection = OpenConnection();
            return ReadDeviceOrThrow(connection, id);
        }
    }

    public Device AddDevice(string name, string? roomName, int? roomId, bool isOn, string? type, string? provider, string? identifier, Dictionary<string, string>? connection)
    {
        var cleanName = NormalizeRequired(name, "Название устройства обязательно", "DEVICE_NAME_REQUIRED");
        var cleanType = NormalizeOptional(type, "Другое");
        var cleanProvider = NormalizeOptional(provider, "mock");
        var cleanIdentifier = NormalizeIdentifier(identifier);
        var connectionData = connection ?? new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureDeviceIdentifierIsUnique(db, cleanIdentifier, null);
            var validation = ValidateConnection(cleanProvider, connectionData);
            using var transaction = db.BeginTransaction();
            var resolvedRoomId = ResolveRoomId(db, transaction, roomId, roomName, createIfMissing: true);

            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = @"
INSERT INTO Devices (Name, RoomId, IsOn, Type, Provider, Identifier, ConnectionStatus, LastSeenAt, ConnectionJson, CreatedAt, UpdatedAt)
VALUES (@name, @roomId, @isOn, @type, @provider, @identifier, @connectionStatus, @lastSeenAt, @connectionJson, @createdAt, @updatedAt);
SELECT last_insert_rowid();";
            var now = DateTime.UtcNow;
            command.Parameters.AddWithValue("@name", cleanName);
            command.Parameters.AddWithValue("@roomId", resolvedRoomId);
            command.Parameters.AddWithValue("@isOn", isOn ? 1 : 0);
            command.Parameters.AddWithValue("@type", cleanType);
            command.Parameters.AddWithValue("@provider", cleanProvider);
            command.Parameters.AddWithValue("@identifier", (object?)cleanIdentifier ?? DBNull.Value);
            command.Parameters.AddWithValue("@connectionStatus", validation.Ok ? "connected" : "no_connection");
            command.Parameters.AddWithValue("@lastSeenAt", validation.Ok ? now.ToString("O") : DBNull.Value);
            command.Parameters.AddWithValue("@connectionJson", JsonSerializer.Serialize(connectionData, _jsonOptions));
            command.Parameters.AddWithValue("@createdAt", now.ToString("O"));
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            var insertedId = Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));

            LogEvent(db, transaction, validation.Ok ? "info" : "warning", "api", "DEVICE_CREATED", $"Создано устройство «{cleanName}». Проверка связи: {validation.Message}", deviceId: insertedId, roomId: resolvedRoomId);
            transaction.Commit();

            SyncLegacyDevicesJson(db);
            return ReadDeviceOrThrow(db, insertedId);
        }
    }

    public Device UpdateDevice(int id, string? name, string? roomName, int? roomId, bool? isOn, string? type, string? provider, string? identifier, Dictionary<string, string>? connection)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var current = ReadDeviceOrThrow(db, id);
            using var transaction = db.BeginTransaction();

            var finalName = string.IsNullOrWhiteSpace(name) ? current.Name : NormalizeRequired(name, "Название устройства обязательно", "DEVICE_NAME_REQUIRED");
            var finalType = string.IsNullOrWhiteSpace(type) ? current.Type : NormalizeOptional(type, current.Type);
            var finalProvider = string.IsNullOrWhiteSpace(provider) ? current.Provider : NormalizeOptional(provider, current.Provider);
            var finalIdentifier = string.IsNullOrWhiteSpace(identifier) ? current.Identifier : NormalizeIdentifier(identifier);
            var finalConnection = connection is null || connection.Count == 0 ? current.Connection : connection;
            var validation = ValidateConnection(finalProvider, finalConnection);
            var finalIsOn = isOn ?? current.IsOn;
            var finalRoomId = ResolveRoomId(db, transaction, roomId ?? current.RoomId, roomName, createIfMissing: !string.IsNullOrWhiteSpace(roomName));
            var now = DateTime.UtcNow;
            EnsureDeviceIdentifierIsUnique(db, finalIdentifier, id);

            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = @"
UPDATE Devices
SET Name = @name,
    RoomId = @roomId,
    IsOn = @isOn,
    Type = @type,
    Provider = @provider,
    Identifier = @identifier,
    ConnectionStatus = @connectionStatus,
    LastSeenAt = @lastSeenAt,
    ConnectionJson = @connectionJson,
    UpdatedAt = @updatedAt
WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@name", finalName);
            command.Parameters.AddWithValue("@roomId", (object?)finalRoomId ?? DBNull.Value);
            command.Parameters.AddWithValue("@isOn", finalIsOn ? 1 : 0);
            command.Parameters.AddWithValue("@type", finalType);
            command.Parameters.AddWithValue("@provider", finalProvider);
            command.Parameters.AddWithValue("@identifier", (object?)finalIdentifier ?? DBNull.Value);
            command.Parameters.AddWithValue("@connectionStatus", validation.Ok ? "connected" : "no_connection");
            command.Parameters.AddWithValue("@lastSeenAt", validation.Ok ? now.ToString("O") : DBNull.Value);
            command.Parameters.AddWithValue("@connectionJson", JsonSerializer.Serialize(finalConnection, _jsonOptions));
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            command.ExecuteNonQuery();

            LogEvent(db, transaction, validation.Ok ? "info" : "warning", "api", "DEVICE_UPDATED", $"Обновлено устройство «{finalName}». Проверка связи: {validation.Message}", deviceId: id, roomId: finalRoomId);
            transaction.Commit();

            SyncLegacyDevicesJson(db);
            return ReadDeviceOrThrow(db, id);
        }
    }

    public Device ToggleDevice(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var current = ReadDeviceOrThrow(db, id);
            using var transaction = db.BeginTransaction();
            var nextState = !current.IsOn;
            var now = DateTime.UtcNow;

            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "UPDATE Devices SET IsOn = @isOn, UpdatedAt = @updatedAt WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@isOn", nextState ? 1 : 0);
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            command.ExecuteNonQuery();

            LogEvent(db, transaction, "info", "api", "DEVICE_TOGGLED", $"Устройство «{current.Name}» переключено в {(nextState ? "ON" : "OFF")}", deviceId: id, roomId: current.RoomId);
            transaction.Commit();

            SyncLegacyDevicesJson(db);
            return ReadDeviceOrThrow(db, id);
        }
    }

    public Device AssignDeviceToRoom(int deviceId, int roomId)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var current = ReadDeviceOrThrow(db, deviceId);
            var targetRoom = ReadRoomSummaryOrThrow(db, roomId);
            using var transaction = db.BeginTransaction();
            var now = DateTime.UtcNow;

            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "UPDATE Devices SET RoomId = @roomId, UpdatedAt = @updatedAt WHERE Id = @id;";
            command.Parameters.AddWithValue("@roomId", roomId);
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            command.Parameters.AddWithValue("@id", deviceId);
            command.ExecuteNonQuery();

            LogEvent(db, transaction, "info", "api", "DEVICE_REASSIGNED", $"Устройство «{current.Name}» перенесено в комнату «{targetRoom.Name}»", deviceId: deviceId, roomId: roomId);
            transaction.Commit();

            SyncLegacyDevicesJson(db);
            return ReadDeviceOrThrow(db, deviceId);
        }
    }

    public Device DeleteDevice(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var current = ReadDeviceOrThrow(db, id);
            using var transaction = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "DELETE FROM Devices WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.ExecuteNonQuery();

            LogEvent(db, transaction, "info", "api", "DEVICE_DELETED", $"Удалено устройство «{current.Name}»", deviceId: id, roomId: current.RoomId);
            transaction.Commit();

            SyncLegacyDevicesJson(db);
            return current;
        }
    }

    public IReadOnlyList<Room> GetAllRooms()
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var rooms = new List<Room>();
            var command = db.CreateCommand();
            command.CommandText = @"
SELECT r.Id, r.Name, COALESCE(r.Zone, ''), r.CreatedAt, r.UpdatedAt, COUNT(d.Id)
FROM Rooms r
LEFT JOIN Devices d ON d.RoomId = r.Id
GROUP BY r.Id, r.Name, r.Zone, r.CreatedAt, r.UpdatedAt
ORDER BY r.Name;";

            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                rooms.Add(new Room
                {
                    Id = reader.GetInt32(0),
                    Name = reader.GetString(1),
                    Zone = reader.GetString(2),
                    CreatedAt = ParseUtc(reader.GetString(3)),
                    UpdatedAt = ParseUtc(reader.GetString(4)),
                    DeviceCount = reader.GetInt32(5),
                });
            }

            return rooms;
        }
    }

    public RoomDetails GetRoom(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var room = ReadRoomSummaryOrThrow(db, id);
            return new RoomDetails
            {
                Id = room.Id,
                Name = room.Name,
                Zone = room.Zone,
                DeviceCount = room.DeviceCount,
                CreatedAt = room.CreatedAt,
                UpdatedAt = room.UpdatedAt,
                Devices = ReadDevices(db, id).ToList(),
            };
        }
    }

    public Room CreateRoom(string name, string? zone)
    {
        var cleanName = NormalizeRequired(name, "Название комнаты обязательно", "ROOM_NAME_REQUIRED");
        var cleanZone = NormalizeOptional(zone, string.Empty);

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureRoomNameIsUnique(db, cleanName, null);
            using var transaction = db.BeginTransaction();
            var now = DateTime.UtcNow;
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = @"
INSERT INTO Rooms (Name, Zone, CreatedAt, UpdatedAt)
VALUES (@name, @zone, @createdAt, @updatedAt);
SELECT last_insert_rowid();";
            command.Parameters.AddWithValue("@name", cleanName);
            command.Parameters.AddWithValue("@zone", cleanZone);
            command.Parameters.AddWithValue("@createdAt", now.ToString("O"));
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            var insertedId = Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));
            LogEvent(db, transaction, "info", "api", "ROOM_CREATED", $"Создана комната «{cleanName}»", roomId: insertedId);
            transaction.Commit();
            return ReadRoomSummaryOrThrow(db, insertedId);
        }
    }

    public Room UpdateRoom(int id, string name, string? zone)
    {
        var cleanName = NormalizeRequired(name, "Название комнаты обязательно", "ROOM_NAME_REQUIRED");
        var cleanZone = NormalizeOptional(zone, string.Empty);

        lock (_sync)
        {
            using var db = OpenConnection();
            _ = ReadRoomSummaryOrThrow(db, id);
            EnsureRoomNameIsUnique(db, cleanName, id);
            using var transaction = db.BeginTransaction();
            var now = DateTime.UtcNow;
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "UPDATE Rooms SET Name = @name, Zone = @zone, UpdatedAt = @updatedAt WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@name", cleanName);
            command.Parameters.AddWithValue("@zone", cleanZone);
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            command.ExecuteNonQuery();
            LogEvent(db, transaction, "info", "api", "ROOM_UPDATED", $"Обновлена комната «{cleanName}»", roomId: id);
            transaction.Commit();
            return ReadRoomSummaryOrThrow(db, id);
        }
    }

    public void DeleteRoom(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var room = ReadRoomSummaryOrThrow(db, id);
            if (room.DeviceCount > 0)
            {
                throw new ConflictProblemException("Комнату нельзя удалить, пока в ней есть устройства", "ROOM_NOT_EMPTY");
            }

            using var transaction = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "DELETE FROM Rooms WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.ExecuteNonQuery();
            LogEvent(db, transaction, "info", "api", "ROOM_DELETED", $"Удалена комната «{room.Name}»", roomId: id);
            transaction.Commit();
        }
    }

    public IReadOnlyList<Scene> GetAllScenes()
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            return ReadScenes(db, null, includeRuns: false);
        }
    }

    public Scene GetScene(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var scenes = ReadScenes(db, id, includeRuns: false);
            return scenes.FirstOrDefault() ?? throw new NotFoundProblemException("Сценарий не найден", "SCENE_NOT_FOUND");
        }
    }

    public IReadOnlyList<SceneRun> GetSceneRuns(int sceneId, int limit = 20)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            _ = GetScene(sceneId);
            return ReadSceneRuns(db, sceneId, limit);
        }
    }

    public Scene CreateScene(string name, string? description, IReadOnlyList<SceneActionInput> actions)
    {
        var cleanName = NormalizeRequired(name, "Название сценария обязательно", "SCENE_NAME_REQUIRED");
        var cleanDescription = NormalizeOptional(description, string.Empty);
        ValidateSceneActions(actions);

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureSceneNameIsUnique(db, cleanName, null);
            EnsureDevicesExist(db, actions.Select(x => x.DeviceId).Distinct());

            using var transaction = db.BeginTransaction();
            var now = DateTime.UtcNow;
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = @"
INSERT INTO Scenes (Name, Description, CreatedAt, UpdatedAt, LastRunAt, LastRunStatus, LastRunMessage)
VALUES (@name, @description, @createdAt, @updatedAt, NULL, NULL, NULL);
SELECT last_insert_rowid();";
            command.Parameters.AddWithValue("@name", cleanName);
            command.Parameters.AddWithValue("@description", cleanDescription);
            command.Parameters.AddWithValue("@createdAt", now.ToString("O"));
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            var sceneId = Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));

            InsertSceneActions(db, transaction, sceneId, actions);
            LogEvent(db, transaction, "info", "api", "SCENE_CREATED", $"Создан сценарий «{cleanName}»", sceneId: sceneId);
            transaction.Commit();
            return GetScene(sceneId);
        }
    }

    public Scene UpdateScene(int id, string name, string? description, IReadOnlyList<SceneActionInput> actions)
    {
        var cleanName = NormalizeRequired(name, "Название сценария обязательно", "SCENE_NAME_REQUIRED");
        var cleanDescription = NormalizeOptional(description, string.Empty);
        ValidateSceneActions(actions);

        lock (_sync)
        {
            using var db = OpenConnection();
            _ = GetScene(id);
            EnsureSceneNameIsUnique(db, cleanName, id);
            EnsureDevicesExist(db, actions.Select(x => x.DeviceId).Distinct());

            using var transaction = db.BeginTransaction();
            var now = DateTime.UtcNow;

            var updateScene = db.CreateCommand();
            updateScene.Transaction = transaction;
            updateScene.CommandText = "UPDATE Scenes SET Name = @name, Description = @description, UpdatedAt = @updatedAt WHERE Id = @id;";
            updateScene.Parameters.AddWithValue("@id", id);
            updateScene.Parameters.AddWithValue("@name", cleanName);
            updateScene.Parameters.AddWithValue("@description", cleanDescription);
            updateScene.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            updateScene.ExecuteNonQuery();

            var deleteActions = db.CreateCommand();
            deleteActions.Transaction = transaction;
            deleteActions.CommandText = "DELETE FROM SceneActions WHERE SceneId = @sceneId;";
            deleteActions.Parameters.AddWithValue("@sceneId", id);
            deleteActions.ExecuteNonQuery();

            InsertSceneActions(db, transaction, id, actions);
            LogEvent(db, transaction, "info", "api", "SCENE_UPDATED", $"Обновлен сценарий «{cleanName}»", sceneId: id);
            transaction.Commit();
            return GetScene(id);
        }
    }

    public void DeleteScene(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var scene = GetScene(id);
            using var transaction = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "DELETE FROM Scenes WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.ExecuteNonQuery();
            LogEvent(db, transaction, "info", "api", "SCENE_DELETED", $"Удален сценарий «{scene.Name}»", sceneId: id);
            transaction.Commit();
        }
    }

    public SceneRun RunScene(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var scene = GetScene(id);
            if (scene.Actions.Count == 0)
            {
                throw new ValidationProblemException("В сценарии нет действий", "SCENE_EMPTY");
            }

            using var transaction = db.BeginTransaction();
            var startedAt = DateTime.UtcNow;
            var createRun = db.CreateCommand();
            createRun.Transaction = transaction;
            createRun.CommandText = @"
INSERT INTO SceneRuns (SceneId, StartedAt, CompletedAt, Status, Message)
VALUES (@sceneId, @startedAt, NULL, @status, @message);
SELECT last_insert_rowid();";
            createRun.Parameters.AddWithValue("@sceneId", id);
            createRun.Parameters.AddWithValue("@startedAt", startedAt.ToString("O"));
            createRun.Parameters.AddWithValue("@status", "running");
            createRun.Parameters.AddWithValue("@message", "Сценарий запущен");
            var runId = Convert.ToInt32((long)(createRun.ExecuteScalar() ?? 0));

            foreach (var action in scene.Actions.OrderBy(x => x.SortOrder))
            {
                var updateDevice = db.CreateCommand();
                updateDevice.Transaction = transaction;
                updateDevice.CommandText = "UPDATE Devices SET IsOn = @isOn, UpdatedAt = @updatedAt WHERE Id = @deviceId;";
                updateDevice.Parameters.AddWithValue("@isOn", action.TargetIsOn ? 1 : 0);
                updateDevice.Parameters.AddWithValue("@updatedAt", DateTime.UtcNow.ToString("O"));
                updateDevice.Parameters.AddWithValue("@deviceId", action.DeviceId);
                updateDevice.ExecuteNonQuery();

                LogEvent(
                    db,
                    transaction,
                    "info",
                    "scene-engine",
                    "SCENE_DEVICE_ACTION_APPLIED",
                    $"Сценарий «{scene.Name}» установил устройство «{action.DeviceName}» в состояние {(action.TargetIsOn ? "ON" : "OFF")}",
                    deviceId: action.DeviceId,
                    sceneId: id,
                    runId: runId);
            }

            var completedAt = DateTime.UtcNow;
            var message = $"Сценарий «{scene.Name}» успешно выполнен. Действий: {scene.Actions.Count}";

            var finishRun = db.CreateCommand();
            finishRun.Transaction = transaction;
            finishRun.CommandText = @"
UPDATE SceneRuns
SET CompletedAt = @completedAt,
    Status = @status,
    Message = @message
WHERE Id = @id;";
            finishRun.Parameters.AddWithValue("@completedAt", completedAt.ToString("O"));
            finishRun.Parameters.AddWithValue("@status", "completed");
            finishRun.Parameters.AddWithValue("@message", message);
            finishRun.Parameters.AddWithValue("@id", runId);
            finishRun.ExecuteNonQuery();

            var updateScene = db.CreateCommand();
            updateScene.Transaction = transaction;
            updateScene.CommandText = @"
UPDATE Scenes
SET LastRunAt = @lastRunAt,
    LastRunStatus = @lastRunStatus,
    LastRunMessage = @lastRunMessage,
    UpdatedAt = @updatedAt
WHERE Id = @sceneId;";
            updateScene.Parameters.AddWithValue("@lastRunAt", completedAt.ToString("O"));
            updateScene.Parameters.AddWithValue("@lastRunStatus", "completed");
            updateScene.Parameters.AddWithValue("@lastRunMessage", message);
            updateScene.Parameters.AddWithValue("@updatedAt", completedAt.ToString("O"));
            updateScene.Parameters.AddWithValue("@sceneId", id);
            updateScene.ExecuteNonQuery();

            LogEvent(db, transaction, "info", "scene-engine", "SCENE_RUN_COMPLETED", message, sceneId: id, runId: runId);
            transaction.Commit();

            SyncLegacyDevicesJson(db);
            return ReadSceneRunOrThrow(db, runId);
        }
    }

    public IReadOnlyList<EventLogEntry> GetLogs(int limit = 50)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var logs = new List<EventLogEntry>();
            var command = db.CreateCommand();
            command.CommandText = @"
SELECT Id, Ts, Severity, Source, EventType, Message, UserId, DeviceId, RoomId, SceneId, RunId
FROM EventLogs
ORDER BY Ts DESC, Id DESC
LIMIT @limit;";
            command.Parameters.AddWithValue("@limit", Math.Clamp(limit, 1, 500));
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                logs.Add(new EventLogEntry
                {
                    Id = reader.GetInt32(0),
                    Ts = ParseUtc(reader.GetString(1)),
                    Severity = reader.GetString(2),
                    Source = reader.GetString(3),
                    EventType = reader.GetString(4),
                    Message = reader.GetString(5),
                    UserId = reader.IsDBNull(6) ? null : reader.GetString(6),
                    DeviceId = reader.IsDBNull(7) ? null : reader.GetInt32(7),
                    RoomId = reader.IsDBNull(8) ? null : reader.GetInt32(8),
                    SceneId = reader.IsDBNull(9) ? null : reader.GetInt32(9),
                    RunId = reader.IsDBNull(10) ? null : reader.GetInt32(10),
                });
            }

            return logs;
        }
    }

    public ConnectionValidationResult ValidateDeviceConnection(string? provider, Dictionary<string, string>? connection)
    {
        var cleanProvider = NormalizeOptional(provider, "mock");
        return ValidateConnection(cleanProvider, connection ?? new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase));
    }

    public IReadOnlyList<AutomationRule> GetRules()
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var command = db.CreateCommand();
            command.CommandText = @"
SELECT r.Id, r.Name, r.IsEnabled, r.SourceDeviceId, d.Name, r.EventType, r.Operator, r.CompareValue,
       r.ActionType, r.ActionSceneId, r.ActionDeviceId, r.ActionTargetIsOn, r.CreatedAt, r.UpdatedAt, r.LastTriggeredAt, r.TriggerCount
FROM AutomationRules r
INNER JOIN Devices d ON d.Id = r.SourceDeviceId
ORDER BY r.Name;";
            var items = new List<AutomationRule>();
            using var reader = command.ExecuteReader();
            while (reader.Read())
            {
                items.Add(new AutomationRule
                {
                    Id = reader.GetInt32(0),
                    Name = reader.GetString(1),
                    IsEnabled = reader.GetInt32(2) == 1,
                    SourceDeviceId = reader.GetInt32(3),
                    SourceDeviceName = reader.GetString(4),
                    EventType = reader.GetString(5),
                    Operator = reader.GetString(6),
                    CompareValue = reader.GetString(7),
                    ActionType = reader.GetString(8),
                    ActionSceneId = reader.IsDBNull(9) ? null : reader.GetInt32(9),
                    ActionDeviceId = reader.IsDBNull(10) ? null : reader.GetInt32(10),
                    ActionTargetIsOn = reader.IsDBNull(11) ? null : reader.GetInt32(11) == 1,
                    CreatedAt = ParseUtc(reader.GetString(12)),
                    UpdatedAt = ParseUtc(reader.GetString(13)),
                    LastTriggeredAt = reader.IsDBNull(14) ? null : ParseUtc(reader.GetString(14)),
                    TriggerCount = reader.GetInt32(15),
                });
            }
            return items;
        }
    }

    public AutomationRule CreateRule(string name, bool isEnabled, int sourceDeviceId, string eventType, string op, string compareValue, string actionType, int? actionSceneId, int? actionDeviceId, bool? actionTargetIsOn)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            ValidateRulePayload(db, sourceDeviceId, actionType, actionSceneId, actionDeviceId, actionTargetIsOn);
            var now = DateTime.UtcNow;
            using var tx = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = tx;
            command.CommandText = @"INSERT INTO AutomationRules (Name, IsEnabled, SourceDeviceId, EventType, Operator, CompareValue, ActionType, ActionSceneId, ActionDeviceId, ActionTargetIsOn, CreatedAt, UpdatedAt)
VALUES (@name,@isEnabled,@sourceDeviceId,@eventType,@op,@compareValue,@actionType,@actionSceneId,@actionDeviceId,@actionTargetIsOn,@createdAt,@updatedAt);
SELECT last_insert_rowid();";
            command.Parameters.AddWithValue("@name", NormalizeRequired(name, "Название правила обязательно", "RULE_NAME_REQUIRED"));
            command.Parameters.AddWithValue("@isEnabled", isEnabled ? 1 : 0);
            command.Parameters.AddWithValue("@sourceDeviceId", sourceDeviceId);
            command.Parameters.AddWithValue("@eventType", NormalizeOptional(eventType, "state"));
            command.Parameters.AddWithValue("@op", NormalizeOptional(op, "eq"));
            command.Parameters.AddWithValue("@compareValue", NormalizeOptional(compareValue, ""));
            command.Parameters.AddWithValue("@actionType", NormalizeOptional(actionType, "scene"));
            command.Parameters.AddWithValue("@actionSceneId", (object?)actionSceneId ?? DBNull.Value);
            command.Parameters.AddWithValue("@actionDeviceId", (object?)actionDeviceId ?? DBNull.Value);
            command.Parameters.AddWithValue("@actionTargetIsOn", actionTargetIsOn.HasValue ? (actionTargetIsOn.Value ? 1 : 0) : DBNull.Value);
            command.Parameters.AddWithValue("@createdAt", now.ToString("O"));
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            var id = Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));
            LogEvent(db, tx, "info", "automation", "RULE_CREATED", $"Создано правило «{name}»");
            tx.Commit();
            return GetRules().First(x => x.Id == id);
        }
    }

    public void DeleteRule(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var cmd = db.CreateCommand();
            cmd.CommandText = "DELETE FROM AutomationRules WHERE Id = @id;";
            cmd.Parameters.AddWithValue("@id", id);
            if (cmd.ExecuteNonQuery() == 0)
            {
                throw new NotFoundProblemException("Правило не найдено", "RULE_NOT_FOUND");
            }
        }
    }

    public IReadOnlyList<RuleTriggerLog> GetRuleTriggerLogs(int limit = 50)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var cmd = db.CreateCommand();
            cmd.CommandText = @"SELECT l.Id, l.RuleId, r.Name, l.TriggeredAt, l.EventType, l.EventValue, l.Status, l.Message
FROM RuleTriggerLogs l
INNER JOIN AutomationRules r ON r.Id = l.RuleId
ORDER BY l.TriggeredAt DESC, l.Id DESC
LIMIT @limit;";
            cmd.Parameters.AddWithValue("@limit", Math.Clamp(limit, 1, 200));
            var items = new List<RuleTriggerLog>();
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                items.Add(new RuleTriggerLog
                {
                    Id = reader.GetInt32(0),
                    RuleId = reader.GetInt32(1),
                    RuleName = reader.GetString(2),
                    TriggeredAt = ParseUtc(reader.GetString(3)),
                    EventType = reader.GetString(4),
                    EventValue = reader.GetString(5),
                    Status = reader.GetString(6),
                    Message = reader.GetString(7),
                });
            }
            return items;
        }
    }

    public RuleEventResult ProcessEvent(int deviceId, string eventType, string value)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            _ = ReadDeviceOrThrow(db, deviceId);
            var rules = GetRules().Where(r => r.IsEnabled && r.SourceDeviceId == deviceId && string.Equals(r.EventType, eventType, StringComparison.OrdinalIgnoreCase)).ToList();
            var triggered = 0;
            foreach (var rule in rules)
            {
                if (!IsRuleMatch(rule.Operator, rule.CompareValue, value))
                {
                    continue;
                }

                triggered++;
                var status = "completed";
                var message = ExecuteAction(rule.ActionType, rule.ActionSceneId, rule.ActionDeviceId, rule.ActionTargetIsOn);

                using var tx = db.BeginTransaction();
                var upd = db.CreateCommand();
                upd.Transaction = tx;
                upd.CommandText = "UPDATE AutomationRules SET TriggerCount = TriggerCount + 1, LastTriggeredAt = @now, UpdatedAt = @now WHERE Id = @id;";
                var now = DateTime.UtcNow;
                upd.Parameters.AddWithValue("@now", now.ToString("O"));
                upd.Parameters.AddWithValue("@id", rule.Id);
                upd.ExecuteNonQuery();

                var log = db.CreateCommand();
                log.Transaction = tx;
                log.CommandText = "INSERT INTO RuleTriggerLogs (RuleId, TriggeredAt, EventType, EventValue, Status, Message) VALUES (@ruleId, @ts, @eventType, @eventValue, @status, @message);";
                log.Parameters.AddWithValue("@ruleId", rule.Id);
                log.Parameters.AddWithValue("@ts", now.ToString("O"));
                log.Parameters.AddWithValue("@eventType", eventType);
                log.Parameters.AddWithValue("@eventValue", value);
                log.Parameters.AddWithValue("@status", status);
                log.Parameters.AddWithValue("@message", message);
                log.ExecuteNonQuery();
                LogEvent(db, tx, "info", "automation", "RULE_TRIGGERED", $"Сработало правило «{rule.Name}»: {message}", deviceId: deviceId);
                tx.Commit();
            }

            return new RuleEventResult(rules.Count, triggered, triggered == 0 ? "Совпадений не найдено" : "Правила обработаны");
        }
    }

    public IReadOnlyList<ScheduleEntry> GetSchedules()
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var cmd = db.CreateCommand();
            cmd.CommandText = "SELECT Id, Name, IsEnabled, DaysOfWeek, TimeOfDay, ActionType, ActionSceneId, ActionDeviceId, ActionTargetIsOn, CreatedAt, UpdatedAt, LastRunAt FROM Schedules ORDER BY Name;";
            var items = new List<ScheduleEntry>();
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                items.Add(new ScheduleEntry
                {
                    Id = reader.GetInt32(0), Name = reader.GetString(1), IsEnabled = reader.GetInt32(2) == 1, DaysOfWeek = reader.GetString(3), TimeOfDay = reader.GetString(4), ActionType = reader.GetString(5),
                    ActionSceneId = reader.IsDBNull(6) ? null : reader.GetInt32(6), ActionDeviceId = reader.IsDBNull(7) ? null : reader.GetInt32(7), ActionTargetIsOn = reader.IsDBNull(8) ? null : reader.GetInt32(8) == 1,
                    CreatedAt = ParseUtc(reader.GetString(9)), UpdatedAt = ParseUtc(reader.GetString(10)), LastRunAt = reader.IsDBNull(11) ? null : ParseUtc(reader.GetString(11)),
                });
            }
            return items;
        }
    }

    public ScheduleEntry CreateSchedule(string name, bool isEnabled, string daysOfWeek, string timeOfDay, string actionType, int? actionSceneId, int? actionDeviceId, bool? actionTargetIsOn)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            ValidateSchedulePayload(db, actionType, actionSceneId, actionDeviceId, actionTargetIsOn, timeOfDay);
            using var tx = db.BeginTransaction();
            var now = DateTime.UtcNow;
            var cmd = db.CreateCommand();
            cmd.Transaction = tx;
            cmd.CommandText = @"INSERT INTO Schedules (Name, IsEnabled, DaysOfWeek, TimeOfDay, ActionType, ActionSceneId, ActionDeviceId, ActionTargetIsOn, CreatedAt, UpdatedAt)
VALUES (@name,@isEnabled,@days,@time,@actionType,@sceneId,@deviceId,@target,@created,@updated); SELECT last_insert_rowid();";
            cmd.Parameters.AddWithValue("@name", NormalizeRequired(name, "Название расписания обязательно", "SCHEDULE_NAME_REQUIRED"));
            cmd.Parameters.AddWithValue("@isEnabled", isEnabled ? 1 : 0);
            cmd.Parameters.AddWithValue("@days", NormalizeOptional(daysOfWeek, "1,2,3,4,5,6,7"));
            cmd.Parameters.AddWithValue("@time", timeOfDay);
            cmd.Parameters.AddWithValue("@actionType", actionType);
            cmd.Parameters.AddWithValue("@sceneId", (object?)actionSceneId ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@deviceId", (object?)actionDeviceId ?? DBNull.Value);
            cmd.Parameters.AddWithValue("@target", actionTargetIsOn.HasValue ? (actionTargetIsOn.Value ? 1 : 0) : DBNull.Value);
            cmd.Parameters.AddWithValue("@created", now.ToString("O"));
            cmd.Parameters.AddWithValue("@updated", now.ToString("O"));
            var id = Convert.ToInt32((long)(cmd.ExecuteScalar() ?? 0));
            LogEvent(db, tx, "info", "scheduler", "SCHEDULE_CREATED", $"Создано расписание «{name}»");
            tx.Commit();
            return GetSchedules().First(x => x.Id == id);
        }
    }

    public void DeleteSchedule(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var cmd = db.CreateCommand();
            cmd.CommandText = "DELETE FROM Schedules WHERE Id = @id;";
            cmd.Parameters.AddWithValue("@id", id);
            if (cmd.ExecuteNonQuery() == 0)
            {
                throw new NotFoundProblemException("Расписание не найдено", "SCHEDULE_NOT_FOUND");
            }
        }
    }

    public IReadOnlyList<ScheduleRunLog> GetScheduleRuns(int limit = 50)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var cmd = db.CreateCommand();
            cmd.CommandText = @"SELECT sr.Id, sr.ScheduleId, s.Name, sr.StartedAt, sr.Status, sr.Message
FROM ScheduleRuns sr INNER JOIN Schedules s ON s.Id = sr.ScheduleId
ORDER BY sr.StartedAt DESC, sr.Id DESC LIMIT @limit;";
            cmd.Parameters.AddWithValue("@limit", Math.Clamp(limit, 1, 200));
            var items = new List<ScheduleRunLog>();
            using var reader = cmd.ExecuteReader();
            while (reader.Read())
            {
                items.Add(new ScheduleRunLog { Id = reader.GetInt32(0), ScheduleId = reader.GetInt32(1), ScheduleName = reader.GetString(2), StartedAt = ParseUtc(reader.GetString(3)), Status = reader.GetString(4), Message = reader.GetString(5) });
            }
            return items;
        }
    }

    public ScheduleRunResult RunDueSchedules(DateTime utcNow)
    {
        lock (_sync)
        {
            var schedules = GetSchedules().Where(x => x.IsEnabled && IsScheduleDue(x, utcNow)).ToList();
            var started = 0;
            using var db = OpenConnection();
            foreach (var schedule in schedules)
            {
                started++;
                var message = ExecuteAction(schedule.ActionType, schedule.ActionSceneId, schedule.ActionDeviceId, schedule.ActionTargetIsOn);
                using var tx = db.BeginTransaction();
                var now = DateTime.UtcNow;
                var upd = db.CreateCommand();
                upd.Transaction = tx;
                upd.CommandText = "UPDATE Schedules SET LastRunAt = @lastRunAt, UpdatedAt = @updatedAt WHERE Id = @id;";
                upd.Parameters.AddWithValue("@lastRunAt", now.ToString("O"));
                upd.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
                upd.Parameters.AddWithValue("@id", schedule.Id);
                upd.ExecuteNonQuery();
                var log = db.CreateCommand();
                log.Transaction = tx;
                log.CommandText = "INSERT INTO ScheduleRuns (ScheduleId, StartedAt, Status, Message) VALUES (@scheduleId, @startedAt, @status, @message);";
                log.Parameters.AddWithValue("@scheduleId", schedule.Id);
                log.Parameters.AddWithValue("@startedAt", now.ToString("O"));
                log.Parameters.AddWithValue("@status", "completed");
                log.Parameters.AddWithValue("@message", message);
                log.ExecuteNonQuery();
                LogEvent(db, tx, "info", "scheduler", "SCHEDULE_TRIGGERED", $"Сработало расписание «{schedule.Name}»: {message}");
                tx.Commit();
            }
            return new ScheduleRunResult(schedules.Count, started, started == 0 ? "Нет задач для запуска" : "Расписание выполнено");
        }
    }

    private void InitializeDatabase(SqliteConnection connection)
    {
        var command = connection.CreateCommand();
        command.CommandText = @"
CREATE TABLE IF NOT EXISTS Rooms (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    Zone TEXT NOT NULL DEFAULT '',
    CreatedAt TEXT NOT NULL,
    UpdatedAt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Devices (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    RoomId INTEGER NULL,
    IsOn INTEGER NOT NULL,
    Type TEXT NOT NULL DEFAULT 'Другое',
    Provider TEXT NOT NULL DEFAULT 'mock',
    Identifier TEXT NULL,
    ConnectionStatus TEXT NOT NULL DEFAULT 'unknown',
    LastSeenAt TEXT NULL,
    ConnectionJson TEXT NOT NULL DEFAULT '{}',
    CreatedAt TEXT NOT NULL,
    UpdatedAt TEXT NOT NULL,
    FOREIGN KEY(RoomId) REFERENCES Rooms(Id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS Scenes (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    Description TEXT NOT NULL DEFAULT '',
    CreatedAt TEXT NOT NULL,
    UpdatedAt TEXT NOT NULL,
    LastRunAt TEXT NULL,
    LastRunStatus TEXT NULL,
    LastRunMessage TEXT NULL
);

CREATE TABLE IF NOT EXISTS SceneActions (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    SceneId INTEGER NOT NULL,
    DeviceId INTEGER NOT NULL,
    TargetIsOn INTEGER NOT NULL,
    SortOrder INTEGER NOT NULL,
    FOREIGN KEY(SceneId) REFERENCES Scenes(Id) ON DELETE CASCADE,
    FOREIGN KEY(DeviceId) REFERENCES Devices(Id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS SceneRuns (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    SceneId INTEGER NOT NULL,
    StartedAt TEXT NOT NULL,
    CompletedAt TEXT NULL,
    Status TEXT NOT NULL,
    Message TEXT NOT NULL,
    FOREIGN KEY(SceneId) REFERENCES Scenes(Id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS AutomationRules (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    IsEnabled INTEGER NOT NULL,
    SourceDeviceId INTEGER NOT NULL,
    EventType TEXT NOT NULL,
    Operator TEXT NOT NULL,
    CompareValue TEXT NOT NULL,
    ActionType TEXT NOT NULL,
    ActionSceneId INTEGER NULL,
    ActionDeviceId INTEGER NULL,
    ActionTargetIsOn INTEGER NULL,
    LastTriggeredAt TEXT NULL,
    TriggerCount INTEGER NOT NULL DEFAULT 0,
    CreatedAt TEXT NOT NULL,
    UpdatedAt TEXT NOT NULL,
    FOREIGN KEY(SourceDeviceId) REFERENCES Devices(Id) ON DELETE CASCADE,
    FOREIGN KEY(ActionSceneId) REFERENCES Scenes(Id) ON DELETE SET NULL,
    FOREIGN KEY(ActionDeviceId) REFERENCES Devices(Id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS RuleTriggerLogs (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    RuleId INTEGER NOT NULL,
    TriggeredAt TEXT NOT NULL,
    EventType TEXT NOT NULL,
    EventValue TEXT NOT NULL,
    Status TEXT NOT NULL,
    Message TEXT NOT NULL,
    FOREIGN KEY(RuleId) REFERENCES AutomationRules(Id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Schedules (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    IsEnabled INTEGER NOT NULL,
    DaysOfWeek TEXT NOT NULL,
    TimeOfDay TEXT NOT NULL,
    ActionType TEXT NOT NULL,
    ActionSceneId INTEGER NULL,
    ActionDeviceId INTEGER NULL,
    ActionTargetIsOn INTEGER NULL,
    LastRunAt TEXT NULL,
    CreatedAt TEXT NOT NULL,
    UpdatedAt TEXT NOT NULL,
    FOREIGN KEY(ActionSceneId) REFERENCES Scenes(Id) ON DELETE SET NULL,
    FOREIGN KEY(ActionDeviceId) REFERENCES Devices(Id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ScheduleRuns (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    ScheduleId INTEGER NOT NULL,
    StartedAt TEXT NOT NULL,
    Status TEXT NOT NULL,
    Message TEXT NOT NULL,
    FOREIGN KEY(ScheduleId) REFERENCES Schedules(Id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS EventLogs (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Ts TEXT NOT NULL,
    Severity TEXT NOT NULL,
    Source TEXT NOT NULL,
    EventType TEXT NOT NULL,
    Message TEXT NOT NULL,
    UserId TEXT NULL,
    DeviceId INTEGER NULL,
    RoomId INTEGER NULL,
    SceneId INTEGER NULL,
    RunId INTEGER NULL
);";
        command.ExecuteNonQuery();

        AddColumnIfMissing(connection, "Devices", "Identifier", "TEXT NULL");
        AddColumnIfMissing(connection, "Devices", "ConnectionStatus", "TEXT NOT NULL DEFAULT 'unknown'");
        AddColumnIfMissing(connection, "Devices", "LastSeenAt", "TEXT NULL");

        var idxCommand = connection.CreateCommand();
        idxCommand.CommandText = "CREATE UNIQUE INDEX IF NOT EXISTS IX_Devices_Identifier_Unique ON Devices(Identifier) WHERE Identifier IS NOT NULL;";
        idxCommand.ExecuteNonQuery();
    }

    private void SeedIfNeeded(SqliteConnection connection)
    {
        var roomsCount = ExecuteCount(connection, "SELECT COUNT(1) FROM Rooms;");
        var devicesCount = ExecuteCount(connection, "SELECT COUNT(1) FROM Devices;");
        if (roomsCount > 0 || devicesCount > 0)
        {
            return;
        }

        var seedDevices = LoadLegacyDevices();
        if (seedDevices.Count == 0)
        {
            seedDevices =
            new List<LegacyDevice>
            {
                new LegacyDevice { Name = "Термостат", Room = "Гостиная", IsOn = false, Type = "Климат" },
                new LegacyDevice { Name = "Освещение", Room = "Кухня", IsOn = true, Type = "Свет" },
                new LegacyDevice { Name = "Камера", Room = "Вход", IsOn = true, Type = "Камера" },
            };
        }

        using var transaction = connection.BeginTransaction();
        var roomIds = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        foreach (var legacy in seedDevices)
        {
            var roomName = NormalizeOptional(legacy.Room, "Комната без названия");
            if (!roomIds.ContainsKey(roomName))
            {
                roomIds[roomName] = InsertRoom(connection, transaction, roomName, "Основная зона");
            }
        }

        foreach (var legacy in seedDevices)
        {
            var roomName = NormalizeOptional(legacy.Room, "Комната без названия");
            var roomId = roomIds[roomName];
            InsertDevice(
                connection,
                transaction,
                NormalizeOptional(legacy.Name, "Устройство"),
                roomId,
                legacy.IsOn,
                NormalizeOptional(legacy.Type, InferDeviceType(legacy.Name)),
                NormalizeOptional(legacy.Provider, "mock"),
                legacy.Connection ?? new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase));
        }

        LogEvent(connection, transaction, "info", "bootstrap", "DATA_IMPORTED", "Исходные устройства перенесены в SQLite-хранилище");
        transaction.Commit();
    }

    private void SyncLegacyDevicesJson(SqliteConnection connection)
    {
        var legacyDevices = ReadDevices(connection, null)
            .Select(device => new LegacyDevice
            {
                Id = device.Id,
                Name = device.Name,
                Room = device.Room,
                IsOn = device.IsOn,
                Type = device.Type,
                Provider = device.Provider,
                Connection = device.Connection,
            })
            .ToList();

        File.WriteAllText(_legacyDevicesPath, JsonSerializer.Serialize(legacyDevices, _jsonOptions));
    }

    private List<LegacyDevice> LoadLegacyDevices()
    {
        if (!File.Exists(_legacyDevicesPath))
        {
            return new List<LegacyDevice>();
        }

        try
        {
            var json = File.ReadAllText(_legacyDevicesPath);
            return JsonSerializer.Deserialize<List<LegacyDevice>>(json, _jsonOptions) ?? new List<LegacyDevice>();
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Не удалось прочитать legacy devices.json");
            return new List<LegacyDevice>();
        }
    }

    private List<Device> ReadDevices(SqliteConnection connection, int? roomId)
    {
        var devices = new List<Device>();
        var command = connection.CreateCommand();
        command.CommandText = @"
SELECT d.Id,
       d.Name,
       d.RoomId,
       COALESCE(r.Name, 'Комната не указана') AS RoomName,
       d.IsOn,
       d.Type,
       d.Provider,
       d.Identifier,
       d.ConnectionStatus,
       d.LastSeenAt,
       d.ConnectionJson,
       d.CreatedAt,
       d.UpdatedAt
FROM Devices d
LEFT JOIN Rooms r ON r.Id = d.RoomId
WHERE (@roomId IS NULL OR d.RoomId = @roomId)
ORDER BY d.Name;";
        command.Parameters.AddWithValue("@roomId", (object?)roomId ?? DBNull.Value);
        using var reader = command.ExecuteReader();
        while (reader.Read())
        {
            devices.Add(new Device
            {
                Id = reader.GetInt32(0),
                Name = reader.GetString(1),
                RoomId = reader.IsDBNull(2) ? null : reader.GetInt32(2),
                Room = reader.GetString(3),
                IsOn = reader.GetInt32(4) == 1,
                Type = reader.GetString(5),
                Provider = reader.GetString(6),
                Identifier = reader.IsDBNull(7) ? null : reader.GetString(7),
                ConnectionStatus = reader.IsDBNull(8) ? "unknown" : reader.GetString(8),
                LastSeenAt = reader.IsDBNull(9) ? null : ParseUtc(reader.GetString(9)),
                Connection = DeserializeConnection(reader.GetString(10)),
                CreatedAt = ParseUtc(reader.GetString(11)),
                UpdatedAt = ParseUtc(reader.GetString(12)),
            });
        }

        return devices;
    }

    private Device ReadDeviceOrThrow(SqliteConnection connection, int id)
    {
        var command = connection.CreateCommand();
        command.CommandText = @"
SELECT d.Id,
       d.Name,
       d.RoomId,
       COALESCE(r.Name, 'Комната не указана') AS RoomName,
       d.IsOn,
       d.Type,
       d.Provider,
       d.Identifier,
       d.ConnectionStatus,
       d.LastSeenAt,
       d.ConnectionJson,
       d.CreatedAt,
       d.UpdatedAt
FROM Devices d
LEFT JOIN Rooms r ON r.Id = d.RoomId
WHERE d.Id = @id;";
        command.Parameters.AddWithValue("@id", id);
        using var reader = command.ExecuteReader();
        if (!reader.Read())
        {
            throw new NotFoundProblemException("Устройство не найдено", "DEVICE_NOT_FOUND");
        }

        return new Device
        {
            Id = reader.GetInt32(0),
            Name = reader.GetString(1),
            RoomId = reader.IsDBNull(2) ? null : reader.GetInt32(2),
            Room = reader.GetString(3),
            IsOn = reader.GetInt32(4) == 1,
            Type = reader.GetString(5),
            Provider = reader.GetString(6),
            Identifier = reader.IsDBNull(7) ? null : reader.GetString(7),
            ConnectionStatus = reader.IsDBNull(8) ? "unknown" : reader.GetString(8),
            LastSeenAt = reader.IsDBNull(9) ? null : ParseUtc(reader.GetString(9)),
            Connection = DeserializeConnection(reader.GetString(10)),
            CreatedAt = ParseUtc(reader.GetString(11)),
            UpdatedAt = ParseUtc(reader.GetString(12)),
        };
    }

    private Room ReadRoomSummaryOrThrow(SqliteConnection connection, int id)
    {
        var command = connection.CreateCommand();
        command.CommandText = @"
SELECT r.Id, r.Name, COALESCE(r.Zone, ''), r.CreatedAt, r.UpdatedAt, COUNT(d.Id)
FROM Rooms r
LEFT JOIN Devices d ON d.RoomId = r.Id
WHERE r.Id = @id
GROUP BY r.Id, r.Name, r.Zone, r.CreatedAt, r.UpdatedAt;";
        command.Parameters.AddWithValue("@id", id);
        using var reader = command.ExecuteReader();
        if (!reader.Read())
        {
            throw new NotFoundProblemException("Комната не найдена", "ROOM_NOT_FOUND");
        }

        return new Room
        {
            Id = reader.GetInt32(0),
            Name = reader.GetString(1),
            Zone = reader.GetString(2),
            CreatedAt = ParseUtc(reader.GetString(3)),
            UpdatedAt = ParseUtc(reader.GetString(4)),
            DeviceCount = reader.GetInt32(5),
        };
    }

    private List<Scene> ReadScenes(SqliteConnection connection, int? sceneId, bool includeRuns)
    {
        var scenes = new List<Scene>();
        var command = connection.CreateCommand();
        command.CommandText = @"
SELECT Id, Name, Description, CreatedAt, UpdatedAt, LastRunAt, LastRunStatus, LastRunMessage
FROM Scenes
WHERE (@sceneId IS NULL OR Id = @sceneId)
ORDER BY Name;";
        command.Parameters.AddWithValue("@sceneId", (object?)sceneId ?? DBNull.Value);
        using (var reader = command.ExecuteReader())
        {
            while (reader.Read())
            {
                scenes.Add(new Scene
                {
                    Id = reader.GetInt32(0),
                    Name = reader.GetString(1),
                    Description = reader.GetString(2),
                    CreatedAt = ParseUtc(reader.GetString(3)),
                    UpdatedAt = ParseUtc(reader.GetString(4)),
                    LastRunAt = reader.IsDBNull(5) ? null : ParseUtc(reader.GetString(5)),
                    LastRunStatus = reader.IsDBNull(6) ? null : reader.GetString(6),
                    LastRunMessage = reader.IsDBNull(7) ? null : reader.GetString(7),
                });
            }
        }

        if (scenes.Count == 0)
        {
            return scenes;
        }

        var sceneMap = scenes.ToDictionary(scene => scene.Id);
        var actionsCommand = connection.CreateCommand();
        actionsCommand.CommandText = @"
SELECT a.Id, a.SceneId, a.DeviceId, d.Name, COALESCE(r.Name, 'Комната не указана'), a.TargetIsOn, a.SortOrder
FROM SceneActions a
INNER JOIN Devices d ON d.Id = a.DeviceId
LEFT JOIN Rooms r ON r.Id = d.RoomId
WHERE (@sceneId IS NULL OR a.SceneId = @sceneId)
ORDER BY a.SceneId, a.SortOrder;";
        actionsCommand.Parameters.AddWithValue("@sceneId", (object?)sceneId ?? DBNull.Value);
        using (var reader = actionsCommand.ExecuteReader())
        {
            while (reader.Read())
            {
                var action = new SceneAction
                {
                    Id = reader.GetInt32(0),
                    SceneId = reader.GetInt32(1),
                    DeviceId = reader.GetInt32(2),
                    DeviceName = reader.GetString(3),
                    RoomName = reader.GetString(4),
                    TargetIsOn = reader.GetInt32(5) == 1,
                    SortOrder = reader.GetInt32(6),
                };
                if (sceneMap.TryGetValue(action.SceneId, out var scene))
                {
                    scene.Actions.Add(action);
                }
            }
        }

        if (includeRuns)
        {
            foreach (var scene in scenes)
            {
                _ = ReadSceneRuns(connection, scene.Id, 10);
            }
        }

        return scenes;
    }

    private List<SceneRun> ReadSceneRuns(SqliteConnection connection, int sceneId, int limit)
    {
        var runs = new List<SceneRun>();
        var command = connection.CreateCommand();
        command.CommandText = @"
SELECT sr.Id, sr.SceneId, s.Name, sr.StartedAt, sr.CompletedAt, sr.Status, sr.Message
FROM SceneRuns sr
INNER JOIN Scenes s ON s.Id = sr.SceneId
WHERE sr.SceneId = @sceneId
ORDER BY sr.StartedAt DESC, sr.Id DESC
LIMIT @limit;";
        command.Parameters.AddWithValue("@sceneId", sceneId);
        command.Parameters.AddWithValue("@limit", Math.Clamp(limit, 1, 100));
        using var reader = command.ExecuteReader();
        while (reader.Read())
        {
            runs.Add(new SceneRun
            {
                Id = reader.GetInt32(0),
                SceneId = reader.GetInt32(1),
                SceneName = reader.GetString(2),
                StartedAt = ParseUtc(reader.GetString(3)),
                CompletedAt = reader.IsDBNull(4) ? null : ParseUtc(reader.GetString(4)),
                Status = reader.GetString(5),
                Message = reader.GetString(6),
            });
        }

        return runs;
    }

    private SceneRun ReadSceneRunOrThrow(SqliteConnection connection, int runId)
    {
        var command = connection.CreateCommand();
        command.CommandText = @"
SELECT sr.Id, sr.SceneId, s.Name, sr.StartedAt, sr.CompletedAt, sr.Status, sr.Message
FROM SceneRuns sr
INNER JOIN Scenes s ON s.Id = sr.SceneId
WHERE sr.Id = @runId;";
        command.Parameters.AddWithValue("@runId", runId);
        using var reader = command.ExecuteReader();
        if (!reader.Read())
        {
            throw new NotFoundProblemException("Запуск сценария не найден", "SCENE_RUN_NOT_FOUND");
        }

        return new SceneRun
        {
            Id = reader.GetInt32(0),
            SceneId = reader.GetInt32(1),
            SceneName = reader.GetString(2),
            StartedAt = ParseUtc(reader.GetString(3)),
            CompletedAt = reader.IsDBNull(4) ? null : ParseUtc(reader.GetString(4)),
            Status = reader.GetString(5),
            Message = reader.GetString(6),
        };
    }

    private int ResolveRoomId(SqliteConnection connection, SqliteTransaction transaction, int? roomId, string? roomName, bool createIfMissing)
    {
        if (roomId.HasValue)
        {
            _ = ReadRoomSummaryOrThrow(connection, roomId.Value);
            return roomId.Value;
        }

        var cleanRoomName = NormalizeOptional(roomName, string.Empty);
        if (string.IsNullOrWhiteSpace(cleanRoomName))
        {
            throw new ValidationProblemException("Нужно указать комнату или roomId", "ROOM_BINDING_REQUIRED");
        }

        var find = connection.CreateCommand();
        find.Transaction = transaction;
        find.CommandText = "SELECT Id FROM Rooms WHERE lower(Name) = lower(@name) LIMIT 1;";
        find.Parameters.AddWithValue("@name", cleanRoomName);
        var existing = find.ExecuteScalar();
        if (existing is long existingId)
        {
            return Convert.ToInt32(existingId);
        }

        if (!createIfMissing)
        {
            throw new NotFoundProblemException("Комната не найдена", "ROOM_NOT_FOUND");
        }

        return InsertRoom(connection, transaction, cleanRoomName, string.Empty);
    }

    private int InsertRoom(SqliteConnection connection, SqliteTransaction transaction, string name, string zone)
    {
        var now = DateTime.UtcNow;
        var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = @"
INSERT INTO Rooms (Name, Zone, CreatedAt, UpdatedAt)
VALUES (@name, @zone, @createdAt, @updatedAt);
SELECT last_insert_rowid();";
        command.Parameters.AddWithValue("@name", name);
        command.Parameters.AddWithValue("@zone", zone);
        command.Parameters.AddWithValue("@createdAt", now.ToString("O"));
        command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
        return Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));
    }

    private int InsertDevice(SqliteConnection connection, SqliteTransaction transaction, string name, int roomId, bool isOn, string type, string provider, Dictionary<string, string> connectionData)
    {
        var now = DateTime.UtcNow;
        var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = @"
INSERT INTO Devices (Name, RoomId, IsOn, Type, Provider, Identifier, ConnectionStatus, LastSeenAt, ConnectionJson, CreatedAt, UpdatedAt)
VALUES (@name, @roomId, @isOn, @type, @provider, NULL, 'unknown', NULL, @connectionJson, @createdAt, @updatedAt);
SELECT last_insert_rowid();";
        command.Parameters.AddWithValue("@name", name);
        command.Parameters.AddWithValue("@roomId", roomId);
        command.Parameters.AddWithValue("@isOn", isOn ? 1 : 0);
        command.Parameters.AddWithValue("@type", type);
        command.Parameters.AddWithValue("@provider", provider);
        command.Parameters.AddWithValue("@connectionJson", JsonSerializer.Serialize(connectionData, _jsonOptions));
        command.Parameters.AddWithValue("@createdAt", now.ToString("O"));
        command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
        return Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));
    }

    private void InsertSceneActions(SqliteConnection connection, SqliteTransaction transaction, int sceneId, IReadOnlyList<SceneActionInput> actions)
    {
        foreach (var action in actions.OrderBy(x => x.SortOrder))
        {
            var command = connection.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = @"
INSERT INTO SceneActions (SceneId, DeviceId, TargetIsOn, SortOrder)
VALUES (@sceneId, @deviceId, @targetIsOn, @sortOrder);";
            command.Parameters.AddWithValue("@sceneId", sceneId);
            command.Parameters.AddWithValue("@deviceId", action.DeviceId);
            command.Parameters.AddWithValue("@targetIsOn", action.TargetIsOn ? 1 : 0);
            command.Parameters.AddWithValue("@sortOrder", action.SortOrder);
            command.ExecuteNonQuery();
        }
    }

    private void LogEvent(
        SqliteConnection connection,
        SqliteTransaction? transaction,
        string severity,
        string source,
        string eventType,
        string message,
        string? userId = null,
        int? deviceId = null,
        int? roomId = null,
        int? sceneId = null,
        int? runId = null)
    {
        var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = @"
INSERT INTO EventLogs (Ts, Severity, Source, EventType, Message, UserId, DeviceId, RoomId, SceneId, RunId)
VALUES (@ts, @severity, @source, @eventType, @message, @userId, @deviceId, @roomId, @sceneId, @runId);";
        command.Parameters.AddWithValue("@ts", DateTime.UtcNow.ToString("O"));
        command.Parameters.AddWithValue("@severity", severity);
        command.Parameters.AddWithValue("@source", source);
        command.Parameters.AddWithValue("@eventType", eventType);
        command.Parameters.AddWithValue("@message", message);
        command.Parameters.AddWithValue("@userId", (object?)userId ?? DBNull.Value);
        command.Parameters.AddWithValue("@deviceId", (object?)deviceId ?? DBNull.Value);
        command.Parameters.AddWithValue("@roomId", (object?)roomId ?? DBNull.Value);
        command.Parameters.AddWithValue("@sceneId", (object?)sceneId ?? DBNull.Value);
        command.Parameters.AddWithValue("@runId", (object?)runId ?? DBNull.Value);
        command.ExecuteNonQuery();
    }

    private void ValidateSceneActions(IReadOnlyList<SceneActionInput> actions)
    {
        if (actions.Count == 0)
        {
            throw new ValidationProblemException("Добавьте хотя бы одно действие в сценарий", "SCENE_ACTIONS_REQUIRED");
        }
    }

    private void EnsureDevicesExist(SqliteConnection connection, IEnumerable<int> deviceIds)
    {
        foreach (var deviceId in deviceIds)
        {
            var command = connection.CreateCommand();
            command.CommandText = "SELECT COUNT(1) FROM Devices WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", deviceId);
            if (Convert.ToInt32(command.ExecuteScalar() ?? 0) == 0)
            {
                throw new NotFoundProblemException($"Устройство с ID {deviceId} не найдено", "DEVICE_NOT_FOUND");
            }
        }
    }

    private void EnsureRoomNameIsUnique(SqliteConnection connection, string name, int? currentRoomId)
    {
        var command = connection.CreateCommand();
        command.CommandText = "SELECT Id FROM Rooms WHERE lower(Name) = lower(@name) LIMIT 1;";
        command.Parameters.AddWithValue("@name", name);
        var existing = command.ExecuteScalar();
        if (existing is long id && (!currentRoomId.HasValue || currentRoomId.Value != Convert.ToInt32(id)))
        {
            throw new ConflictProblemException("Комната с таким названием уже существует", "ROOM_NAME_EXISTS");
        }
    }

    private void EnsureSceneNameIsUnique(SqliteConnection connection, string name, int? currentSceneId)
    {
        var command = connection.CreateCommand();
        command.CommandText = "SELECT Id FROM Scenes WHERE lower(Name) = lower(@name) LIMIT 1;";
        command.Parameters.AddWithValue("@name", name);
        var existing = command.ExecuteScalar();
        if (existing is long id && (!currentSceneId.HasValue || currentSceneId.Value != Convert.ToInt32(id)))
        {
            throw new ConflictProblemException("Сценарий с таким названием уже существует", "SCENE_NAME_EXISTS");
        }
    }

    private Dictionary<string, string> DeserializeConnection(string rawJson)
    {
        try
        {
            return JsonSerializer.Deserialize<Dictionary<string, string>>(rawJson, _jsonOptions)
                ?? new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        }
        catch
        {
            return new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        }
    }

    private static DateTime ParseUtc(string raw)
    {
        return DateTime.TryParse(raw, null, System.Globalization.DateTimeStyles.RoundtripKind, out var parsed)
            ? parsed
            : DateTime.UtcNow;
    }

    private static int ExecuteCount(SqliteConnection connection, string sql)
    {
        var command = connection.CreateCommand();
        command.CommandText = sql;
        return Convert.ToInt32(command.ExecuteScalar() ?? 0);
    }

    private SqliteConnection OpenConnection()
    {
        var connection = new SqliteConnection($"Data Source={_databasePath}");
        connection.Open();
        var command = connection.CreateCommand();
        command.CommandText = "PRAGMA foreign_keys = ON;";
        command.ExecuteNonQuery();
        return connection;
    }

    private static string NormalizeRequired(string? value, string message, string code)
    {
        var normalized = value?.Trim();
        if (string.IsNullOrWhiteSpace(normalized))
        {
            throw new ValidationProblemException(message, code);
        }

        return normalized;
    }

    private static string NormalizeOptional(string? value, string fallback)
    {
        return string.IsNullOrWhiteSpace(value) ? fallback : value.Trim();
    }

    private static string? NormalizeIdentifier(string? identifier)
    {
        var normalized = identifier?.Trim();
        return string.IsNullOrWhiteSpace(normalized) ? null : normalized;
    }

    private void EnsureDeviceIdentifierIsUnique(SqliteConnection connection, string? identifier, int? currentDeviceId)
    {
        if (string.IsNullOrWhiteSpace(identifier))
        {
            return;
        }

        var command = connection.CreateCommand();
        command.CommandText = "SELECT Id FROM Devices WHERE lower(Identifier) = lower(@identifier) LIMIT 1;";
        command.Parameters.AddWithValue("@identifier", identifier);
        var existing = command.ExecuteScalar();
        if (existing is long id && (!currentDeviceId.HasValue || currentDeviceId.Value != Convert.ToInt32(id)))
        {
            throw new ConflictProblemException("Устройство с таким идентификатором уже существует", "DEVICE_IDENTIFIER_EXISTS");
        }
    }

    private static ConnectionValidationResult ValidateConnection(string provider, Dictionary<string, string> connection)
    {
        var cleanProvider = NormalizeOptional(provider, "mock").ToLowerInvariant();
        if (cleanProvider == "mock")
        {
            return new ConnectionValidationResult(true, "Локальное устройство подключено");
        }

        if (cleanProvider == "http")
        {
            if (!connection.TryGetValue("url", out var url) || string.IsNullOrWhiteSpace(url))
            {
                return new ConnectionValidationResult(false, "Для HTTP-провайдера требуется поле url");
            }

            try
            {
                using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(3) };
                using var request = new HttpRequestMessage(HttpMethod.Head, url);
                var response = client.Send(request);
                return response.IsSuccessStatusCode
                    ? new ConnectionValidationResult(true, $"HTTP OK ({(int)response.StatusCode})")
                    : new ConnectionValidationResult(false, $"HTTP недоступен ({(int)response.StatusCode})");
            }
            catch (Exception ex)
            {
                return new ConnectionValidationResult(false, $"HTTP ошибка: {ex.Message}");
            }
        }

        if (cleanProvider is "tcp" or "mqtt")
        {
            if (!connection.TryGetValue("host", out var host) || string.IsNullOrWhiteSpace(host))
            {
                return new ConnectionValidationResult(false, "Требуется host");
            }

            if (!connection.TryGetValue("port", out var portRaw) || !int.TryParse(portRaw, out var port))
            {
                return new ConnectionValidationResult(false, "Требуется корректный port");
            }

            try
            {
                using var client = new TcpClient();
                var connectTask = client.ConnectAsync(host, port);
                var finished = connectTask.Wait(TimeSpan.FromSeconds(3));
                return finished && client.Connected
                    ? new ConnectionValidationResult(true, $"TCP-соединение установлено ({host}:{port})")
                    : new ConnectionValidationResult(false, $"Нет связи с {host}:{port}");
            }
            catch (Exception ex)
            {
                return new ConnectionValidationResult(false, $"TCP ошибка: {ex.Message}");
            }
        }

        var hasAnyValue = connection.Values.Any(x => !string.IsNullOrWhiteSpace(x));
        return hasAnyValue
            ? new ConnectionValidationResult(true, "Параметры подключения заполнены")
            : new ConnectionValidationResult(false, "Заполните параметры подключения");
    }

    private void AddColumnIfMissing(SqliteConnection connection, string table, string column, string definition)
    {
        var cmd = connection.CreateCommand();
        cmd.CommandText = $"PRAGMA table_info({table});";
        using var reader = cmd.ExecuteReader();
        while (reader.Read())
        {
            if (string.Equals(reader.GetString(1), column, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }
        }

        var alter = connection.CreateCommand();
        alter.CommandText = $"ALTER TABLE {table} ADD COLUMN {column} {definition};";
        alter.ExecuteNonQuery();
    }

    private void ValidateRulePayload(SqliteConnection connection, int sourceDeviceId, string actionType, int? actionSceneId, int? actionDeviceId, bool? actionTargetIsOn)
    {
        EnsureDevicesExist(connection, new[] { sourceDeviceId });
        if (string.Equals(actionType, "scene", StringComparison.OrdinalIgnoreCase))
        {
            if (!actionSceneId.HasValue)
            {
                throw new ValidationProblemException("Для actionType=scene требуется actionSceneId", "RULE_ACTION_SCENE_REQUIRED");
            }
            _ = GetScene(actionSceneId.Value);
            return;
        }

        if (string.Equals(actionType, "device", StringComparison.OrdinalIgnoreCase))
        {
            if (!actionDeviceId.HasValue || !actionTargetIsOn.HasValue)
            {
                throw new ValidationProblemException("Для actionType=device требуются actionDeviceId и actionTargetIsOn", "RULE_ACTION_DEVICE_REQUIRED");
            }
            EnsureDevicesExist(connection, new[] { actionDeviceId.Value });
            return;
        }

        throw new ValidationProblemException("actionType должен быть scene или device", "RULE_ACTION_INVALID");
    }

    private void ValidateSchedulePayload(SqliteConnection connection, string actionType, int? actionSceneId, int? actionDeviceId, bool? actionTargetIsOn, string timeOfDay)
    {
        _ = TimeOnly.ParseExact(timeOfDay, "HH:mm", CultureInfo.InvariantCulture);
        if (string.Equals(actionType, "scene", StringComparison.OrdinalIgnoreCase))
        {
            if (!actionSceneId.HasValue)
            {
                throw new ValidationProblemException("Для actionType=scene требуется actionSceneId", "SCHEDULE_ACTION_SCENE_REQUIRED");
            }
            _ = GetScene(actionSceneId.Value);
            return;
        }

        if (string.Equals(actionType, "device", StringComparison.OrdinalIgnoreCase))
        {
            if (!actionDeviceId.HasValue || !actionTargetIsOn.HasValue)
            {
                throw new ValidationProblemException("Для actionType=device требуются actionDeviceId и actionTargetIsOn", "SCHEDULE_ACTION_DEVICE_REQUIRED");
            }
            EnsureDevicesExist(connection, new[] { actionDeviceId.Value });
            return;
        }

        throw new ValidationProblemException("actionType должен быть scene или device", "SCHEDULE_ACTION_INVALID");
    }

    private string ExecuteAction(string actionType, int? actionSceneId, int? actionDeviceId, bool? actionTargetIsOn)
    {
        if (string.Equals(actionType, "scene", StringComparison.OrdinalIgnoreCase) && actionSceneId.HasValue)
        {
            var run = RunScene(actionSceneId.Value);
            return $"Запущен сценарий #{actionSceneId.Value} ({run.Status})";
        }

        if (string.Equals(actionType, "device", StringComparison.OrdinalIgnoreCase) && actionDeviceId.HasValue && actionTargetIsOn.HasValue)
        {
            using var db = OpenConnection();
            using var tx = db.BeginTransaction();
            var cmd = db.CreateCommand();
            cmd.Transaction = tx;
            cmd.CommandText = "UPDATE Devices SET IsOn = @isOn, UpdatedAt = @updatedAt WHERE Id = @id;";
            cmd.Parameters.AddWithValue("@isOn", actionTargetIsOn.Value ? 1 : 0);
            cmd.Parameters.AddWithValue("@updatedAt", DateTime.UtcNow.ToString("O"));
            cmd.Parameters.AddWithValue("@id", actionDeviceId.Value);
            if (cmd.ExecuteNonQuery() == 0)
            {
                throw new NotFoundProblemException("Устройство не найдено", "DEVICE_NOT_FOUND");
            }
            LogEvent(db, tx, "info", "automation", "DEVICE_ACTION_EXECUTED", $"Устройство #{actionDeviceId.Value} установлено в {(actionTargetIsOn.Value ? "ON" : "OFF")}", deviceId: actionDeviceId.Value);
            tx.Commit();
            SyncLegacyDevicesJson(db);
            return $"Устройство #{actionDeviceId.Value} -> {(actionTargetIsOn.Value ? "ON" : "OFF")}";
        }

        throw new ValidationProblemException("Некорректная конфигурация действия", "AUTOMATION_ACTION_INVALID");
    }

    private static bool IsRuleMatch(string op, string expectedRaw, string actualRaw)
    {
        var expected = expectedRaw.Trim();
        var actual = actualRaw.Trim();
        var cleanOp = NormalizeOptional(op, "eq").ToLowerInvariant();

        if (double.TryParse(expected, NumberStyles.Any, CultureInfo.InvariantCulture, out var expectedNumber)
            && double.TryParse(actual, NumberStyles.Any, CultureInfo.InvariantCulture, out var actualNumber))
        {
            return cleanOp switch
            {
                "gt" => actualNumber > expectedNumber,
                "gte" => actualNumber >= expectedNumber,
                "lt" => actualNumber < expectedNumber,
                "lte" => actualNumber <= expectedNumber,
                "neq" => Math.Abs(actualNumber - expectedNumber) > 0.0001,
                _ => Math.Abs(actualNumber - expectedNumber) < 0.0001,
            };
        }

        return cleanOp switch
        {
            "contains" => actual.Contains(expected, StringComparison.OrdinalIgnoreCase),
            "neq" => !string.Equals(actual, expected, StringComparison.OrdinalIgnoreCase),
            _ => string.Equals(actual, expected, StringComparison.OrdinalIgnoreCase),
        };
    }

    private static bool IsScheduleDue(ScheduleEntry schedule, DateTime utcNow)
    {
        var days = schedule.DaysOfWeek.Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        var dayIndex = ((int)utcNow.DayOfWeek + 6) % 7 + 1;
        if (days.Length > 0 && !days.Contains(dayIndex.ToString(CultureInfo.InvariantCulture)))
        {
            return false;
        }

        var time = TimeOnly.ParseExact(schedule.TimeOfDay, "HH:mm", CultureInfo.InvariantCulture);
        if (utcNow.Hour != time.Hour || utcNow.Minute != time.Minute)
        {
            return false;
        }

        if (!schedule.LastRunAt.HasValue)
        {
            return true;
        }

        return schedule.LastRunAt.Value.Date < utcNow.Date || schedule.LastRunAt.Value.Hour != utcNow.Hour || schedule.LastRunAt.Value.Minute != utcNow.Minute;
    }

    private static string InferDeviceType(string? name)
    {
        var lowered = (name ?? string.Empty).Trim().ToLowerInvariant();
        if (lowered.Contains("свет") || lowered.Contains("ламп"))
        {
            return "Свет";
        }

        if (lowered.Contains("термо") || lowered.Contains("климат") || lowered.Contains("кондиционер"))
        {
            return "Климат";
        }

        if (lowered.Contains("камер"))
        {
            return "Камера";
        }

        if (lowered.Contains("розет"))
        {
            return "Розетка";
        }

        return "Другое";
    }

    private sealed class LegacyDevice
    {
        public int Id { get; set; }
        public string Name { get; set; } = string.Empty;
        public string Room { get; set; } = string.Empty;
        public bool IsOn { get; set; }
        public string Type { get; set; } = "Другое";
        public string Provider { get; set; } = "mock";
        public Dictionary<string, string>? Connection { get; set; }
    }
}

public sealed record SceneActionInput(int DeviceId, bool TargetIsOn, int SortOrder);
public sealed record ConnectionValidationResult(bool Ok, string Message);
public sealed record RuleEventResult(int CheckedRules, int TriggeredRules, string Message);
public sealed record ScheduleRunResult(int CheckedSchedules, int StartedSchedules, string Message);
