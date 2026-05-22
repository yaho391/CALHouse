using System.Data;
using System.Text.Json;
using CalHouse.Api.Infrastructure;
using CalHouse.Api.Models;
using Microsoft.Data.Sqlite;

namespace CalHouse.Api.Services;

public partial class DeviceStore
{
    private readonly string _databasePath;
    private readonly string _legacyDevicesPath;
    private readonly DeviceCatalogService _catalog;
    private readonly ILogger<DeviceStore> _logger;
    private readonly object _sync = new();
    private readonly JsonSerializerOptions _jsonOptions = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
    };

    public DeviceStore(IWebHostEnvironment environment, DeviceCatalogService catalog, ILogger<DeviceStore> logger)
    {
        _catalog = catalog;
        _logger = logger;

        var appDataDirectory = Path.Combine(environment.ContentRootPath, "App_Data");
        Directory.CreateDirectory(appDataDirectory);

        _databasePath = Path.Combine(appDataDirectory, "calhouse.db");
        _legacyDevicesPath = Path.Combine(appDataDirectory, "devices.json");

        lock (_sync)
        {
            using var connection = OpenConnection();
            InitializeDatabase(connection);
            EnsureAutomationSchema(connection);
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

    public Device AddDevice(
        string name,
        string? roomName,
        int? roomId,
        bool isOn,
        string? type,
        string? provider,
        string? protocol,
        string? channel,
        string? externalId,
        string? manufacturer,
        string? model,
        Dictionary<string, string>? connection)
    {
        var cleanName = NormalizeRequired(name, "Название устройства обязательно", "DEVICE_NAME_REQUIRED");
        var cleanType = NormalizeOptional(type, "Другое");
        var cleanProvider = _catalog.NormalizeProviderCode(provider);
        cleanType = _catalog.NormalizeDeviceTypeCode(cleanType);
        _catalog.EnsureProviderAllowed(cleanType, cleanProvider);
        var cleanProtocol = NormalizeOptional(protocol, _catalog.InferProtocol(cleanProvider));
        var cleanChannel = NormalizeOptional(channel, _catalog.InferChannel(cleanProvider, cleanProtocol));
        var cleanExternalId = NormalizeRequired(externalId, "Идентификатор устройства обязателен", "DEVICE_EXTERNAL_ID_REQUIRED");
        var cleanManufacturer = NormalizeOptional(manufacturer, string.Empty);
        var cleanModel = NormalizeOptional(model, string.Empty);
        var connectionData = NormalizeConnection(connection);

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureDeviceExternalIdIsUnique(db, cleanExternalId, null);
            var connectionCheck = ValidateConnectionInternal(cleanProvider, cleanProtocol, connectionData);
            using var transaction = db.BeginTransaction();
            var resolvedRoomId = ResolveRoomId(db, transaction, roomId, roomName, createIfMissing: true);

            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = @"
INSERT INTO Devices (Name, RoomId, IsOn, Type, Provider, Protocol, Channel, ExternalId, Manufacturer, Model, ConnectionJson, ConnectionStatus, ConnectionMessage, LastConnectionCheckAt, CreatedAt, UpdatedAt)
VALUES (@name, @roomId, @isOn, @type, @provider, @protocol, @channel, @externalId, @manufacturer, @model, @connectionJson, @connectionStatus, @connectionMessage, @lastConnectionCheckAt, @createdAt, @updatedAt);
SELECT last_insert_rowid();";
            var now = DateTime.UtcNow;
            command.Parameters.AddWithValue("@name", cleanName);
            command.Parameters.AddWithValue("@roomId", resolvedRoomId);
            command.Parameters.AddWithValue("@isOn", isOn ? 1 : 0);
            command.Parameters.AddWithValue("@type", cleanType);
            command.Parameters.AddWithValue("@provider", cleanProvider);
            command.Parameters.AddWithValue("@protocol", cleanProtocol);
            command.Parameters.AddWithValue("@channel", cleanChannel);
            command.Parameters.AddWithValue("@externalId", cleanExternalId);
            command.Parameters.AddWithValue("@manufacturer", cleanManufacturer);
            command.Parameters.AddWithValue("@model", cleanModel);
            command.Parameters.AddWithValue("@connectionJson", JsonSerializer.Serialize(connectionData, _jsonOptions));
            command.Parameters.AddWithValue("@connectionStatus", connectionCheck.Status);
            command.Parameters.AddWithValue("@connectionMessage", connectionCheck.Message);
            command.Parameters.AddWithValue("@lastConnectionCheckAt", now.ToString("O"));
            command.Parameters.AddWithValue("@createdAt", now.ToString("O"));
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            var insertedId = Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));

            LogEvent(db, transaction, "info", "api", "DEVICE_CREATED", $"Создано устройство «{cleanName}» со статусом «{connectionCheck.Status}»", deviceId: insertedId, roomId: resolvedRoomId);
            transaction.Commit();

            SyncLegacyDevicesJson(db);
            return ReadDeviceOrThrow(db, insertedId);
        }
    }

    public Device UpdateDevice(
        int id,
        string? name,
        string? roomName,
        int? roomId,
        bool? isOn,
        string? type,
        string? provider,
        string? protocol,
        string? channel,
        string? externalId,
        string? manufacturer,
        string? model,
        Dictionary<string, string>? connection)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var current = ReadDeviceOrThrow(db, id);
            using var transaction = db.BeginTransaction();

            var finalName = string.IsNullOrWhiteSpace(name) ? current.Name : NormalizeRequired(name, "Название устройства обязательно", "DEVICE_NAME_REQUIRED");
            var finalType = string.IsNullOrWhiteSpace(type) ? current.Type : NormalizeOptional(type, current.Type);
            var finalProvider = string.IsNullOrWhiteSpace(provider) ? _catalog.NormalizeProviderCode(current.Provider) : _catalog.NormalizeProviderCode(provider);
            finalType = _catalog.NormalizeDeviceTypeCode(finalType);
            _catalog.EnsureProviderAllowed(finalType, finalProvider);
            var finalProtocol = protocol is null ? current.Protocol : NormalizeOptional(protocol, _catalog.InferProtocol(finalProvider));
            var finalChannel = channel is null ? current.Channel : NormalizeOptional(channel, _catalog.InferChannel(finalProvider, finalProtocol));
            var finalExternalId = string.IsNullOrWhiteSpace(externalId) ? current.ExternalId : NormalizeRequired(externalId, "Идентификатор устройства обязателен", "DEVICE_EXTERNAL_ID_REQUIRED");
            var finalManufacturer = manufacturer is null ? current.Manufacturer : NormalizeOptional(manufacturer, string.Empty);
            var finalModel = model is null ? current.Model : NormalizeOptional(model, string.Empty);
            var finalConnection = connection is null ? current.Connection : NormalizeConnection(connection);
            var finalIsOn = isOn ?? current.IsOn;
            var finalRoomId = ResolveRoomId(db, transaction, roomId ?? current.RoomId, roomName, createIfMissing: !string.IsNullOrWhiteSpace(roomName));
            var now = DateTime.UtcNow;
            EnsureDeviceExternalIdIsUnique(db, finalExternalId, id);
            var connectionCheck = ValidateConnectionInternal(finalProvider, finalProtocol, finalConnection);

            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = @"
UPDATE Devices
SET Name = @name,
    RoomId = @roomId,
    IsOn = @isOn,
    Type = @type,
    Provider = @provider,
    Protocol = @protocol,
    Channel = @channel,
    ExternalId = @externalId,
    Manufacturer = @manufacturer,
    Model = @model,
    ConnectionJson = @connectionJson,
    ConnectionStatus = @connectionStatus,
    ConnectionMessage = @connectionMessage,
    LastConnectionCheckAt = @lastConnectionCheckAt,
    UpdatedAt = @updatedAt
WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@name", finalName);
            command.Parameters.AddWithValue("@roomId", (object?)finalRoomId ?? DBNull.Value);
            command.Parameters.AddWithValue("@isOn", finalIsOn ? 1 : 0);
            command.Parameters.AddWithValue("@type", finalType);
            command.Parameters.AddWithValue("@provider", finalProvider);
            command.Parameters.AddWithValue("@protocol", finalProtocol);
            command.Parameters.AddWithValue("@channel", finalChannel);
            command.Parameters.AddWithValue("@externalId", finalExternalId);
            command.Parameters.AddWithValue("@manufacturer", finalManufacturer);
            command.Parameters.AddWithValue("@model", finalModel);
            command.Parameters.AddWithValue("@connectionJson", JsonSerializer.Serialize(finalConnection, _jsonOptions));
            command.Parameters.AddWithValue("@connectionStatus", connectionCheck.Status);
            command.Parameters.AddWithValue("@connectionMessage", connectionCheck.Message);
            command.Parameters.AddWithValue("@lastConnectionCheckAt", now.ToString("O"));
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            command.ExecuteNonQuery();

            LogEvent(db, transaction, "info", "api", "DEVICE_UPDATED", $"Обновлено устройство «{finalName}» со статусом «{connectionCheck.Status}»", deviceId: id, roomId: finalRoomId);
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
            var commandResult = ExecuteDeviceStateCommand(current, nextState);
            var now = DateTime.UtcNow;

            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = @"
UPDATE Devices
SET IsOn = @isOn,
    ConnectionStatus = @connectionStatus,
    ConnectionMessage = @connectionMessage,
    LastConnectionCheckAt = @lastConnectionCheckAt,
    UpdatedAt = @updatedAt
WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@isOn", commandResult.Ok ? (nextState ? 1 : 0) : (current.IsOn ? 1 : 0));
            command.Parameters.AddWithValue("@connectionStatus", commandResult.Status);
            command.Parameters.AddWithValue("@connectionMessage", commandResult.Message);
            command.Parameters.AddWithValue("@lastConnectionCheckAt", now.ToString("O"));
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            command.ExecuteNonQuery();

            LogEvent(
                db,
                transaction,
                commandResult.Ok ? "info" : "warning",
                "api",
                commandResult.Ok ? "DEVICE_TOGGLED" : "DEVICE_TOGGLE_FAILED",
                commandResult.Ok
                    ? $"Устройство «{current.Name}» переключено в {(nextState ? "ON" : "OFF")}. {commandResult.Message}"
                    : $"Не удалось переключить устройство «{current.Name}» в {(nextState ? "ON" : "OFF")}: {commandResult.Message}",
                deviceId: id,
                roomId: current.RoomId);
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

            var failures = new List<string>();
            foreach (var action in scene.Actions.OrderBy(x => x.SortOrder))
            {
                var device = ReadDeviceOrThrow(db, action.DeviceId);
                var commandResult = ExecuteDeviceStateCommand(device, action.TargetIsOn);
                UpdateDeviceStateAfterCommand(db, transaction, device, action.TargetIsOn, commandResult);
                if (!commandResult.Ok)
                {
                    failures.Add($"{action.DeviceName}: {commandResult.Message}");
                }

                LogEvent(
                    db,
                    transaction,
                    commandResult.Ok ? "info" : "warning",
                    "scene-engine",
                    commandResult.Ok ? "SCENE_DEVICE_ACTION_APPLIED" : "SCENE_DEVICE_ACTION_FAILED",
                    commandResult.Ok
                        ? $"Сценарий «{scene.Name}» установил устройство «{action.DeviceName}» в состояние {(action.TargetIsOn ? "ON" : "OFF")}. {commandResult.Message}"
                        : $"Сценарий «{scene.Name}» не смог установить устройство «{action.DeviceName}» в состояние {(action.TargetIsOn ? "ON" : "OFF")}: {commandResult.Message}",
                    deviceId: action.DeviceId,
                    sceneId: id,
                    runId: runId);
            }

            var completedAt = DateTime.UtcNow;
            var runStatus = failures.Count == 0 ? "completed" : "failed";
            var message = failures.Count == 0
                ? $"Сценарий «{scene.Name}» успешно выполнен. Действий: {scene.Actions.Count}"
                : $"Сценарий «{scene.Name}» завершился с ошибками: {string.Join("; ", failures)}";

            var finishRun = db.CreateCommand();
            finishRun.Transaction = transaction;
            finishRun.CommandText = @"
UPDATE SceneRuns
SET CompletedAt = @completedAt,
    Status = @status,
    Message = @message
WHERE Id = @id;";
            finishRun.Parameters.AddWithValue("@completedAt", completedAt.ToString("O"));
            finishRun.Parameters.AddWithValue("@status", runStatus);
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
            updateScene.Parameters.AddWithValue("@lastRunStatus", runStatus);
            updateScene.Parameters.AddWithValue("@lastRunMessage", message);
            updateScene.Parameters.AddWithValue("@updatedAt", completedAt.ToString("O"));
            updateScene.Parameters.AddWithValue("@sceneId", id);
            updateScene.ExecuteNonQuery();

            LogEvent(db, transaction, failures.Count == 0 ? "info" : "warning", "scene-engine", failures.Count == 0 ? "SCENE_RUN_COMPLETED" : "SCENE_RUN_FAILED", message, sceneId: id, runId: runId);
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
       d.Protocol,
       d.Channel,
       COALESCE(d.ExternalId, ''),
       COALESCE(d.Manufacturer, ''),
       COALESCE(d.Model, ''),
       d.ConnectionJson,
       COALESCE(d.ConnectionStatus, 'unknown'),
       COALESCE(d.ConnectionMessage, ''),
       d.LastConnectionCheckAt,
       d.LastSeenAt,
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
                Protocol = reader.GetString(7),
                Channel = reader.GetString(8),
                ExternalId = reader.GetString(9),
                Manufacturer = reader.GetString(10),
                Model = reader.GetString(11),
                Connection = DeserializeConnection(reader.GetString(12)),
                ConnectionStatus = reader.GetString(13),
                ConnectionMessage = reader.GetString(14),
                LastConnectionCheckAt = reader.IsDBNull(15) ? null : ParseUtc(reader.GetString(15)),
                LastSeenAt = reader.IsDBNull(16) ? null : ParseUtc(reader.GetString(16)),
                CreatedAt = ParseUtc(reader.GetString(17)),
                UpdatedAt = ParseUtc(reader.GetString(18)),
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
       d.Protocol,
       d.Channel,
       COALESCE(d.ExternalId, ''),
       COALESCE(d.Manufacturer, ''),
       COALESCE(d.Model, ''),
       d.ConnectionJson,
       COALESCE(d.ConnectionStatus, 'unknown'),
       COALESCE(d.ConnectionMessage, ''),
       d.LastConnectionCheckAt,
       d.LastSeenAt,
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
            Protocol = reader.GetString(7),
            Channel = reader.GetString(8),
            ExternalId = reader.GetString(9),
            Manufacturer = reader.GetString(10),
            Model = reader.GetString(11),
            Connection = DeserializeConnection(reader.GetString(12)),
            ConnectionStatus = reader.GetString(13),
            ConnectionMessage = reader.GetString(14),
            LastConnectionCheckAt = reader.IsDBNull(15) ? null : ParseUtc(reader.GetString(15)),
            LastSeenAt = reader.IsDBNull(16) ? null : ParseUtc(reader.GetString(16)),
            CreatedAt = ParseUtc(reader.GetString(17)),
            UpdatedAt = ParseUtc(reader.GetString(18)),
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
INSERT INTO Devices (Name, RoomId, IsOn, Type, Provider, Protocol, Channel, ExternalId, Manufacturer, Model, ConnectionJson, ConnectionStatus, ConnectionMessage, LastConnectionCheckAt, CreatedAt, UpdatedAt)
VALUES (@name, @roomId, @isOn, @type, @provider, @protocol, @channel, @externalId, @manufacturer, @model, @connectionJson, @connectionStatus, @connectionMessage, @lastConnectionCheckAt, @createdAt, @updatedAt);
SELECT last_insert_rowid();";
        command.Parameters.AddWithValue("@name", name);
        command.Parameters.AddWithValue("@roomId", roomId);
        command.Parameters.AddWithValue("@isOn", isOn ? 1 : 0);
        command.Parameters.AddWithValue("@type", type);
        command.Parameters.AddWithValue("@provider", provider);
        command.Parameters.AddWithValue("@protocol", InferProtocol(provider));
        command.Parameters.AddWithValue("@channel", InferChannel(InferProtocol(provider)));
        command.Parameters.AddWithValue("@externalId", $"legacy-{Guid.NewGuid():N}"[..18]);
        command.Parameters.AddWithValue("@manufacturer", string.Empty);
        command.Parameters.AddWithValue("@model", string.Empty);
        command.Parameters.AddWithValue("@connectionJson", JsonSerializer.Serialize(connectionData, _jsonOptions));
        command.Parameters.AddWithValue("@connectionStatus", provider == "mock" ? "connected" : "unknown");
        command.Parameters.AddWithValue("@connectionMessage", provider == "mock" ? "Локальное устройство" : "Импортировано без проверки связи");
        command.Parameters.AddWithValue("@lastConnectionCheckAt", now.ToString("O"));
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
        public string Protocol { get; set; } = "manual";
        public string Channel { get; set; } = "local";
        public string ExternalId { get; set; } = string.Empty;
        public string Manufacturer { get; set; } = string.Empty;
        public string Model { get; set; } = string.Empty;
        public Dictionary<string, string>? Connection { get; set; }
    }
}

public sealed record SceneActionInput(int DeviceId, bool TargetIsOn, int SortOrder);
