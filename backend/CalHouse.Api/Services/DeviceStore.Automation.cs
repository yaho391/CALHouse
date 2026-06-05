using System.Globalization;
using System.Net.Http;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using CalHouse.Api.Infrastructure;
using CalHouse.Api.Models;
using Microsoft.Data.Sqlite;

namespace CalHouse.Api.Services;

public partial class DeviceStore
{
    private static readonly string[] SupportedDeviceTypes = ["Свет", "Климат", "Камера", "Розетка", "Датчик", "Замок", "Штора", "Другое"];
    private static readonly string[] SupportedProviders = ["mock", "demo", "shelly", "tasmota", "mqtt", "zigbee2mqtt", "homeassistant", "http", "camera", "custom"];
    private static readonly string[] SupportedProtocols = ["manual", "demo", "http", "https", "mqtt", "tcp", "rtsp"];
    private static readonly string[] SupportedRuleOperators = ["=", "!=", ">", ">=", "<", "<=", "contains"];
    private static readonly string[] SupportedActionKinds = ["device_state", "scene_run"];
    private static readonly string[] BooleanEventTypes = ["motion", "smoke", "water_leak", "door_open", "online", "offline"];
    private static readonly string[] NumericEventTypes = ["temperature", "humidity", "battery"];
    private static readonly string[] TextEventTypes = ["power", "button_click", "state"];
    private static readonly string[] SupportedEventTypes = [.. BooleanEventTypes, .. NumericEventTypes, .. TextEventTypes];

    public object GetDeviceCatalog()
    {
        return new
        {
            deviceTypes = SupportedDeviceTypes,
            providers = new[]
            {
                new { key = "mock", title = "Локальное / тестовое", protocol = "manual", channel = "local", requiredFields = Array.Empty<string>(), testMode = "local", note = "Для демонстрации и локальных сценариев" },
                new { key = "shelly", title = "Shelly", protocol = "http", channel = "wifi", requiredFields = new[] { "host" }, testMode = "http", note = "Проверяется HTTP доступность устройства" },
                new { key = "tasmota", title = "Tasmota", protocol = "http", channel = "wifi", requiredFields = new[] { "host" }, testMode = "http", note = "Подходит для устройств с web API" },
                new { key = "homeassistant", title = "Home Assistant entity", protocol = "http", channel = "lan", requiredFields = new[] { "url", "token", "entity_id" }, testMode = "http", note = "Интеграция через Home Assistant API" },
                new { key = "mqtt", title = "MQTT устройство", protocol = "mqtt", channel = "mqtt", requiredFields = new[] { "host", "port", "topic" }, testMode = "tcp", note = "Проверяется доступность брокера" },
                new { key = "zigbee2mqtt", title = "Zigbee2MQTT", protocol = "mqtt", channel = "zigbee", requiredFields = new[] { "host", "port", "topic" }, testMode = "tcp", note = "Реальные Zigbee устройства через MQTT" },
                new { key = "camera", title = "IP-камера", protocol = "rtsp", channel = "lan", requiredFields = new[] { "host", "port" }, testMode = "tcp", note = "Проверяется сетевой порт камеры" },
                new { key = "http", title = "Custom HTTP", protocol = "http", channel = "lan", requiredFields = new[] { "url" }, testMode = "http", note = "Подходит для произвольных HTTP устройств" },
                new { key = "custom", title = "Custom TCP", protocol = "tcp", channel = "lan", requiredFields = new[] { "host", "port" }, testMode = "tcp", note = "Подходит для произвольных TCP устройств" },
            },
            ruleOperators = SupportedRuleOperators,
            actionKinds = SupportedActionKinds,
            scheduleDays = new[]
            {
                new { value = 1, title = "Пн" },
                new { value = 2, title = "Вт" },
                new { value = 3, title = "Ср" },
                new { value = 4, title = "Чт" },
                new { value = 5, title = "Пт" },
                new { value = 6, title = "Сб" },
                new { value = 7, title = "Вс" },
            }
        };
    }

    public object ValidateConnection(string? provider, string? protocol, Dictionary<string, string>? connection)
    {
        var cleanProvider = _catalog.NormalizeProviderCode(provider);
        var result = ValidateConnectionInternal(cleanProvider, NormalizeProtocol(NormalizeOptional(protocol, _catalog.InferProtocol(cleanProvider))), NormalizeConnection(connection));
        return new
        {
            ok = result.Ok,
            status = result.Status,
            message = result.Message,
            normalizedConnection = result.Connection,
        };
    }

    public IReadOnlyList<AutomationRule> GetAllRules()
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            return ReadRules(db, null);
        }
    }

    public AutomationRule GetRule(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            return ReadRules(db, id).FirstOrDefault() ?? throw new NotFoundProblemException("Правило не найдено", "RULE_NOT_FOUND");
        }
    }

    public AutomationRule CreateRule(
        string name,
        string? description,
        bool isEnabled,
        int triggerDeviceId,
        string eventType,
        string comparisonOperator,
        string compareValue,
        string actionKind,
        int? actionDeviceId,
        bool? actionTargetIsOn,
        int? actionSceneId)
    {
        var cleanName = NormalizeSafeTextRequired(name, "Название правила", 3, MaxNameLength, "RULE_NAME_REQUIRED", "RULE_NAME_INVALID");
        var cleanDescription = NormalizeFreeTextOptional(description, "Описание правила", MaxDescriptionLength, "RULE_DESCRIPTION_INVALID");
        var cleanEventType = NormalizeCodeValue(eventType, "Тип события обязателен", "RULE_EVENT_TYPE_REQUIRED", MaxChannelLength, "Тип события может содержать только латиницу, цифры, точку, дефис и подчёркивание", "RULE_EVENT_TYPE_INVALID");
        var cleanOperator = NormalizeRequired(comparisonOperator, "Оператор сравнения обязателен", "RULE_OPERATOR_REQUIRED");
        var cleanCompareValue = NormalizeRequiredBounded(compareValue, "Значение условия обязательно", "RULE_COMPARE_VALUE_REQUIRED", MaxEventValueLength, "Значение условия слишком длинное", "RULE_COMPARE_VALUE_TOO_LONG");
        var cleanActionKind = NormalizeRequired(actionKind, "Тип действия обязателен", "RULE_ACTION_KIND_REQUIRED");

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            EnsureRuleNameIsUnique(db, cleanName, null);
            EnsurePositiveId(triggerDeviceId, "Источник события выбран некорректно", "RULE_TRIGGER_DEVICE_INVALID");
            var sourceDevice = ReadDeviceOrThrow(db, triggerDeviceId);
            EnsureDeviceCanEmitEvent(sourceDevice, cleanEventType);
            ValidateActionTarget(db, cleanActionKind, actionDeviceId, actionTargetIsOn, actionSceneId);
            ValidateRuleOperator(cleanOperator);
            ValidateEventValue(cleanEventType, cleanCompareValue, "Значение условия", "RULE_COMPARE_VALUE_INVALID");
            ValidateRuleOperatorForEvent(cleanEventType, cleanOperator);

            using var transaction = db.BeginTransaction();
            var now = DateTime.UtcNow;
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = @"
INSERT INTO AutomationRules
(Name, Description, IsEnabled, TriggerDeviceId, TriggerEventType, ComparisonOperator, CompareValue, ActionKind, ActionDeviceId, ActionTargetIsOn, ActionSceneId, CreatedAt, UpdatedAt, LastTriggeredAt, LastTriggerStatus, LastTriggerMessage)
VALUES
(@name, @description, @isEnabled, @triggerDeviceId, @triggerEventType, @comparisonOperator, @compareValue, @actionKind, @actionDeviceId, @actionTargetIsOn, @actionSceneId, @createdAt, @updatedAt, NULL, NULL, NULL);
SELECT last_insert_rowid();";
            command.Parameters.AddWithValue("@name", cleanName);
            command.Parameters.AddWithValue("@description", cleanDescription);
            command.Parameters.AddWithValue("@isEnabled", isEnabled ? 1 : 0);
            command.Parameters.AddWithValue("@triggerDeviceId", triggerDeviceId);
            command.Parameters.AddWithValue("@triggerEventType", cleanEventType);
            command.Parameters.AddWithValue("@comparisonOperator", cleanOperator);
            command.Parameters.AddWithValue("@compareValue", cleanCompareValue);
            command.Parameters.AddWithValue("@actionKind", cleanActionKind);
            command.Parameters.AddWithValue("@actionDeviceId", (object?)actionDeviceId ?? DBNull.Value);
            command.Parameters.AddWithValue("@actionTargetIsOn", actionTargetIsOn.HasValue ? (object)(actionTargetIsOn.Value ? 1 : 0) : DBNull.Value);
            command.Parameters.AddWithValue("@actionSceneId", (object?)actionSceneId ?? DBNull.Value);
            command.Parameters.AddWithValue("@createdAt", now.ToString("O"));
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            var id = Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));

            LogEvent(db, transaction, "info", "automation", "RULE_CREATED", $"Создано правило «{cleanName}»", sceneId: actionSceneId, deviceId: actionDeviceId ?? triggerDeviceId);
            transaction.Commit();
            return GetRule(id);
        }
    }

    public AutomationRule UpdateRule(
        int id,
        string name,
        string? description,
        bool isEnabled,
        int triggerDeviceId,
        string eventType,
        string comparisonOperator,
        string compareValue,
        string actionKind,
        int? actionDeviceId,
        bool? actionTargetIsOn,
        int? actionSceneId)
    {
        var cleanName = NormalizeSafeTextRequired(name, "Название правила", 3, MaxNameLength, "RULE_NAME_REQUIRED", "RULE_NAME_INVALID");
        var cleanDescription = NormalizeFreeTextOptional(description, "Описание правила", MaxDescriptionLength, "RULE_DESCRIPTION_INVALID");
        var cleanEventType = NormalizeCodeValue(eventType, "Тип события обязателен", "RULE_EVENT_TYPE_REQUIRED", MaxChannelLength, "Тип события может содержать только латиницу, цифры, точку, дефис и подчёркивание", "RULE_EVENT_TYPE_INVALID");
        var cleanOperator = NormalizeRequired(comparisonOperator, "Оператор сравнения обязателен", "RULE_OPERATOR_REQUIRED");
        var cleanCompareValue = NormalizeRequiredBounded(compareValue, "Значение условия обязательно", "RULE_COMPARE_VALUE_REQUIRED", MaxEventValueLength, "Значение условия слишком длинное", "RULE_COMPARE_VALUE_TOO_LONG");
        var cleanActionKind = NormalizeRequired(actionKind, "Тип действия обязателен", "RULE_ACTION_KIND_REQUIRED");

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            _ = GetRule(id);
            EnsureRuleNameIsUnique(db, cleanName, id);
            EnsurePositiveId(triggerDeviceId, "Источник события выбран некорректно", "RULE_TRIGGER_DEVICE_INVALID");
            var sourceDevice = ReadDeviceOrThrow(db, triggerDeviceId);
            EnsureDeviceCanEmitEvent(sourceDevice, cleanEventType);
            ValidateActionTarget(db, cleanActionKind, actionDeviceId, actionTargetIsOn, actionSceneId);
            ValidateRuleOperator(cleanOperator);
            ValidateEventValue(cleanEventType, cleanCompareValue, "Значение условия", "RULE_COMPARE_VALUE_INVALID");
            ValidateRuleOperatorForEvent(cleanEventType, cleanOperator);

            using var transaction = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = @"
UPDATE AutomationRules
SET Name = @name,
    Description = @description,
    IsEnabled = @isEnabled,
    TriggerDeviceId = @triggerDeviceId,
    TriggerEventType = @triggerEventType,
    ComparisonOperator = @comparisonOperator,
    CompareValue = @compareValue,
    ActionKind = @actionKind,
    ActionDeviceId = @actionDeviceId,
    ActionTargetIsOn = @actionTargetIsOn,
    ActionSceneId = @actionSceneId,
    UpdatedAt = @updatedAt
WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@name", cleanName);
            command.Parameters.AddWithValue("@description", cleanDescription);
            command.Parameters.AddWithValue("@isEnabled", isEnabled ? 1 : 0);
            command.Parameters.AddWithValue("@triggerDeviceId", triggerDeviceId);
            command.Parameters.AddWithValue("@triggerEventType", cleanEventType);
            command.Parameters.AddWithValue("@comparisonOperator", cleanOperator);
            command.Parameters.AddWithValue("@compareValue", cleanCompareValue);
            command.Parameters.AddWithValue("@actionKind", cleanActionKind);
            command.Parameters.AddWithValue("@actionDeviceId", (object?)actionDeviceId ?? DBNull.Value);
            command.Parameters.AddWithValue("@actionTargetIsOn", actionTargetIsOn.HasValue ? (object)(actionTargetIsOn.Value ? 1 : 0) : DBNull.Value);
            command.Parameters.AddWithValue("@actionSceneId", (object?)actionSceneId ?? DBNull.Value);
            command.Parameters.AddWithValue("@updatedAt", DateTime.UtcNow.ToString("O"));
            command.ExecuteNonQuery();

            LogEvent(db, transaction, "info", "automation", "RULE_UPDATED", $"Обновлено правило «{cleanName}»", sceneId: actionSceneId, deviceId: actionDeviceId ?? triggerDeviceId);
            transaction.Commit();
            return GetRule(id);
        }
    }

    public AutomationRule SetRuleEnabled(int id, bool isEnabled)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            var rule = GetRule(id);
            using var transaction = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "UPDATE AutomationRules SET IsEnabled = @isEnabled, UpdatedAt = @updatedAt WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@isEnabled", isEnabled ? 1 : 0);
            command.Parameters.AddWithValue("@updatedAt", DateTime.UtcNow.ToString("O"));
            command.ExecuteNonQuery();
            LogEvent(db, transaction, "info", "automation", isEnabled ? "RULE_ENABLED" : "RULE_DISABLED", $"Правило «{rule.Name}» {(isEnabled ? "включено" : "выключено")}", deviceId: rule.TriggerDeviceId, sceneId: rule.ActionSceneId);
            transaction.Commit();
            return GetRule(id);
        }
    }

    public void DeleteRule(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            var rule = GetRule(id);
            using var transaction = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "DELETE FROM AutomationRules WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.ExecuteNonQuery();
            LogEvent(db, transaction, "info", "automation", "RULE_DELETED", $"Удалено правило «{rule.Name}»", deviceId: rule.TriggerDeviceId, sceneId: rule.ActionSceneId);
            transaction.Commit();
        }
    }

    public IReadOnlyList<RuleRun> GetRuleRuns(int ruleId, int limit = 20)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            _ = GetRule(ruleId);
            return ReadRuleRuns(db, ruleId, limit);
        }
    }

    public DeviceEventResult ProcessIncomingEvent(int? deviceId, string? deviceExternalId, string eventType, string value, string? message = null)
    {
        var cleanEventType = NormalizeEventTypeAlias(NormalizeCodeValue(eventType, "Тип события обязателен", "EVENT_TYPE_REQUIRED", MaxChannelLength, "Тип события может содержать только латиницу, цифры, точку, дефис и подчёркивание", "EVENT_TYPE_INVALID"));
        var cleanValue = NormalizeRequiredBounded(value, "Значение события обязательно", "EVENT_VALUE_REQUIRED", MaxEventValueLength, "Значение события слишком длинное", "EVENT_VALUE_TOO_LONG");
        var cleanMessage = NormalizeFreeTextOptional(message, "Сообщение события", 1000, "EVENT_MESSAGE_INVALID");

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            var sourceDevice = ResolveDeviceByReference(db, deviceId, deviceExternalId);
            EnsureDeviceCanEmitEvent(sourceDevice, cleanEventType);
            ValidateEventValue(cleanEventType, cleanValue, "Значение события", "EVENT_VALUE_INVALID");
            using var transaction = db.BeginTransaction();
            var now = DateTime.UtcNow;

            var touchDevice = db.CreateCommand();
            touchDevice.Transaction = transaction;
            touchDevice.CommandText = "UPDATE Devices SET LastSeenAt = @lastSeenAt, ConnectionStatus = @connectionStatus, ConnectionMessage = @connectionMessage, UpdatedAt = @updatedAt WHERE Id = @id;";
            touchDevice.Parameters.AddWithValue("@lastSeenAt", now.ToString("O"));
            touchDevice.Parameters.AddWithValue("@connectionStatus", "connected");
            touchDevice.Parameters.AddWithValue("@connectionMessage", string.IsNullOrWhiteSpace(cleanMessage) ? $"Получено событие {cleanEventType}" : cleanMessage);
            touchDevice.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            touchDevice.Parameters.AddWithValue("@id", sourceDevice.Id);
            touchDevice.ExecuteNonQuery();

            LogEvent(db, transaction, "info", "event-ingest", "DEVICE_EVENT_RECEIVED", $"Событие «{cleanEventType}={cleanValue}» от устройства «{sourceDevice.Name}»", deviceId: sourceDevice.Id, roomId: sourceDevice.RoomId);

            var rules = ReadEnabledRulesForEvent(db, sourceDevice.Id, cleanEventType);
            var triggered = new List<RuleRun>();
            foreach (var rule in rules)
            {
                if (!RuleMatches(rule, cleanValue))
                {
                    continue;
                }

                var run = ExecuteRuleInternal(db, transaction, rule, sourceDevice, cleanEventType, cleanValue);
                triggered.Add(run);
            }

            transaction.Commit();
            SyncLegacyDevicesJson(db);

            return new DeviceEventResult
            {
                SourceDeviceId = sourceDevice.Id,
                SourceDeviceName = sourceDevice.Name,
                EventType = cleanEventType,
                EventValue = cleanValue,
                TriggeredRules = triggered,
                Message = triggered.Count == 0 ? "Подходящих правил не найдено" : $"Сработало правил: {triggered.Count}",
            };
        }
    }

    public IReadOnlyList<ScheduleEntry> GetAllSchedules()
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            return ReadSchedules(db, null);
        }
    }

    public ScheduleEntry GetSchedule(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            return ReadSchedules(db, id).FirstOrDefault() ?? throw new NotFoundProblemException("Расписание не найдено", "SCHEDULE_NOT_FOUND");
        }
    }

    public ScheduleEntry CreateSchedule(
        string name,
        string? description,
        bool isEnabled,
        string timeOfDay,
        IReadOnlyList<int>? daysOfWeek,
        string actionKind,
        int? actionDeviceId,
        bool? actionTargetIsOn,
        int? actionSceneId)
    {
        var cleanName = NormalizeSafeTextRequired(name, "Название расписания", 3, MaxNameLength, "SCHEDULE_NAME_REQUIRED", "SCHEDULE_NAME_INVALID");
        var cleanDescription = NormalizeFreeTextOptional(description, "Описание расписания", MaxDescriptionLength, "SCHEDULE_DESCRIPTION_INVALID");
        var cleanTime = NormalizeTimeOfDay(timeOfDay);
        var cleanActionKind = NormalizeRequired(actionKind, "Тип действия обязателен", "SCHEDULE_ACTION_KIND_REQUIRED");
        var cleanDays = NormalizeDaysOfWeek(daysOfWeek);

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            EnsureScheduleNameIsUnique(db, cleanName, null);
            ValidateActionTarget(db, cleanActionKind, actionDeviceId, actionTargetIsOn, actionSceneId);

            using var transaction = db.BeginTransaction();
            var now = DateTime.UtcNow;
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = @"
INSERT INTO Schedules
(Name, Description, IsEnabled, TimeOfDay, DaysOfWeek, ActionKind, ActionDeviceId, ActionTargetIsOn, ActionSceneId, CreatedAt, UpdatedAt, LastRunAt, LastRunStatus, LastRunMessage, LastTriggeredSlot)
VALUES
(@name, @description, @isEnabled, @timeOfDay, @daysOfWeek, @actionKind, @actionDeviceId, @actionTargetIsOn, @actionSceneId, @createdAt, @updatedAt, NULL, NULL, NULL, '');
SELECT last_insert_rowid();";
            command.Parameters.AddWithValue("@name", cleanName);
            command.Parameters.AddWithValue("@description", cleanDescription);
            command.Parameters.AddWithValue("@isEnabled", isEnabled ? 1 : 0);
            command.Parameters.AddWithValue("@timeOfDay", cleanTime);
            command.Parameters.AddWithValue("@daysOfWeek", SerializeDays(cleanDays));
            command.Parameters.AddWithValue("@actionKind", cleanActionKind);
            command.Parameters.AddWithValue("@actionDeviceId", (object?)actionDeviceId ?? DBNull.Value);
            command.Parameters.AddWithValue("@actionTargetIsOn", actionTargetIsOn.HasValue ? (object)(actionTargetIsOn.Value ? 1 : 0) : DBNull.Value);
            command.Parameters.AddWithValue("@actionSceneId", (object?)actionSceneId ?? DBNull.Value);
            command.Parameters.AddWithValue("@createdAt", now.ToString("O"));
            command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            var id = Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));

            LogEvent(db, transaction, "info", "scheduler", "SCHEDULE_CREATED", $"Создано расписание «{cleanName}»", deviceId: actionDeviceId, sceneId: actionSceneId);
            transaction.Commit();
            return GetSchedule(id);
        }
    }

    public ScheduleEntry UpdateSchedule(
        int id,
        string name,
        string? description,
        bool isEnabled,
        string timeOfDay,
        IReadOnlyList<int>? daysOfWeek,
        string actionKind,
        int? actionDeviceId,
        bool? actionTargetIsOn,
        int? actionSceneId)
    {
        var cleanName = NormalizeSafeTextRequired(name, "Название расписания", 3, MaxNameLength, "SCHEDULE_NAME_REQUIRED", "SCHEDULE_NAME_INVALID");
        var cleanDescription = NormalizeFreeTextOptional(description, "Описание расписания", MaxDescriptionLength, "SCHEDULE_DESCRIPTION_INVALID");
        var cleanTime = NormalizeTimeOfDay(timeOfDay);
        var cleanActionKind = NormalizeRequired(actionKind, "Тип действия обязателен", "SCHEDULE_ACTION_KIND_REQUIRED");
        var cleanDays = NormalizeDaysOfWeek(daysOfWeek);

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            _ = GetSchedule(id);
            EnsureScheduleNameIsUnique(db, cleanName, id);
            ValidateActionTarget(db, cleanActionKind, actionDeviceId, actionTargetIsOn, actionSceneId);

            using var transaction = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = @"
UPDATE Schedules
SET Name = @name,
    Description = @description,
    IsEnabled = @isEnabled,
    TimeOfDay = @timeOfDay,
    DaysOfWeek = @daysOfWeek,
    ActionKind = @actionKind,
    ActionDeviceId = @actionDeviceId,
    ActionTargetIsOn = @actionTargetIsOn,
    ActionSceneId = @actionSceneId,
    UpdatedAt = @updatedAt
WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@name", cleanName);
            command.Parameters.AddWithValue("@description", cleanDescription);
            command.Parameters.AddWithValue("@isEnabled", isEnabled ? 1 : 0);
            command.Parameters.AddWithValue("@timeOfDay", cleanTime);
            command.Parameters.AddWithValue("@daysOfWeek", SerializeDays(cleanDays));
            command.Parameters.AddWithValue("@actionKind", cleanActionKind);
            command.Parameters.AddWithValue("@actionDeviceId", (object?)actionDeviceId ?? DBNull.Value);
            command.Parameters.AddWithValue("@actionTargetIsOn", actionTargetIsOn.HasValue ? (object)(actionTargetIsOn.Value ? 1 : 0) : DBNull.Value);
            command.Parameters.AddWithValue("@actionSceneId", (object?)actionSceneId ?? DBNull.Value);
            command.Parameters.AddWithValue("@updatedAt", DateTime.UtcNow.ToString("O"));
            command.ExecuteNonQuery();

            LogEvent(db, transaction, "info", "scheduler", "SCHEDULE_UPDATED", $"Обновлено расписание «{cleanName}»", deviceId: actionDeviceId, sceneId: actionSceneId);
            transaction.Commit();
            return GetSchedule(id);
        }
    }

    public ScheduleEntry SetScheduleEnabled(int id, bool isEnabled)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            var schedule = GetSchedule(id);
            using var transaction = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "UPDATE Schedules SET IsEnabled = @isEnabled, UpdatedAt = @updatedAt WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@isEnabled", isEnabled ? 1 : 0);
            command.Parameters.AddWithValue("@updatedAt", DateTime.UtcNow.ToString("O"));
            command.ExecuteNonQuery();
            LogEvent(db, transaction, "info", "scheduler", isEnabled ? "SCHEDULE_ENABLED" : "SCHEDULE_DISABLED", $"Расписание «{schedule.Name}» {(isEnabled ? "включено" : "выключено")}", deviceId: schedule.ActionDeviceId, sceneId: schedule.ActionSceneId);
            transaction.Commit();
            return GetSchedule(id);
        }
    }

    public void DeleteSchedule(int id)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            var schedule = GetSchedule(id);
            using var transaction = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "DELETE FROM Schedules WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.ExecuteNonQuery();
            LogEvent(db, transaction, "info", "scheduler", "SCHEDULE_DELETED", $"Удалено расписание «{schedule.Name}»", deviceId: schedule.ActionDeviceId, sceneId: schedule.ActionSceneId);
            transaction.Commit();
        }
    }

    public IReadOnlyList<ScheduleRun> GetScheduleRuns(int scheduleId, int limit = 20)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            _ = GetSchedule(scheduleId);
            return ReadScheduleRuns(db, scheduleId, limit);
        }
    }

    public ScheduleRunBatchResult RunDueSchedules(DateTime? nowLocal = null)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            var now = nowLocal ?? DateTime.Now;
            var slot = now.ToString("yyyy-MM-dd HH:mm");
            var timeOfDay = now.ToString("HH:mm");
            var day = MapDayOfWeek(now.DayOfWeek);
            var schedules = ReadSchedules(db, null).Where(s => s.IsEnabled && s.TimeOfDay == timeOfDay && s.DaysOfWeek.Contains(day) && !string.Equals(s.LastTriggeredSlot, slot, StringComparison.Ordinal)).ToList();

            var result = new ScheduleRunBatchResult
            {
                Slot = slot,
                Message = schedules.Count == 0 ? "Подходящих расписаний нет" : $"Запущено расписаний: {schedules.Count}",
            };

            if (schedules.Count == 0)
            {
                return result;
            }

            using var transaction = db.BeginTransaction();
            foreach (var schedule in schedules)
            {
                var run = ExecuteScheduleInternal(db, transaction, schedule, slot);
                result.Runs.Add(run);
            }
            transaction.Commit();
            SyncLegacyDevicesJson(db);
            return result;
        }
    }

    private void EnsureAutomationSchema(SqliteConnection connection)
    {
        EnsureDeviceSchema(connection);

        var command = connection.CreateCommand();
        command.CommandText = @"
CREATE TABLE IF NOT EXISTS AutomationRules (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    Description TEXT NOT NULL DEFAULT '',
    IsEnabled INTEGER NOT NULL DEFAULT 1,
    TriggerDeviceId INTEGER NOT NULL,
    TriggerEventType TEXT NOT NULL,
    ComparisonOperator TEXT NOT NULL,
    CompareValue TEXT NOT NULL,
    ActionKind TEXT NOT NULL,
    ActionDeviceId INTEGER NULL,
    ActionTargetIsOn INTEGER NULL,
    ActionSceneId INTEGER NULL,
    CreatedAt TEXT NOT NULL,
    UpdatedAt TEXT NOT NULL,
    LastTriggeredAt TEXT NULL,
    LastTriggerStatus TEXT NULL,
    LastTriggerMessage TEXT NULL,
    FOREIGN KEY(TriggerDeviceId) REFERENCES Devices(Id) ON DELETE CASCADE,
    FOREIGN KEY(ActionDeviceId) REFERENCES Devices(Id) ON DELETE SET NULL,
    FOREIGN KEY(ActionSceneId) REFERENCES Scenes(Id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS RuleRuns (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    RuleId INTEGER NOT NULL,
    SourceDeviceId INTEGER NOT NULL,
    EventType TEXT NOT NULL,
    EventValue TEXT NOT NULL,
    TriggeredAt TEXT NOT NULL,
    Status TEXT NOT NULL,
    Message TEXT NOT NULL,
    FOREIGN KEY(RuleId) REFERENCES AutomationRules(Id) ON DELETE CASCADE,
    FOREIGN KEY(SourceDeviceId) REFERENCES Devices(Id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Schedules (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL COLLATE NOCASE UNIQUE,
    Description TEXT NOT NULL DEFAULT '',
    IsEnabled INTEGER NOT NULL DEFAULT 1,
    TimeOfDay TEXT NOT NULL,
    DaysOfWeek TEXT NOT NULL,
    ActionKind TEXT NOT NULL,
    ActionDeviceId INTEGER NULL,
    ActionTargetIsOn INTEGER NULL,
    ActionSceneId INTEGER NULL,
    CreatedAt TEXT NOT NULL,
    UpdatedAt TEXT NOT NULL,
    LastRunAt TEXT NULL,
    LastRunStatus TEXT NULL,
    LastRunMessage TEXT NULL,
    LastTriggeredSlot TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(ActionDeviceId) REFERENCES Devices(Id) ON DELETE SET NULL,
    FOREIGN KEY(ActionSceneId) REFERENCES Scenes(Id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS ScheduleRuns (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    ScheduleId INTEGER NOT NULL,
    ScheduledSlot TEXT NOT NULL,
    TriggeredAt TEXT NOT NULL,
    Status TEXT NOT NULL,
    Message TEXT NOT NULL,
    FOREIGN KEY(ScheduleId) REFERENCES Schedules(Id) ON DELETE CASCADE
);";
        command.ExecuteNonQuery();
    }

    private void EnsureDeviceSchema(SqliteConnection connection)
    {
        EnsureColumnExists(connection, "Devices", "Protocol", "TEXT NOT NULL DEFAULT 'manual'");
        EnsureColumnExists(connection, "Devices", "Channel", "TEXT NOT NULL DEFAULT 'local'");
        EnsureColumnExists(connection, "Devices", "ExternalId", "TEXT NULL");
        EnsureColumnExists(connection, "Devices", "Manufacturer", "TEXT NOT NULL DEFAULT ''");
        EnsureColumnExists(connection, "Devices", "Model", "TEXT NOT NULL DEFAULT ''");
        EnsureColumnExists(connection, "Devices", "ConnectionStatus", "TEXT NOT NULL DEFAULT 'unknown'");
        EnsureColumnExists(connection, "Devices", "ConnectionMessage", "TEXT NOT NULL DEFAULT ''");
        EnsureColumnExists(connection, "Devices", "LastConnectionCheckAt", "TEXT NULL");
        EnsureColumnExists(connection, "Devices", "LastSeenAt", "TEXT NULL");

        var index = connection.CreateCommand();
        index.CommandText = "CREATE UNIQUE INDEX IF NOT EXISTS IX_Devices_ExternalId_Unique ON Devices(ExternalId) WHERE ExternalId IS NOT NULL AND trim(ExternalId) <> '';";
        index.ExecuteNonQuery();
    }

    private static void EnsureColumnExists(SqliteConnection connection, string tableName, string columnName, string sqlType)
    {
        var pragma = connection.CreateCommand();
        pragma.CommandText = $"PRAGMA table_info({tableName});";
        using var reader = pragma.ExecuteReader();
        while (reader.Read())
        {
            if (string.Equals(reader.GetString(1), columnName, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }
        }
        reader.Close();

        var alter = connection.CreateCommand();
        alter.CommandText = $"ALTER TABLE {tableName} ADD COLUMN {columnName} {sqlType};";
        alter.ExecuteNonQuery();
    }

    private ConnectionValidationResult ValidateConnectionInternal(string provider, string protocol, Dictionary<string, string> connection)
    {
        provider = _catalog.NormalizeProviderCode(provider);
        protocol = NormalizeProtocol(NormalizeOptional(protocol, _catalog.InferProtocol(provider)));

        if (provider is "mock" or "demo" || protocol is "manual" or "demo")
        {
            return new ConnectionValidationResult(true, "connected", "Локальное устройство не требует сетевой проверки", connection);
        }

        EnsureRequiredConnectionFields(provider, protocol, connection);
        ValidateConnectionFields(provider, protocol, connection);

        if (protocol is "http" or "https")
        {
            var ok = TryHttpConnection(connection, protocol, out var message);
            return new ConnectionValidationResult(ok, ok ? "connected" : "no_connection", message, connection);
        }

        if (protocol is "mqtt" or "tcp" or "rtsp")
        {
            var ok = TryTcpConnection(connection, out var message);
            return new ConnectionValidationResult(ok, ok ? "connected" : "no_connection", message, connection);
        }

        return new ConnectionValidationResult(true, "unknown", "Параметры сохранены, проверка выполняется вручную", connection);
    }

    private ConnectionValidationResult ValidateConnectionForSave(string provider, string protocol, Dictionary<string, string> connection)
    {
        provider = _catalog.NormalizeProviderCode(provider);
        protocol = NormalizeProtocol(NormalizeOptional(protocol, _catalog.InferProtocol(provider)));

        if (provider is "mock" or "demo" || protocol is "manual" or "demo")
        {
            return new ConnectionValidationResult(true, "connected", "Локальное устройство не требует сетевой проверки", connection);
        }

        EnsureRequiredConnectionFields(provider, protocol, connection);
        ValidateConnectionFields(provider, protocol, connection);

        return new ConnectionValidationResult(true, "unknown", "Параметры сохранены. Проверка связи не выполнялась", connection);
    }

    private static bool TryHttpConnection(Dictionary<string, string> connection, string protocol, out string message)
    {
        try
        {
            var url = BuildHttpUrl(connection, protocol);
            using var handler = new HttpClientHandler();
            using var client = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(3) };
            using var request = new HttpRequestMessage(HttpMethod.Get, url);
            var response = client.Send(request);
            message = response.IsSuccessStatusCode
                ? $"HTTP устройство отвечает ({(int)response.StatusCode})"
                : $"HTTP устройство недоступно ({(int)response.StatusCode})";
            return response.IsSuccessStatusCode;
        }
        catch (TaskCanceledException ex)
        {
            message = $"HTTP connection timeout: {ex.Message}";
            return false;
        }
        catch (TimeoutException ex)
        {
            message = $"HTTP connection timeout: {ex.Message}";
            return false;
        }
        catch (Exception ex)
        {
            message = $"Не удалось проверить HTTP подключение: {ex.Message}";
            return false;
        }
    }

    private static bool TryTcpConnection(Dictionary<string, string> connection, out string message)
    {
        var host = GetConnectionValue(connection, "host", "url");
        var portRaw = GetConnectionValue(connection, "port");
        var port = ParsePort(portRaw);

        try
        {
            using var client = new TcpClient();
            var connectTask = client.ConnectAsync(host, port);
            var finished = Task.WaitAny([connectTask], TimeSpan.FromSeconds(3)) == 0;
            if (connectTask.IsFaulted)
            {
                throw connectTask.Exception?.GetBaseException() ?? new SocketException();
            }

            if (!finished || !client.Connected)
            {
                message = "Таймаут при сетевой проверке";
                return false;
            }

            message = $"TCP порт {port} доступен";
            return true;
        }
        catch (Exception ex)
        {
            message = $"Не удалось проверить TCP подключение: {ex.Message}";
            return false;
        }
    }

    private static string BuildHttpUrl(Dictionary<string, string> connection, string protocol)
    {
        var direct = GetConnectionValue(connection, "url");
        if (!string.IsNullOrWhiteSpace(direct))
        {
            return direct.StartsWith("http", StringComparison.OrdinalIgnoreCase) ? direct : $"{protocol}://{direct}";
        }

        var host = GetConnectionValue(connection, "host");
        var port = GetConnectionValue(connection, "port");
        var path = GetConnectionValue(connection, "path");
        var hostPart = string.IsNullOrWhiteSpace(port) ? host : $"{host}:{port}";
        var finalPath = string.IsNullOrWhiteSpace(path) ? string.Empty : (path.StartsWith('/') ? path : $"/{path}");
        return $"{protocol}://{hostPart}{finalPath}";
    }

    private static void EnsureRequiredConnectionFields(string provider, string protocol, Dictionary<string, string> connection)
    {
        string[] required = provider switch
        {
            "shelly" or "tasmota" => ["host"],
            "homeassistant" => ["url", "token", "entity_id"],
            "mqtt" or "zigbee2mqtt" => ["host", "port", "topic"],
            "camera" or "camera_rtsp" or "custom" or "custom_tcp" => ["host", "port"],
            "http" or "custom_http" => ["url"],
            _ when protocol is "http" or "https" => ["url"],
            _ when protocol is "mqtt" or "tcp" or "rtsp" => ["host", "port"],
            _ => Array.Empty<string>(),
        };

        foreach (var field in required)
        {
            var value = GetConnectionValue(connection, field);
            if (string.IsNullOrWhiteSpace(value))
            {
                throw new ValidationProblemException($"Поле подключения «{field}» обязательно", "DEVICE_CONNECTION_FIELD_REQUIRED");
            }
        }
    }

    private static void ValidateConnectionFields(string provider, string protocol, Dictionary<string, string> connection)
    {
        ValidateConnectionTextLength(connection, "host", 253, "Host / IP слишком длинный", "DEVICE_CONNECTION_HOST_TOO_LONG");
        ValidateConnectionTextLength(connection, "url", 253, "URL слишком длинный", "DEVICE_CONNECTION_URL_TOO_LONG");
        ValidateConnectionTextLength(connection, "snapshot_url", 253, "URL снимка слишком длинный", "DEVICE_CONNECTION_SNAPSHOT_URL_TOO_LONG");
        ValidateConnectionTextLength(connection, "path", 512, "Path слишком длинный", "DEVICE_CONNECTION_PATH_TOO_LONG");
        ValidateConnectionTextLength(connection, "topic", 200, "Topic слишком длинный", "DEVICE_CONNECTION_TOPIC_TOO_LONG");
        ValidateConnectionTextLength(connection, "state_topic", 200, "Topic состояния слишком длинный", "DEVICE_CONNECTION_STATE_TOPIC_TOO_LONG");
        ValidateConnectionTextLength(connection, "username", 50, "Пользователь слишком длинный", "DEVICE_CONNECTION_USERNAME_TOO_LONG");
        ValidateConnectionTextLength(connection, "password", 200, "Пароль / ключ устройства слишком длинный", "DEVICE_CONNECTION_PASSWORD_TOO_LONG");
        ValidateConnectionTextLength(connection, "device_key", 200, "Пароль / ключ устройства слишком длинный", "DEVICE_CONNECTION_DEVICE_KEY_TOO_LONG");
        ValidateConnectionTextLength(connection, "token", 200, "Токен слишком длинный", "DEVICE_CONNECTION_TOKEN_TOO_LONG");
        ValidateConnectionTextLength(connection, "entity_id", MaxShortTextLength, "Entity ID слишком длинный", "DEVICE_CONNECTION_ENTITY_ID_TOO_LONG");
        ValidateConnectionTextLength(connection, "headers", MaxConnectionTextLength, "Заголовки JSON слишком длинные", "DEVICE_CONNECTION_HEADERS_TOO_LONG");
        ValidateConnectionTextLength(connection, "body_template", MaxConnectionTextLength, "Шаблон body слишком длинный", "DEVICE_CONNECTION_BODY_TEMPLATE_TOO_LONG");
        ValidateConnectionTextLength(connection, "payload_template", MaxConnectionTextLength, "Шаблон payload слишком длинный", "DEVICE_CONNECTION_PAYLOAD_TEMPLATE_TOO_LONG");

        var host = GetConnectionValue(connection, "host");
        if (!string.IsNullOrWhiteSpace(host))
        {
            ValidateHost(host);
        }

        var port = GetConnectionValue(connection, "port");
        if (!string.IsNullOrWhiteSpace(port))
        {
            _ = ParsePort(port);
        }

        var url = GetConnectionValue(connection, "url");
        if (!string.IsNullOrWhiteSpace(url))
        {
            ValidateUrl(url, protocol, "URL", "DEVICE_CONNECTION_URL_INVALID");
        }

        var snapshotUrl = GetConnectionValue(connection, "snapshot_url");
        if (!string.IsNullOrWhiteSpace(snapshotUrl))
        {
            ValidateUrl(snapshotUrl, "http", "URL снимка", "DEVICE_CONNECTION_SNAPSHOT_URL_INVALID");
        }

        var path = GetConnectionValue(connection, "path");
        if (!string.IsNullOrWhiteSpace(path)
            && (path.Contains("://", StringComparison.Ordinal) || path.Any(char.IsWhiteSpace) || path.Any(char.IsControl)))
        {
            throw new ValidationProblemException("Path должен быть без протокола, пробелов и управляющих символов", "DEVICE_CONNECTION_PATH_INVALID");
        }

        var method = GetConnectionValue(connection, "method");
        if (!string.IsNullOrWhiteSpace(method))
        {
            ValidateHttpMethod(method);
        }

        var username = GetConnectionValue(connection, "username");
        if (!string.IsNullOrWhiteSpace(username))
        {
            _ = NormalizeSafeTextOptional(username, "Пользователь", 1, 50, "DEVICE_CONNECTION_USERNAME_INVALID");
        }

        var headers = GetConnectionValue(connection, "headers");
        if (!TryReadHttpHeaders(headers, out _, out var headersError))
        {
            throw new ValidationProblemException(headersError, "DEVICE_CONNECTION_HEADERS_INVALID");
        }

        var entityId = GetConnectionValue(connection, "entity_id");
        if (!string.IsNullOrWhiteSpace(entityId)
            && (!entityId.Contains('.', StringComparison.Ordinal) || entityId.Any(char.IsWhiteSpace) || entityId.Any(char.IsControl)))
        {
            throw new ValidationProblemException("Entity ID должен быть в формате domain.object_id, например light.kitchen", "DEVICE_CONNECTION_ENTITY_ID_INVALID");
        }

        if (provider is "mqtt" or "zigbee2mqtt" || protocol == "mqtt")
        {
            ValidateMqttTopic(connection, "topic", required: true);
            ValidateMqttTopic(connection, "state_topic", required: false);
            var topic = GetConnectionValue(connection, "topic");
            var stateTopic = GetConnectionValue(connection, "state_topic");
            if (!string.IsNullOrWhiteSpace(topic)
                && !string.IsNullOrWhiteSpace(stateTopic)
                && string.Equals(topic, stateTopic, StringComparison.OrdinalIgnoreCase))
            {
                throw new ValidationProblemException("Topic состояния не должен совпадать с командным Topic", "DEVICE_CONNECTION_TOPIC_DUPLICATE");
            }
        }

        var payloadOn = GetConnectionValue(connection, "payload_on");
        var payloadOff = GetConnectionValue(connection, "payload_off");
        if (!string.IsNullOrWhiteSpace(payloadOn))
        {
            _ = NormalizeSafeTextRequired(payloadOn, "Payload ON", 1, 50, "DEVICE_CONNECTION_PAYLOAD_ON_REQUIRED", "DEVICE_CONNECTION_PAYLOAD_ON_INVALID");
        }
        if (!string.IsNullOrWhiteSpace(payloadOff))
        {
            _ = NormalizeSafeTextRequired(payloadOff, "Payload OFF", 1, 50, "DEVICE_CONNECTION_PAYLOAD_OFF_REQUIRED", "DEVICE_CONNECTION_PAYLOAD_OFF_INVALID");
        }
        if (!string.IsNullOrWhiteSpace(payloadOn)
            && !string.IsNullOrWhiteSpace(payloadOff)
            && string.Equals(payloadOn, payloadOff, StringComparison.OrdinalIgnoreCase))
        {
            throw new ValidationProblemException("Payload ON и Payload OFF не должны совпадать", "DEVICE_CONNECTION_PAYLOAD_DUPLICATE");
        }
    }

    private static void ValidateConnectionTextLength(Dictionary<string, string> connection, string key, int maxLength, string message, string code)
    {
        var value = GetConnectionValue(connection, key);
        if (value.Length > maxLength)
        {
            throw new ValidationProblemException($"{message}: максимум {maxLength} символов", code);
        }
    }

    private static void ValidateHost(string host)
    {
        if (host.Contains("://", StringComparison.Ordinal) || host.Contains('/') || host.Any(char.IsWhiteSpace) || host.Any(char.IsControl))
        {
            throw new ValidationProblemException("Host / IP должен быть именем хоста или IP без протокола, пути и пробелов", "DEVICE_CONNECTION_HOST_INVALID");
        }
        if (!HostPattern.IsMatch(host))
        {
            throw new ValidationProblemException("Host / IP должен быть валидным IPv4, доменом или hostname", "DEVICE_CONNECTION_HOST_INVALID");
        }
    }

    private static int ParsePort(string value)
    {
        if (!int.TryParse(value, NumberStyles.None, CultureInfo.InvariantCulture, out var port) || port is < 1 or > 65535)
        {
            throw new ValidationProblemException("Port должен быть числом от 1 до 65535", "DEVICE_CONNECTION_PORT_INVALID");
        }

        return port;
    }

    private static void ValidateUrl(string value, string protocol, string label, string code)
    {
        var sample = RenderDeviceCommandTemplate(value, true);
        if (!Uri.TryCreate(sample, UriKind.Absolute, out var uri)
            || (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps)
            || string.IsNullOrWhiteSpace(uri.Host))
        {
            throw new ValidationProblemException($"{label} должен быть абсолютным HTTP/HTTPS URL", code);
        }
    }

    private static void ValidateHttpMethod(string value)
    {
        var method = value.Trim().ToUpperInvariant();
        string[] allowed = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"];
        if (!allowed.Contains(method, StringComparer.OrdinalIgnoreCase))
        {
            throw new ValidationProblemException("HTTP-метод должен быть одним из GET, POST, PUT, PATCH, DELETE, HEAD", "DEVICE_CONNECTION_METHOD_INVALID");
        }
    }

    private static void ValidateMqttTopic(Dictionary<string, string> connection, string key, bool required)
    {
        var value = GetConnectionValue(connection, key);
        if (string.IsNullOrWhiteSpace(value))
        {
            if (required)
            {
                throw new ValidationProblemException($"Поле подключения «{key}» обязательно", "DEVICE_CONNECTION_FIELD_REQUIRED");
            }
            return;
        }

        if (value.Any(char.IsControl) || value.Any(char.IsWhiteSpace) || value.Contains('#') || value.Contains('+'))
        {
            throw new ValidationProblemException($"MQTT topic «{key}» не должен содержать пробелы, управляющие символы или wildcard #/+", "DEVICE_CONNECTION_TOPIC_INVALID");
        }

        if (!MqttTopicPattern.IsMatch(value))
        {
            throw new ValidationProblemException($"MQTT topic «{key}» может содержать только латиницу, цифры, /, _, -, .", "DEVICE_CONNECTION_TOPIC_INVALID");
        }
    }

    private static string GetConnectionValue(Dictionary<string, string> connection, params string[] keys)
    {
        foreach (var key in keys)
        {
            if (connection.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value))
            {
                return value.Trim();
            }
        }
        return string.Empty;
    }

    private DeviceCommandResult ExecuteDeviceStateCommand(Device device, bool targetIsOn)
    {
        var provider = _catalog.NormalizeProviderCode(device.Provider);
        var protocol = NormalizeOptional(device.Protocol, _catalog.InferProtocol(provider)).ToLowerInvariant();

        if (provider == "custom_http")
        {
            return ExecuteCustomHttpCommand(device, protocol, targetIsOn);
        }

        if (provider is "mock" or "demo" || protocol is "manual" or "demo")
        {
            return new DeviceCommandResult(true, "connected", "Локальное устройство переключено без сетевой команды");
        }

        return new DeviceCommandResult(
            true,
            string.IsNullOrWhiteSpace(device.ConnectionStatus) ? "unknown" : device.ConnectionStatus,
            string.IsNullOrWhiteSpace(device.ConnectionMessage) ? "Состояние устройства обновлено локально" : device.ConnectionMessage);
    }

    private static DeviceCommandResult ExecuteCustomHttpCommand(Device device, string protocol, bool targetIsOn)
    {
        try
        {
            var url = RenderDeviceCommandTemplate(BuildHttpUrl(device.Connection, protocol), targetIsOn);
            var method = NormalizeOptional(GetConnectionValue(device.Connection, "method"), "POST").ToUpperInvariant();
            var bodyTemplate = GetConnectionValue(device.Connection, "body_template");
            var body = RenderDeviceCommandTemplate(bodyTemplate, targetIsOn);
            var headersJson = GetConnectionValue(device.Connection, "headers");

            if (!TryReadHttpHeaders(headersJson, out var headers, out var headersError))
            {
                return new DeviceCommandResult(false, "no_connection", headersError);
            }

            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(3) };
            using var request = new HttpRequestMessage(new HttpMethod(method), url);

            var contentType = headers.TryGetValue("Content-Type", out var requestedContentType)
                ? requestedContentType
                : "application/json";

            foreach (var header in headers)
            {
                if (string.Equals(header.Key, "Content-Type", StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }
                request.Headers.TryAddWithoutValidation(header.Key, header.Value);
            }

            if (!string.IsNullOrWhiteSpace(body) && method is not "GET" and not "HEAD")
            {
                request.Content = new StringContent(body, Encoding.UTF8, contentType);
            }

            using var response = client.Send(request);
            var safeUrl = RedactSensitiveText(url);
            var message = $"HTTP {method} {safeUrl} -> {(int)response.StatusCode}";

            return new DeviceCommandResult(
                response.IsSuccessStatusCode,
                response.IsSuccessStatusCode ? "connected" : "no_connection",
                message);
        }
        catch (TaskCanceledException ex)
        {
            return new DeviceCommandResult(false, "timeout", $"HTTP command timeout: {ex.Message}");
        }
        catch (TimeoutException ex)
        {
            return new DeviceCommandResult(false, "timeout", $"HTTP command timeout: {ex.Message}");
        }
        catch (Exception ex)
        {
            return new DeviceCommandResult(false, "no_connection", $"Не удалось выполнить HTTP-команду: {ex.Message}");
        }
    }

    private void UpdateDeviceStateAfterCommand(SqliteConnection connection, SqliteTransaction transaction, Device device, bool targetIsOn, DeviceCommandResult commandResult)
    {
        var now = DateTime.UtcNow;
        var updateDevice = connection.CreateCommand();
        updateDevice.Transaction = transaction;
        updateDevice.CommandText = @"
UPDATE Devices
SET IsOn = @isOn,
    ConnectionStatus = @connectionStatus,
    ConnectionMessage = @connectionMessage,
    LastConnectionCheckAt = @lastConnectionCheckAt,
    UpdatedAt = @updatedAt
WHERE Id = @id;";
        updateDevice.Parameters.AddWithValue("@isOn", commandResult.Ok ? (targetIsOn ? 1 : 0) : (device.IsOn ? 1 : 0));
        updateDevice.Parameters.AddWithValue("@connectionStatus", commandResult.Status);
        updateDevice.Parameters.AddWithValue("@connectionMessage", commandResult.Message);
        updateDevice.Parameters.AddWithValue("@lastConnectionCheckAt", now.ToString("O"));
        updateDevice.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
        updateDevice.Parameters.AddWithValue("@id", device.Id);
        updateDevice.ExecuteNonQuery();
    }

    private static bool TryReadHttpHeaders(string headersJson, out Dictionary<string, string> headers, out string error)
    {
        headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        error = string.Empty;
        if (string.IsNullOrWhiteSpace(headersJson))
        {
            return true;
        }

        try
        {
            using var document = JsonDocument.Parse(headersJson);
            if (document.RootElement.ValueKind != JsonValueKind.Object)
            {
                error = "HTTP headers должны быть JSON-объектом";
                return false;
            }

            foreach (var property in document.RootElement.EnumerateObject())
            {
                if (string.IsNullOrWhiteSpace(property.Name) || property.Name.Any(char.IsWhiteSpace) || property.Name.Any(char.IsControl))
                {
                    error = "HTTP headers содержат некорректное имя заголовка";
                    return false;
                }

                var value = property.Value.ValueKind == JsonValueKind.String
                    ? property.Value.GetString()
                    : property.Value.GetRawText();
                if (!string.IsNullOrWhiteSpace(value))
                {
                    if (value.Contains('\r') || value.Contains('\n'))
                    {
                        error = "HTTP headers не должны содержать переносы строк";
                        return false;
                    }
                    headers[property.Name] = value;
                }
            }
            return true;
        }
        catch (JsonException ex)
        {
            error = $"HTTP headers должны быть валидным JSON: {ex.Message}";
            return false;
        }
    }

    private static string RenderDeviceCommandTemplate(string template, bool targetIsOn)
    {
        if (string.IsNullOrEmpty(template))
        {
            return string.Empty;
        }

        var boolText = targetIsOn ? "true" : "false";
        var stateText = targetIsOn ? "ON" : "OFF";
        var stateLower = targetIsOn ? "on" : "off";
        return template
            .Replace("{{isOn}}", boolText, StringComparison.OrdinalIgnoreCase)
            .Replace("{isOn}", boolText, StringComparison.OrdinalIgnoreCase)
            .Replace("{{value}}", boolText, StringComparison.OrdinalIgnoreCase)
            .Replace("{value}", boolText, StringComparison.OrdinalIgnoreCase)
            .Replace("{{state}}", stateText, StringComparison.OrdinalIgnoreCase)
            .Replace("{state}", stateText, StringComparison.OrdinalIgnoreCase)
            .Replace("{{stateLower}}", stateLower, StringComparison.OrdinalIgnoreCase)
            .Replace("{stateLower}", stateLower, StringComparison.OrdinalIgnoreCase);
    }

    private static string Shorten(string value, int maxLength)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }
        var clean = value.Replace("\r", " ").Replace("\n", " ").Trim();
        return clean.Length <= maxLength ? clean : clean[..maxLength] + "...";
    }

    private static string RedactSensitiveText(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return string.Empty;
        }

        var redacted = Regex.Replace(value, "(token|password|passwd|device_key|key|secret)=([^&\\s]+)", "$1=***", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
        return Regex.Replace(redacted, "Bearer\\s+[A-Za-z0-9._\\-]+", "Bearer ***", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    }

    private static Dictionary<string, string> NormalizeConnection(Dictionary<string, string>? connection)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (connection is null)
        {
            return result;
        }

        foreach (var pair in connection)
        {
            var key = pair.Key?.Trim();
            var value = pair.Value?.Trim();
            if (!string.IsNullOrWhiteSpace(key) && !string.IsNullOrWhiteSpace(value))
            {
                if (key.Length > MaxShortTextLength || key.Any(char.IsWhiteSpace) || key.Any(char.IsControl))
                {
                    throw new ValidationProblemException("Имя поля подключения некорректно", "DEVICE_CONNECTION_KEY_INVALID");
                }
                if (!CodePattern.IsMatch(key))
                {
                    throw new ValidationProblemException("Имя поля подключения может содержать только латиницу, цифры, точку, дефис и подчёркивание", "DEVICE_CONNECTION_KEY_INVALID");
                }

                if (value.Length > MaxConnectionTextLength)
                {
                    throw new ValidationProblemException($"Значение поля подключения «{key}» слишком длинное: максимум {MaxConnectionTextLength} символов", "DEVICE_CONNECTION_VALUE_TOO_LONG");
                }

                result[key] = value;
            }
        }
        return result;
    }

    private void EnsureDeviceExternalIdIsUnique(SqliteConnection connection, string externalId, int? currentDeviceId)
    {
        var command = connection.CreateCommand();
        command.CommandText = "SELECT Id FROM Devices WHERE trim(COALESCE(ExternalId, '')) <> '' AND lower(ExternalId) = lower(@externalId) LIMIT 1;";
        command.Parameters.AddWithValue("@externalId", externalId);
        var existing = command.ExecuteScalar();
        if (existing is long existingId && (!currentDeviceId.HasValue || currentDeviceId.Value != Convert.ToInt32(existingId)))
        {
            throw new ConflictProblemException("Устройство с таким идентификатором уже существует", "DEVICE_EXTERNAL_ID_EXISTS");
        }
    }

    private static string InferProtocol(string? provider)
    {
        return NormalizeOptional(provider, "mock").Trim().ToLowerInvariant() switch
        {
            "demo" => "demo",
            "shelly" or "tasmota" or "homeassistant" or "http" or "custom_http" => "http",
            "mqtt" or "zigbee2mqtt" => "mqtt",
            "camera" or "camera_rtsp" => "rtsp",
            "custom" or "custom_tcp" => "tcp",
            _ => "manual",
        };
    }

    private static string InferChannel(string? protocol)
    {
        return NormalizeOptional(protocol, "manual").Trim().ToLowerInvariant() switch
        {
            "http" or "https" => "wifi",
            "demo" => "local",
            "mqtt" => "mqtt",
            "rtsp" => "lan",
            "tcp" => "lan",
            _ => "local",
        };
    }

    private static void ValidateRuleOperator(string value)
    {
        if (!SupportedRuleOperators.Contains(value))
        {
            throw new ValidationProblemException("Неподдерживаемый оператор правила", "RULE_OPERATOR_INVALID");
        }
    }

    private static void ValidateEventType(string value, string code)
    {
        if (!SupportedEventTypes.Contains(value, StringComparer.OrdinalIgnoreCase))
        {
            throw new ValidationProblemException("Неподдерживаемый тип события", code);
        }
    }

    private static void ValidateEventValue(string eventType, string value, string label, string code)
    {
        ValidateEventType(eventType, code);
        EnsureNoDangerousText(value, label, code);
        var normalized = value.Trim();
        var lowered = normalized.ToLowerInvariant();

        if (BooleanEventTypes.Contains(eventType, StringComparer.OrdinalIgnoreCase))
        {
            if (lowered is not "true" and not "false")
            {
                throw new ValidationProblemException($"{label}: для {eventType} можно только true/false", code);
            }
            return;
        }

        if (NumericEventTypes.Contains(eventType, StringComparer.OrdinalIgnoreCase))
        {
            if (!double.TryParse(normalized.Replace(',', '.'), NumberStyles.Float, CultureInfo.InvariantCulture, out var number))
            {
                throw new ValidationProblemException($"{label}: для {eventType} нужно число", code);
            }

            var (min, max) = eventType.ToLowerInvariant() switch
            {
                "temperature" => (-50d, 100d),
                "humidity" => (0d, 100d),
                "battery" => (0d, 100d),
                _ => (double.MinValue, double.MaxValue),
            };
            if (number < min || number > max)
            {
                throw new ValidationProblemException($"{label}: для {eventType} диапазон {min}..{max}", code);
            }
            return;
        }

        if (eventType.Equals("power", StringComparison.OrdinalIgnoreCase)
            && lowered is not "true" and not "false" and not "on" and not "off" and not "1" and not "0")
        {
            throw new ValidationProblemException($"{label}: для power можно true/false или ON/OFF", code);
        }
    }

    private static void ValidateRuleOperatorForEvent(string eventType, string ruleOperator)
    {
        if (BooleanEventTypes.Contains(eventType, StringComparer.OrdinalIgnoreCase) && ruleOperator is not "=" and not "!=")
        {
            throw new ValidationProblemException("Для boolean-событий доступны только операторы = и !=", "RULE_OPERATOR_EVENT_INCOMPATIBLE");
        }

        if (NumericEventTypes.Contains(eventType, StringComparer.OrdinalIgnoreCase)
            && ruleOperator is not "=" and not "!=" and not ">" and not ">=" and not "<" and not "<=")
        {
            throw new ValidationProblemException("Для числовых событий доступны =, !=, >, >=, <, <=", "RULE_OPERATOR_EVENT_INCOMPATIBLE");
        }

        if (ruleOperator == "contains" && !TextEventTypes.Contains(eventType, StringComparer.OrdinalIgnoreCase))
        {
            throw new ValidationProblemException("Оператор contains доступен только для строковых событий", "RULE_OPERATOR_EVENT_INCOMPATIBLE");
        }
    }

    private void EnsureDeviceCanEmitEvent(Device device, string eventType)
    {
        var type = _catalog.GetDeviceType(device.Type);
        if (!type.Capabilities.CanEmitEvents)
        {
            throw new ValidationProblemException("Выбранное устройство не отправляет события", "EVENT_SOURCE_NOT_SUPPORTED");
        }

        var normalizedType = type.Code.ToLowerInvariant();
        var normalizedEvent = eventType.ToLowerInvariant();
        if (normalizedType == "motion_sensor" && normalizedEvent is not "motion" and not "battery" and not "online" and not "offline")
        {
            throw new ValidationProblemException("Для датчика движения допустимы события motion, battery, online, offline", "EVENT_TYPE_DEVICE_INCOMPATIBLE");
        }

        if (normalizedType == "temperature_sensor" && normalizedEvent is not "temperature" and not "humidity" and not "battery" and not "online" and not "offline")
        {
            throw new ValidationProblemException("Для датчика температуры допустимы события temperature, humidity, battery, online, offline", "EVENT_TYPE_DEVICE_INCOMPATIBLE");
        }

        if (normalizedType == "leak_sensor" && normalizedEvent is not "water_leak" and not "battery" and not "online" and not "offline")
        {
            throw new ValidationProblemException("Для датчика протечки допустимы события water_leak, battery, online, offline", "EVENT_TYPE_DEVICE_INCOMPATIBLE");
        }
    }

    private void ValidateActionTarget(SqliteConnection connection, string actionKind, int? actionDeviceId, bool? actionTargetIsOn, int? actionSceneId)
    {
        actionKind = actionKind.Trim().ToLowerInvariant();
        if (!SupportedActionKinds.Contains(actionKind))
        {
            throw new ValidationProblemException("Неподдерживаемый тип действия", "ACTION_KIND_INVALID");
        }

        if (actionKind == "device_state")
        {
            if (!actionDeviceId.HasValue)
            {
                throw new ValidationProblemException("Нужно выбрать устройство для действия", "RULE_ACTION_DEVICE_REQUIRED");
            }
            if (actionDeviceId.Value <= 0)
            {
                throw new ValidationProblemException("Устройство для действия выбрано некорректно", "RULE_ACTION_DEVICE_INVALID");
            }
            if (!actionTargetIsOn.HasValue)
            {
                throw new ValidationProblemException("Нужно выбрать целевое состояние устройства", "RULE_ACTION_STATE_REQUIRED");
            }
            var device = ReadDeviceOrThrow(connection, actionDeviceId.Value);
            if (!_catalog.GetDeviceType(device.Type).Capabilities.CanReceiveCommands)
            {
                throw new ValidationProblemException("Датчик или камера не могут быть целевым устройством действия", "RULE_ACTION_DEVICE_NOT_COMMANDABLE");
            }
            return;
        }

        if (!actionSceneId.HasValue)
        {
            throw new ValidationProblemException("Нужно выбрать сценарий для действия", "RULE_ACTION_SCENE_REQUIRED");
        }
        if (actionSceneId.Value <= 0)
        {
            throw new ValidationProblemException("Сценарий для действия выбран некорректно", "RULE_ACTION_SCENE_INVALID");
        }
        _ = ReadScenes(connection, actionSceneId.Value, includeRuns: false).FirstOrDefault() ?? throw new NotFoundProblemException("Сценарий не найден", "SCENE_NOT_FOUND");
    }

    private static void EnsurePositiveId(int value, string message, string code)
    {
        if (value <= 0)
        {
            throw new ValidationProblemException(message, code);
        }
    }

    private void EnsureRuleNameIsUnique(SqliteConnection connection, string name, int? currentRuleId)
    {
        var command = connection.CreateCommand();
        command.CommandText = "SELECT Id FROM AutomationRules WHERE lower(Name) = lower(@name) LIMIT 1;";
        command.Parameters.AddWithValue("@name", name);
        var existing = command.ExecuteScalar();
        if (existing is long id && (!currentRuleId.HasValue || currentRuleId.Value != Convert.ToInt32(id)))
        {
            throw new ConflictProblemException("Правило с таким названием уже существует", "RULE_NAME_EXISTS");
        }
    }

    private void EnsureScheduleNameIsUnique(SqliteConnection connection, string name, int? currentScheduleId)
    {
        var command = connection.CreateCommand();
        command.CommandText = "SELECT Id FROM Schedules WHERE lower(Name) = lower(@name) LIMIT 1;";
        command.Parameters.AddWithValue("@name", name);
        var existing = command.ExecuteScalar();
        if (existing is long id && (!currentScheduleId.HasValue || currentScheduleId.Value != Convert.ToInt32(id)))
        {
            throw new ConflictProblemException("Расписание с таким названием уже существует", "SCHEDULE_NAME_EXISTS");
        }
    }

    private static string NormalizeTimeOfDay(string? value)
    {
        var clean = NormalizeRequired(value, "Нужно указать время", "SCHEDULE_TIME_REQUIRED");
        if (!TimeOnly.TryParseExact(clean, "HH:mm", CultureInfo.InvariantCulture, DateTimeStyles.None, out var time))
        {
            throw new ValidationProblemException("Время должно быть в формате HH:mm", "SCHEDULE_TIME_INVALID");
        }
        return time.ToString("HH:mm");
    }

    private static List<int> NormalizeDaysOfWeek(IReadOnlyList<int>? days)
    {
        var result = (days ?? Array.Empty<int>()).Distinct().OrderBy(x => x).Where(x => x is >= 1 and <= 7).ToList();
        if (result.Count == 0)
        {
            throw new ValidationProblemException("Нужно выбрать хотя бы один день недели", "SCHEDULE_DAYS_REQUIRED");
        }
        return result;
    }

    private static string SerializeDays(IEnumerable<int> days)
    {
        return string.Join(',', days.OrderBy(x => x));
    }

    private static List<int> DeserializeDays(string raw)
    {
        return raw.Split(',', StringSplitOptions.RemoveEmptyEntries)
            .Select(part => int.TryParse(part, out var day) ? day : 0)
            .Where(day => day is >= 1 and <= 7)
            .Distinct()
            .OrderBy(day => day)
            .ToList();
    }

    private static int MapDayOfWeek(DayOfWeek value)
    {
        return value switch
        {
            DayOfWeek.Monday => 1,
            DayOfWeek.Tuesday => 2,
            DayOfWeek.Wednesday => 3,
            DayOfWeek.Thursday => 4,
            DayOfWeek.Friday => 5,
            DayOfWeek.Saturday => 6,
            _ => 7,
        };
    }

    private Device ResolveDeviceByReference(SqliteConnection connection, int? deviceId, string? deviceExternalId)
    {
        if (deviceId.HasValue)
        {
            if (deviceId.Value <= 0)
            {
                throw new ValidationProblemException("deviceId должен быть положительным числом", "EVENT_DEVICE_ID_INVALID");
            }
            return ReadDeviceOrThrow(connection, deviceId.Value);
        }

        if (string.IsNullOrWhiteSpace(deviceExternalId))
        {
            throw new ValidationProblemException("Нужно указать deviceId или deviceExternalId", "EVENT_DEVICE_REFERENCE_REQUIRED");
        }
        var cleanExternalId = NormalizeExternalId(deviceExternalId);
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
WHERE lower(COALESCE(d.ExternalId, '')) = lower(@externalId)
LIMIT 1;";
        command.Parameters.AddWithValue("@externalId", cleanExternalId);
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

    private List<AutomationRule> ReadEnabledRulesForEvent(SqliteConnection connection, int triggerDeviceId, string eventType)
    {
        var command = connection.CreateCommand();
        command.CommandText = @"
SELECT ar.Id,
       ar.Name,
       ar.Description,
       ar.IsEnabled,
       ar.TriggerDeviceId,
       ar.TriggerEventType,
       ar.ComparisonOperator,
       ar.CompareValue,
       ar.ActionKind,
       ar.ActionDeviceId,
       ar.ActionTargetIsOn,
       ar.ActionSceneId,
       ar.CreatedAt,
       ar.UpdatedAt,
       ar.LastTriggeredAt,
       ar.LastTriggerStatus,
       ar.LastTriggerMessage,
       COALESCE(td.Name, ''),
       ad.Name,
       s.Name
FROM AutomationRules ar
LEFT JOIN Devices td ON td.Id = ar.TriggerDeviceId
LEFT JOIN Devices ad ON ad.Id = ar.ActionDeviceId
LEFT JOIN Scenes s ON s.Id = ar.ActionSceneId
WHERE ar.IsEnabled = 1 AND ar.TriggerDeviceId = @triggerDeviceId AND lower(ar.TriggerEventType) = lower(@eventType)
ORDER BY ar.Name;";
        command.Parameters.AddWithValue("@triggerDeviceId", triggerDeviceId);
        command.Parameters.AddWithValue("@eventType", eventType);
        return ReadRulesFromCommand(connection, command);
    }

    private bool RuleMatches(AutomationRule rule, string eventValue)
    {
        var op = rule.ComparisonOperator;
        var expected = rule.CompareValue;

        if (double.TryParse(eventValue.Replace(',', '.'), NumberStyles.Any, CultureInfo.InvariantCulture, out var eventNumber)
            && double.TryParse(expected.Replace(',', '.'), NumberStyles.Any, CultureInfo.InvariantCulture, out var expectedNumber))
        {
            return op switch
            {
                "=" => Math.Abs(eventNumber - expectedNumber) < 0.0001,
                "!=" => Math.Abs(eventNumber - expectedNumber) >= 0.0001,
                ">" => eventNumber > expectedNumber,
                ">=" => eventNumber >= expectedNumber,
                "<" => eventNumber < expectedNumber,
                "<=" => eventNumber <= expectedNumber,
                _ => false,
            };
        }

        return op switch
        {
            "=" => string.Equals(eventValue, expected, StringComparison.OrdinalIgnoreCase),
            "!=" => !string.Equals(eventValue, expected, StringComparison.OrdinalIgnoreCase),
            "contains" => eventValue.Contains(expected, StringComparison.OrdinalIgnoreCase),
            _ => false,
        };
    }

    private RuleRun ExecuteRuleInternal(SqliteConnection connection, SqliteTransaction transaction, AutomationRule rule, Device sourceDevice, string eventType, string eventValue)
    {
        var (status, message) = ExecuteActionInternal(connection, transaction, rule.ActionKind, rule.ActionDeviceId, rule.ActionTargetIsOn, rule.ActionSceneId, $"Правило «{rule.Name}»");
        var triggeredAt = DateTime.UtcNow;

        var insertRun = connection.CreateCommand();
        insertRun.Transaction = transaction;
        insertRun.CommandText = @"
INSERT INTO RuleRuns (RuleId, SourceDeviceId, EventType, EventValue, TriggeredAt, Status, Message)
VALUES (@ruleId, @sourceDeviceId, @eventType, @eventValue, @triggeredAt, @status, @message);
SELECT last_insert_rowid();";
        insertRun.Parameters.AddWithValue("@ruleId", rule.Id);
        insertRun.Parameters.AddWithValue("@sourceDeviceId", sourceDevice.Id);
        insertRun.Parameters.AddWithValue("@eventType", eventType);
        insertRun.Parameters.AddWithValue("@eventValue", eventValue);
        insertRun.Parameters.AddWithValue("@triggeredAt", triggeredAt.ToString("O"));
        insertRun.Parameters.AddWithValue("@status", status);
        insertRun.Parameters.AddWithValue("@message", message);
        var runId = Convert.ToInt32((long)(insertRun.ExecuteScalar() ?? 0));

        var updateRule = connection.CreateCommand();
        updateRule.Transaction = transaction;
        updateRule.CommandText = @"
UPDATE AutomationRules
SET LastTriggeredAt = @lastTriggeredAt,
    LastTriggerStatus = @lastTriggerStatus,
    LastTriggerMessage = @lastTriggerMessage,
    UpdatedAt = @updatedAt
WHERE Id = @id;";
        updateRule.Parameters.AddWithValue("@lastTriggeredAt", triggeredAt.ToString("O"));
        updateRule.Parameters.AddWithValue("@lastTriggerStatus", status);
        updateRule.Parameters.AddWithValue("@lastTriggerMessage", message);
        updateRule.Parameters.AddWithValue("@updatedAt", triggeredAt.ToString("O"));
        updateRule.Parameters.AddWithValue("@id", rule.Id);
        updateRule.ExecuteNonQuery();

        LogEvent(connection, transaction, status == "completed" ? "info" : "warning", "rule-engine", "RULE_TRIGGERED", message, deviceId: sourceDevice.Id, sceneId: rule.ActionSceneId, runId: runId);

        return new RuleRun
        {
            Id = runId,
            RuleId = rule.Id,
            RuleName = rule.Name,
            SourceDeviceId = sourceDevice.Id,
            SourceDeviceName = sourceDevice.Name,
            EventType = eventType,
            EventValue = eventValue,
            TriggeredAt = triggeredAt,
            Status = status,
            Message = message,
        };
    }

    private ScheduleRun ExecuteScheduleInternal(SqliteConnection connection, SqliteTransaction transaction, ScheduleEntry schedule, string slot)
    {
        var (status, message) = ExecuteActionInternal(connection, transaction, schedule.ActionKind, schedule.ActionDeviceId, schedule.ActionTargetIsOn, schedule.ActionSceneId, $"Расписание «{schedule.Name}»");
        var triggeredAt = DateTime.UtcNow;

        var insertRun = connection.CreateCommand();
        insertRun.Transaction = transaction;
        insertRun.CommandText = @"
INSERT INTO ScheduleRuns (ScheduleId, ScheduledSlot, TriggeredAt, Status, Message)
VALUES (@scheduleId, @scheduledSlot, @triggeredAt, @status, @message);
SELECT last_insert_rowid();";
        insertRun.Parameters.AddWithValue("@scheduleId", schedule.Id);
        insertRun.Parameters.AddWithValue("@scheduledSlot", slot);
        insertRun.Parameters.AddWithValue("@triggeredAt", triggeredAt.ToString("O"));
        insertRun.Parameters.AddWithValue("@status", status);
        insertRun.Parameters.AddWithValue("@message", message);
        var runId = Convert.ToInt32((long)(insertRun.ExecuteScalar() ?? 0));

        var updateSchedule = connection.CreateCommand();
        updateSchedule.Transaction = transaction;
        updateSchedule.CommandText = @"
UPDATE Schedules
SET LastRunAt = @lastRunAt,
    LastRunStatus = @lastRunStatus,
    LastRunMessage = @lastRunMessage,
    LastTriggeredSlot = @lastTriggeredSlot,
    UpdatedAt = @updatedAt
WHERE Id = @id;";
        updateSchedule.Parameters.AddWithValue("@lastRunAt", triggeredAt.ToString("O"));
        updateSchedule.Parameters.AddWithValue("@lastRunStatus", status);
        updateSchedule.Parameters.AddWithValue("@lastRunMessage", message);
        updateSchedule.Parameters.AddWithValue("@lastTriggeredSlot", slot);
        updateSchedule.Parameters.AddWithValue("@updatedAt", triggeredAt.ToString("O"));
        updateSchedule.Parameters.AddWithValue("@id", schedule.Id);
        updateSchedule.ExecuteNonQuery();

        LogEvent(connection, transaction, status == "completed" ? "info" : "warning", "scheduler", "SCHEDULE_TRIGGERED", message, deviceId: schedule.ActionDeviceId, sceneId: schedule.ActionSceneId, runId: runId);

        return new ScheduleRun
        {
            Id = runId,
            ScheduleId = schedule.Id,
            ScheduleName = schedule.Name,
            ScheduledSlot = slot,
            TriggeredAt = triggeredAt,
            Status = status,
            Message = message,
        };
    }

    private (string Status, string Message) ExecuteActionInternal(SqliteConnection connection, SqliteTransaction transaction, string actionKind, int? actionDeviceId, bool? actionTargetIsOn, int? actionSceneId, string prefix)
    {
        if (string.Equals(actionKind, "device_state", StringComparison.OrdinalIgnoreCase))
        {
            if (!actionDeviceId.HasValue || !actionTargetIsOn.HasValue)
            {
                throw new ValidationProblemException("Для действия устройства нужно указать устройство и целевое состояние", "ACTION_DEVICE_STATE_INVALID");
            }

            var device = ReadDeviceOrThrow(connection, actionDeviceId.Value);
            var commandResult = ExecuteDeviceStateCommand(device, actionTargetIsOn.Value);
            UpdateDeviceStateAfterCommand(connection, transaction, device, actionTargetIsOn.Value, commandResult);

            return commandResult.Ok
                ? ("completed", $"{prefix} установило устройство «{device.Name}» в состояние {(actionTargetIsOn.Value ? "ON" : "OFF")}. {commandResult.Message}")
                : ("failed", $"{prefix} не смогло установить устройство «{device.Name}» в состояние {(actionTargetIsOn.Value ? "ON" : "OFF")}: {commandResult.Message}");
        }

        if (!actionSceneId.HasValue)
        {
            throw new ValidationProblemException("Для запуска сценария нужно указать sceneId", "ACTION_SCENE_REQUIRED");
        }

        var scene = ReadScenes(connection, actionSceneId.Value, includeRuns: false).FirstOrDefault() ?? throw new NotFoundProblemException("Сценарий не найден", "SCENE_NOT_FOUND");
        if (scene.Actions.Count == 0)
        {
            throw new ValidationProblemException("В выбранном сценарии нет действий", "SCENE_EMPTY");
        }

        var startedAt = DateTime.UtcNow;
        var createRun = connection.CreateCommand();
        createRun.Transaction = transaction;
        createRun.CommandText = @"
INSERT INTO SceneRuns (SceneId, StartedAt, CompletedAt, Status, Message)
VALUES (@sceneId, @startedAt, NULL, @status, @message);
SELECT last_insert_rowid();";
        createRun.Parameters.AddWithValue("@sceneId", scene.Id);
        createRun.Parameters.AddWithValue("@startedAt", startedAt.ToString("O"));
        createRun.Parameters.AddWithValue("@status", "running");
        createRun.Parameters.AddWithValue("@message", $"{prefix} запустило сценарий");
        var runId = Convert.ToInt32((long)(createRun.ExecuteScalar() ?? 0));

        var failures = new List<string>();
        foreach (var action in scene.Actions.OrderBy(x => x.SortOrder))
        {
            var device = ReadDeviceOrThrow(connection, action.DeviceId);
            var commandResult = ExecuteDeviceStateCommand(device, action.TargetIsOn);
            UpdateDeviceStateAfterCommand(connection, transaction, device, action.TargetIsOn, commandResult);
            if (!commandResult.Ok)
            {
                failures.Add($"{action.DeviceName}: {commandResult.Message}");
            }
        }

        var completedAt = DateTime.UtcNow;
        var runStatus = failures.Count == 0 ? "completed" : "failed";
        var message = failures.Count == 0
            ? $"{prefix} запустило сценарий «{scene.Name}»"
            : $"{prefix} запустило сценарий «{scene.Name}» с ошибками: {string.Join("; ", failures)}";

        var finishRun = connection.CreateCommand();
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

        var updateScene = connection.CreateCommand();
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
        updateScene.Parameters.AddWithValue("@sceneId", scene.Id);
        updateScene.ExecuteNonQuery();

        return (runStatus, message);
    }

    private List<AutomationRule> ReadRules(SqliteConnection connection, int? ruleId)
    {
        var command = connection.CreateCommand();
        command.CommandText = @"
SELECT ar.Id,
       ar.Name,
       ar.Description,
       ar.IsEnabled,
       ar.TriggerDeviceId,
       ar.TriggerEventType,
       ar.ComparisonOperator,
       ar.CompareValue,
       ar.ActionKind,
       ar.ActionDeviceId,
       ar.ActionTargetIsOn,
       ar.ActionSceneId,
       ar.CreatedAt,
       ar.UpdatedAt,
       ar.LastTriggeredAt,
       ar.LastTriggerStatus,
       ar.LastTriggerMessage,
       COALESCE(td.Name, ''),
       ad.Name,
       s.Name
FROM AutomationRules ar
LEFT JOIN Devices td ON td.Id = ar.TriggerDeviceId
LEFT JOIN Devices ad ON ad.Id = ar.ActionDeviceId
LEFT JOIN Scenes s ON s.Id = ar.ActionSceneId
WHERE (@id IS NULL OR ar.Id = @id)
ORDER BY ar.Name;";
        command.Parameters.AddWithValue("@id", (object?)ruleId ?? DBNull.Value);
        return ReadRulesFromCommand(connection, command);
    }

    private List<AutomationRule> ReadRulesFromCommand(SqliteConnection connection, SqliteCommand command)
    {
        var rules = new List<AutomationRule>();
        using var reader = command.ExecuteReader();
        while (reader.Read())
        {
            rules.Add(new AutomationRule
            {
                Id = reader.GetInt32(0),
                Name = reader.GetString(1),
                Description = reader.GetString(2),
                IsEnabled = reader.GetInt32(3) == 1,
                TriggerDeviceId = reader.GetInt32(4),
                TriggerEventType = reader.GetString(5),
                ComparisonOperator = reader.GetString(6),
                CompareValue = reader.GetString(7),
                ActionKind = reader.GetString(8),
                ActionDeviceId = reader.IsDBNull(9) ? null : reader.GetInt32(9),
                ActionTargetIsOn = reader.IsDBNull(10) ? null : reader.GetInt32(10) == 1,
                ActionSceneId = reader.IsDBNull(11) ? null : reader.GetInt32(11),
                CreatedAt = ParseUtc(reader.GetString(12)),
                UpdatedAt = ParseUtc(reader.GetString(13)),
                LastTriggeredAt = reader.IsDBNull(14) ? null : ParseUtc(reader.GetString(14)),
                LastTriggerStatus = reader.IsDBNull(15) ? null : reader.GetString(15),
                LastTriggerMessage = reader.IsDBNull(16) ? null : reader.GetString(16),
                TriggerDeviceName = reader.GetString(17),
                ActionDeviceName = reader.IsDBNull(18) ? null : reader.GetString(18),
                ActionSceneName = reader.IsDBNull(19) ? null : reader.GetString(19),
            });
        }

        return rules;
    }

    private List<RuleRun> ReadRuleRuns(SqliteConnection connection, int ruleId, int limit)
    {
        var runs = new List<RuleRun>();
        var command = connection.CreateCommand();
        command.CommandText = @"
SELECT rr.Id, rr.RuleId, ar.Name, rr.SourceDeviceId, d.Name, rr.EventType, rr.EventValue, rr.TriggeredAt, rr.Status, rr.Message
FROM RuleRuns rr
INNER JOIN AutomationRules ar ON ar.Id = rr.RuleId
INNER JOIN Devices d ON d.Id = rr.SourceDeviceId
WHERE rr.RuleId = @ruleId
ORDER BY rr.TriggeredAt DESC, rr.Id DESC
LIMIT @limit;";
        command.Parameters.AddWithValue("@ruleId", ruleId);
        command.Parameters.AddWithValue("@limit", Math.Clamp(limit, 1, 100));
        using var reader = command.ExecuteReader();
        while (reader.Read())
        {
            runs.Add(new RuleRun
            {
                Id = reader.GetInt32(0),
                RuleId = reader.GetInt32(1),
                RuleName = reader.GetString(2),
                SourceDeviceId = reader.GetInt32(3),
                SourceDeviceName = reader.GetString(4),
                EventType = reader.GetString(5),
                EventValue = reader.GetString(6),
                TriggeredAt = ParseUtc(reader.GetString(7)),
                Status = reader.GetString(8),
                Message = reader.GetString(9),
            });
        }
        return runs;
    }

    private List<ScheduleEntry> ReadSchedules(SqliteConnection connection, int? scheduleId)
    {
        var schedules = new List<ScheduleEntry>();
        var command = connection.CreateCommand();
        command.CommandText = @"
SELECT Id, Name, Description, IsEnabled, TimeOfDay, DaysOfWeek, ActionKind, ActionDeviceId, ActionTargetIsOn, ActionSceneId, CreatedAt, UpdatedAt, LastRunAt, LastRunStatus, LastRunMessage, LastTriggeredSlot
FROM Schedules
WHERE (@id IS NULL OR Id = @id)
ORDER BY TimeOfDay, Name;";
        command.Parameters.AddWithValue("@id", (object?)scheduleId ?? DBNull.Value);
        using var reader = command.ExecuteReader();
        while (reader.Read())
        {
            schedules.Add(new ScheduleEntry
            {
                Id = reader.GetInt32(0),
                Name = reader.GetString(1),
                Description = reader.GetString(2),
                IsEnabled = reader.GetInt32(3) == 1,
                TimeOfDay = reader.GetString(4),
                DaysOfWeek = DeserializeDays(reader.GetString(5)),
                ActionKind = reader.GetString(6),
                ActionDeviceId = reader.IsDBNull(7) ? null : reader.GetInt32(7),
                ActionTargetIsOn = reader.IsDBNull(8) ? null : reader.GetInt32(8) == 1,
                ActionSceneId = reader.IsDBNull(9) ? null : reader.GetInt32(9),
                CreatedAt = ParseUtc(reader.GetString(10)),
                UpdatedAt = ParseUtc(reader.GetString(11)),
                LastRunAt = reader.IsDBNull(12) ? null : ParseUtc(reader.GetString(12)),
                LastRunStatus = reader.IsDBNull(13) ? null : reader.GetString(13),
                LastRunMessage = reader.IsDBNull(14) ? null : reader.GetString(14),
                LastTriggeredSlot = reader.GetString(15),
            });
        }

        foreach (var schedule in schedules)
        {
            if (schedule.ActionDeviceId.HasValue)
            {
                schedule.ActionDeviceName = ReadDeviceOrThrow(connection, schedule.ActionDeviceId.Value).Name;
            }
            if (schedule.ActionSceneId.HasValue)
            {
                schedule.ActionSceneName = ReadScenes(connection, schedule.ActionSceneId.Value, includeRuns: false).FirstOrDefault()?.Name;
            }
        }

        return schedules;
    }

    private List<ScheduleRun> ReadScheduleRuns(SqliteConnection connection, int scheduleId, int limit)
    {
        var runs = new List<ScheduleRun>();
        var command = connection.CreateCommand();
        command.CommandText = @"
SELECT sr.Id, sr.ScheduleId, s.Name, sr.ScheduledSlot, sr.TriggeredAt, sr.Status, sr.Message
FROM ScheduleRuns sr
INNER JOIN Schedules s ON s.Id = sr.ScheduleId
WHERE sr.ScheduleId = @scheduleId
ORDER BY sr.TriggeredAt DESC, sr.Id DESC
LIMIT @limit;";
        command.Parameters.AddWithValue("@scheduleId", scheduleId);
        command.Parameters.AddWithValue("@limit", Math.Clamp(limit, 1, 100));
        using var reader = command.ExecuteReader();
        while (reader.Read())
        {
            runs.Add(new ScheduleRun
            {
                Id = reader.GetInt32(0),
                ScheduleId = reader.GetInt32(1),
                ScheduleName = reader.GetString(2),
                ScheduledSlot = reader.GetString(3),
                TriggeredAt = ParseUtc(reader.GetString(4)),
                Status = reader.GetString(5),
                Message = reader.GetString(6),
            });
        }
        return runs;
    }

    private sealed record ConnectionValidationResult(bool Ok, string Status, string Message, Dictionary<string, string> Connection);

    private sealed record DeviceCommandResult(bool Ok, string Status, string Message);
}
