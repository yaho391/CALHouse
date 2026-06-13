using CalHouse.Api.Infrastructure;
using CalHouse.Api.Models;
using Microsoft.Data.Sqlite;

namespace CalHouse.Api.Services;

public partial class DeviceStore
{
    public Device QueueToggleDevice(int id, DeviceCommandQueue queue)
    {
        ArgumentNullException.ThrowIfNull(queue);

        var executeImmediately = false;
        lock (_sync)
        {
            using var db = OpenConnection();
            var current = ReadDeviceOrThrow(db, id);
            executeImmediately = IsImmediateLocalDevice(current);
        }

        if (executeImmediately)
        {
            return ToggleDevice(id);
        }

        bool targetIsOn;
        Device queuedDevice;
        lock (_sync)
        {
            using var db = OpenConnection();
            var current = ReadDeviceOrThrow(db, id);
            targetIsOn = !current.IsOn;

            using var transaction = db.BeginTransaction();
            MarkDeviceCommandPending(db, transaction, current, $"Toggle accepted: {(targetIsOn ? "ON" : "OFF")}");
            transaction.Commit();

            SyncLegacyDevicesJson(db);
            queuedDevice = ReadDeviceOrThrow(db, id);
        }

        queue.Queue(_ =>
        {
            ExecuteQueuedDeviceStateCommand(id, targetIsOn, "device-command-worker");
            return ValueTask.CompletedTask;
        });

        return queuedDevice;
    }

    private bool IsImmediateLocalDevice(Device device)
    {
        var provider = _catalog.NormalizeProviderCode(device.Provider);
        var protocol = NormalizeOptional(device.Protocol, _catalog.InferProtocol(provider)).ToLowerInvariant();
        return provider is "mock" or "demo" || protocol is "manual" or "demo";
    }

    public SceneRun QueueSceneRun(int id, DeviceCommandQueue queue)
    {
        ArgumentNullException.ThrowIfNull(queue);

        SceneRun queuedRun;
        int runId;
        lock (_sync)
        {
            using var db = OpenConnection();
            var scene = ReadScenes(db, id, includeRuns: false).FirstOrDefault()
                ?? throw new NotFoundProblemException("Сценарий не найден", "SCENE_NOT_FOUND");
            if (scene.Actions.Count == 0)
            {
                throw new ValidationProblemException("В сценарии нет действий", "SCENE_EMPTY");
            }

            using var transaction = db.BeginTransaction();
            runId = CreatePendingSceneRun(db, transaction, scene, "Scene run accepted");
            UpdateSceneRunState(db, transaction, scene.Id, DateTime.UtcNow, "pending", "Scene run accepted");
            transaction.Commit();

            queuedRun = ReadSceneRunOrThrow(db, runId);
        }

        queue.Queue(_ =>
        {
            RunQueuedSceneRunCore(id, runId, "scene-command-worker");
            return ValueTask.CompletedTask;
        });

        return queuedRun;
    }

    public ScheduleRunBatchResult QueueDueSchedules(DeviceCommandQueue queue, DateTime? nowLocal = null)
    {
        ArgumentNullException.ThrowIfNull(queue);

        var queuedRuns = new List<(int ScheduleId, int RunId, string Slot)>();
        var result = new ScheduleRunBatchResult();

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);

            var now = nowLocal ?? DateTime.Now;
            var slot = now.ToString("yyyy-MM-dd HH:mm");
            var timeOfDay = now.ToString("HH:mm");
            var day = MapDayOfWeek(now.DayOfWeek);
            var schedules = ReadSchedules(db, null)
                .Where(s => s.IsEnabled && s.TimeOfDay == timeOfDay && s.DaysOfWeek.Contains(day) && !string.Equals(s.LastTriggeredSlot, slot, StringComparison.Ordinal))
                .ToList();

            result.Slot = slot;
            result.Message = schedules.Count == 0 ? "No due schedules" : $"Queued schedules: {schedules.Count}";
            if (schedules.Count == 0)
            {
                return result;
            }

            using var transaction = db.BeginTransaction();
            foreach (var schedule in schedules)
            {
                var run = CreatePendingScheduleRun(db, transaction, schedule, slot, "Schedule accepted");
                UpdateScheduleRunState(db, transaction, schedule.Id, slot, "pending", "Schedule accepted");
                result.Runs.Add(run);
                queuedRuns.Add((schedule.Id, run.Id, slot));
            }
            transaction.Commit();
        }

        foreach (var queued in queuedRuns)
        {
            queue.Queue(_ =>
            {
                ExecuteQueuedScheduleRun(queued.ScheduleId, queued.RunId, queued.Slot);
                return ValueTask.CompletedTask;
            });
        }

        return result;
    }

    public DeviceEventResult ProcessIncomingEventQueued(int? deviceId, string? deviceExternalId, string eventType, string value, string? message, DeviceCommandQueue queue, string? source = null)
    {
        ArgumentNullException.ThrowIfNull(queue);

        var cleanEventType = NormalizeEventTypeAlias(NormalizeCodeValue(eventType, "Тип события обязателен", "EVENT_TYPE_REQUIRED", MaxChannelLength, "Тип события может содержать только латиницу, цифры, точку, дефис и подчёркивание", "EVENT_TYPE_INVALID"));
        var cleanValue = NormalizeRequiredBounded(value, "Значение события обязательно", "EVENT_VALUE_REQUIRED", MaxEventValueLength, "Значение события слишком длинное", "EVENT_VALUE_TOO_LONG");
        var cleanMessage = NormalizeFreeTextOptional(message, "Сообщение события", 1000, "EVENT_MESSAGE_INVALID");
        var cleanSource = NormalizeEventSource(source);
        var queuedRuns = new List<(int RuleId, int RunId)>();

        DeviceEventResult result;
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
            touchDevice.Parameters.AddWithValue("@connectionMessage", string.IsNullOrWhiteSpace(cleanMessage) ? $"Received event {cleanEventType}" : cleanMessage);
            touchDevice.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            touchDevice.Parameters.AddWithValue("@id", sourceDevice.Id);
            touchDevice.ExecuteNonQuery();

            LogEvent(db, transaction, "info", cleanSource, "DEVICE_EVENT_RECEIVED", $"Event \"{cleanEventType}={cleanValue}\" received from device \"{sourceDevice.Name}\"", deviceId: sourceDevice.Id, roomId: sourceDevice.RoomId);

            var triggered = new List<RuleRun>();
            foreach (var rule in ReadEnabledRulesForEvent(db, sourceDevice.Id, cleanEventType))
            {
                if (!RuleMatches(rule, cleanValue))
                {
                    continue;
                }

                if (IsVisualDemoSource(cleanSource) && !IsVisualDemoRuleSafe(db, rule))
                {
                    LogEvent(
                        db,
                        transaction,
                        "warning",
                        "visual_demo",
                        "VISUAL_RULE_SKIPPED",
                        $"visual_demo: rule \"{rule.Name}\" skipped because its action is not limited to demo devices",
                        deviceId: sourceDevice.Id,
                        sceneId: rule.ActionSceneId);
                    continue;
                }

                var run = CreatePendingRuleRun(db, transaction, rule, sourceDevice, cleanEventType, cleanValue, "Rule accepted");
                triggered.Add(run);
                queuedRuns.Add((rule.Id, run.Id));
            }

            transaction.Commit();
            SyncLegacyDevicesJson(db);

            result = new DeviceEventResult
            {
                SourceDeviceId = sourceDevice.Id,
                SourceDeviceName = sourceDevice.Name,
                EventType = cleanEventType,
                EventValue = cleanValue,
                TriggeredRules = triggered,
                Message = triggered.Count == 0 ? "Подходящих правил не найдено" : $"Правил принято к выполнению: {triggered.Count}",
            };
        }

        foreach (var queued in queuedRuns)
        {
            queue.Queue(_ =>
            {
                ExecuteQueuedRuleRun(queued.RuleId, queued.RunId);
                return ValueTask.CompletedTask;
            });
        }

        return result;
    }

    private static string NormalizeEventTypeAlias(string eventType)
    {
        return eventType.Trim().ToLowerInvariant() switch
        {
            "leak" => "water_leak",
            "temperature_changed" => "temperature",
            _ => eventType.Trim().ToLowerInvariant(),
        };
    }

    private static string NormalizeEventSource(string? source)
    {
        var clean = NormalizeOptional(source, "event-ingest").Trim().ToLowerInvariant();
        return clean is "visual_demo" or "demo" ? clean : "event-ingest";
    }

    private static bool IsVisualDemoSource(string source)
    {
        return source is "visual_demo" or "demo";
    }

    private bool IsVisualDemoRuleSafe(SqliteConnection db, AutomationRule rule)
    {
        if (string.Equals(rule.ActionKind, "device_state", StringComparison.OrdinalIgnoreCase))
        {
            if (!rule.ActionDeviceId.HasValue)
            {
                return false;
            }

            var target = ReadDeviceOrThrow(db, rule.ActionDeviceId.Value);
            return IsVisualDemoDevice(target);
        }

        // Visual demo events must not launch ordinary scenes because a scene can
        // contain real devices. Built-in visual scenarios use /api/visual-demo.
        return false;
    }

    private void ExecuteQueuedDeviceStateCommand(int id, bool targetIsOn, string source)
    {
        Device device;
        lock (_sync)
        {
            using var db = OpenConnection();
            device = ReadDeviceOrThrow(db, id);
        }

        DeviceCommandResult commandResult;
        try
        {
            commandResult = ExecuteDeviceStateCommand(device, targetIsOn);
        }
        catch (Exception ex)
        {
            commandResult = new DeviceCommandResult(false, "failed", $"Command failed: {ex.Message}");
        }

        CommitDeviceCommandResult(id, targetIsOn, commandResult, source, "DEVICE_COMMAND_COMPLETED", "DEVICE_COMMAND_FAILED");
    }

    private void ExecuteQueuedRuleRun(int ruleId, int runId)
    {
        AutomationRule rule;
        RuleRun run;
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            rule = ReadRules(db, ruleId).FirstOrDefault()
                ?? throw new NotFoundProblemException("Правило не найдено", "RULE_NOT_FOUND");
            run = ReadRuleRunOrThrow(db, runId);
        }

        string status;
        string resultMessage;
        try
        {
            if (string.Equals(rule.ActionKind, "device_state", StringComparison.OrdinalIgnoreCase))
            {
                if (!rule.ActionDeviceId.HasValue || !rule.ActionTargetIsOn.HasValue)
                {
                    throw new ValidationProblemException("Rule device action is invalid", "RULE_ACTION_DEVICE_INVALID");
                }

                Device device;
                lock (_sync)
                {
                    using var db = OpenConnection();
                    device = ReadDeviceOrThrow(db, rule.ActionDeviceId.Value);
                }

                var commandResult = ExecuteDeviceStateCommand(device, rule.ActionTargetIsOn.Value);
                CommitDeviceCommandResult(rule.ActionDeviceId.Value, rule.ActionTargetIsOn.Value, commandResult, "rule-worker", "RULE_DEVICE_ACTION_COMPLETED", "RULE_DEVICE_ACTION_FAILED");
                status = commandResult.Ok ? "completed" : "failed";
                resultMessage = commandResult.Ok
                    ? $"Rule \"{rule.Name}\" set device \"{device.Name}\" to {(rule.ActionTargetIsOn.Value ? "ON" : "OFF")}. {commandResult.Message}"
                    : $"Rule \"{rule.Name}\" failed to set device \"{device.Name}\" to {(rule.ActionTargetIsOn.Value ? "ON" : "OFF")}: {commandResult.Message}";
            }
            else
            {
                if (!rule.ActionSceneId.HasValue)
                {
                    throw new ValidationProblemException("Rule scene action is invalid", "RULE_ACTION_SCENE_INVALID");
                }

                int sceneRunId;
                Scene scene;
                lock (_sync)
                {
                    using var db = OpenConnection();
                    scene = ReadScenes(db, rule.ActionSceneId.Value, includeRuns: false).FirstOrDefault()
                        ?? throw new NotFoundProblemException("Сценарий не найден", "SCENE_NOT_FOUND");
                    using var transaction = db.BeginTransaction();
                    sceneRunId = CreatePendingSceneRun(db, transaction, scene, $"Rule \"{rule.Name}\" accepted scene run");
                    UpdateSceneRunState(db, transaction, scene.Id, DateTime.UtcNow, "pending", $"Rule \"{rule.Name}\" accepted scene run");
                    LogEvent(db, transaction, "info", "rule-worker", "SCENE_RUN_ACCEPTED", $"Rule \"{rule.Name}\" accepted scene \"{scene.Name}\" for background execution", sceneId: scene.Id, runId: sceneRunId);
                    transaction.Commit();
                }

                var sceneResult = RunQueuedSceneRunCore(scene.Id, sceneRunId, "rule-worker");
                status = sceneResult.Ok ? "completed" : "failed";
                resultMessage = sceneResult.Ok
                    ? $"Rule \"{rule.Name}\" ran scene \"{scene.Name}\". {sceneResult.Message}"
                    : $"Rule \"{rule.Name}\" ran scene \"{scene.Name}\" with errors: {sceneResult.Message}";
            }
        }
        catch (Exception ex)
        {
            status = "failed";
            resultMessage = $"Rule \"{rule.Name}\" failed: {ex.Message}";
        }

        lock (_sync)
        {
            using var db = OpenConnection();
            using var transaction = db.BeginTransaction();
            FinishRuleRun(db, transaction, rule.Id, run.Id, run.SourceDeviceId, status, resultMessage);
            LogEvent(
                db,
                transaction,
                status == "completed" ? "info" : "warning",
                "rule-worker",
                status == "completed" ? "RULE_RUN_COMPLETED" : "RULE_RUN_FAILED",
                resultMessage,
                deviceId: run.SourceDeviceId,
                sceneId: rule.ActionSceneId,
                runId: run.Id);
            transaction.Commit();
            SyncLegacyDevicesJson(db);
        }
    }

    private (bool Ok, string Message) RunQueuedSceneRunCore(int sceneId, int runId, string source)
    {
        Scene scene;
        lock (_sync)
        {
            using var db = OpenConnection();
            scene = ReadScenes(db, sceneId, includeRuns: false).FirstOrDefault()
                ?? throw new NotFoundProblemException("Сценарий не найден", "SCENE_NOT_FOUND");
        }

        var failures = new List<string>();
        foreach (var action in scene.Actions.OrderBy(x => x.SortOrder))
        {
            Device device;
            lock (_sync)
            {
                using var db = OpenConnection();
                device = ReadDeviceOrThrow(db, action.DeviceId);
            }

            DeviceCommandResult commandResult;
            try
            {
                commandResult = ExecuteDeviceStateCommand(device, action.TargetIsOn);
            }
            catch (Exception ex)
            {
                commandResult = new DeviceCommandResult(false, "failed", $"Command failed: {ex.Message}");
            }

            lock (_sync)
            {
                using var db = OpenConnection();
                using var transaction = db.BeginTransaction();
                var latest = ReadDeviceOrThrow(db, action.DeviceId);
                UpdateDeviceStateAfterCommand(db, transaction, latest, action.TargetIsOn, commandResult);
                if (!commandResult.Ok)
                {
                    failures.Add($"{action.DeviceName}: {commandResult.Message}");
                }

                LogEvent(
                    db,
                    transaction,
                    commandResult.Ok ? "info" : "warning",
                    source,
                    commandResult.Ok ? "SCENE_DEVICE_ACTION_COMPLETED" : EventTypeForFailedCommand(commandResult, "SCENE_DEVICE_ACTION_FAILED"),
                    commandResult.Ok
                        ? $"Scene \"{scene.Name}\" set device \"{action.DeviceName}\" to {(action.TargetIsOn ? "ON" : "OFF")}. {commandResult.Message}"
                        : $"Scene \"{scene.Name}\" failed to set device \"{action.DeviceName}\" to {(action.TargetIsOn ? "ON" : "OFF")}: {commandResult.Message}",
                    deviceId: action.DeviceId,
                    sceneId: sceneId,
                    runId: runId);
                transaction.Commit();
                SyncLegacyDevicesJson(db);
            }
        }

        var completedAt = DateTime.UtcNow;
        var runStatus = failures.Count == 0 ? "completed" : "failed";
        var message = failures.Count == 0
            ? $"Scene \"{scene.Name}\" completed. Actions: {scene.Actions.Count}"
            : $"Scene \"{scene.Name}\" completed with errors: {string.Join("; ", failures)}";

        lock (_sync)
        {
            using var db = OpenConnection();
            using var transaction = db.BeginTransaction();
            FinishSceneRun(db, transaction, scene.Id, runId, completedAt, runStatus, message);
            LogEvent(db, transaction, failures.Count == 0 ? "info" : "warning", source, failures.Count == 0 ? "SCENE_RUN_COMPLETED" : "SCENE_RUN_FAILED", message, sceneId: scene.Id, runId: runId);
            transaction.Commit();
        }

        return (failures.Count == 0, message);
    }

    private void ExecuteQueuedScheduleRun(int scheduleId, int runId, string slot)
    {
        ScheduleEntry schedule;
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureAutomationSchema(db);
            schedule = ReadSchedules(db, scheduleId).FirstOrDefault()
                ?? throw new NotFoundProblemException("Расписание не найдено", "SCHEDULE_NOT_FOUND");
        }

        string status;
        string message;

        try
        {
            if (string.Equals(schedule.ActionKind, "device_state", StringComparison.OrdinalIgnoreCase))
            {
                if (!schedule.ActionDeviceId.HasValue || !schedule.ActionTargetIsOn.HasValue)
                {
                    throw new ValidationProblemException("Schedule device action is invalid", "SCHEDULE_ACTION_DEVICE_INVALID");
                }

                Device device;
                lock (_sync)
                {
                    using var db = OpenConnection();
                    device = ReadDeviceOrThrow(db, schedule.ActionDeviceId.Value);
                }

                var commandResult = ExecuteDeviceStateCommand(device, schedule.ActionTargetIsOn.Value);
                CommitDeviceCommandResult(schedule.ActionDeviceId.Value, schedule.ActionTargetIsOn.Value, commandResult, "scheduler-worker", "SCHEDULE_DEVICE_ACTION_COMPLETED", "SCHEDULE_DEVICE_ACTION_FAILED");

                status = commandResult.Ok ? "completed" : "failed";
                message = commandResult.Ok
                    ? $"Schedule \"{schedule.Name}\" set device \"{device.Name}\" to {(schedule.ActionTargetIsOn.Value ? "ON" : "OFF")}. {commandResult.Message}"
                    : $"Schedule \"{schedule.Name}\" failed to set device \"{device.Name}\" to {(schedule.ActionTargetIsOn.Value ? "ON" : "OFF")}: {commandResult.Message}";
            }
            else
            {
                if (!schedule.ActionSceneId.HasValue)
                {
                    throw new ValidationProblemException("Schedule scene action is invalid", "SCHEDULE_ACTION_SCENE_INVALID");
                }

                int sceneRunId;
                Scene scene;
                lock (_sync)
                {
                    using var db = OpenConnection();
                    scene = ReadScenes(db, schedule.ActionSceneId.Value, includeRuns: false).FirstOrDefault()
                        ?? throw new NotFoundProblemException("Сценарий не найден", "SCENE_NOT_FOUND");
                    using var transaction = db.BeginTransaction();
                    sceneRunId = CreatePendingSceneRun(db, transaction, scene, $"Schedule \"{schedule.Name}\" accepted scene run");
                    UpdateSceneRunState(db, transaction, scene.Id, DateTime.UtcNow, "pending", $"Schedule \"{schedule.Name}\" accepted scene run");
                    LogEvent(db, transaction, "info", "scheduler-worker", "SCENE_RUN_ACCEPTED", $"Schedule \"{schedule.Name}\" accepted scene \"{scene.Name}\" for background execution", sceneId: scene.Id, runId: sceneRunId);
                    transaction.Commit();
                }

                var sceneResult = RunQueuedSceneRunCore(scene.Id, sceneRunId, "scheduler-worker");
                status = sceneResult.Ok ? "completed" : "failed";
                message = sceneResult.Ok
                    ? $"Schedule \"{schedule.Name}\" ran scene \"{scene.Name}\". {sceneResult.Message}"
                    : $"Schedule \"{schedule.Name}\" ran scene \"{scene.Name}\" with errors: {sceneResult.Message}";
            }
        }
        catch (Exception ex)
        {
            status = "failed";
            message = $"Schedule \"{schedule.Name}\" failed: {ex.Message}";
        }

        lock (_sync)
        {
            using var db = OpenConnection();
            using var transaction = db.BeginTransaction();
            FinishScheduleRun(db, transaction, schedule.Id, runId, slot, status, message);
            LogEvent(
                db,
                transaction,
                status == "completed" ? "info" : "warning",
                "scheduler-worker",
                status == "completed" ? "SCHEDULE_RUN_COMPLETED" : "SCHEDULE_RUN_FAILED",
                message,
                deviceId: schedule.ActionDeviceId,
                sceneId: schedule.ActionSceneId,
                runId: runId);
            transaction.Commit();
            SyncLegacyDevicesJson(db);
        }
    }

    private void CommitDeviceCommandResult(int id, bool targetIsOn, DeviceCommandResult commandResult, string source, string successEventType, string failedEventType)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            var latest = ReadDeviceOrThrow(db, id);
            using var transaction = db.BeginTransaction();
            UpdateDeviceStateAfterCommand(db, transaction, latest, targetIsOn, commandResult);
            LogEvent(
                db,
                transaction,
                commandResult.Ok ? "info" : "warning",
                source,
                commandResult.Ok ? successEventType : EventTypeForFailedCommand(commandResult, failedEventType),
                commandResult.Ok
                    ? $"Command completed for device \"{latest.Name}\": {(targetIsOn ? "ON" : "OFF")}. {commandResult.Message}"
                    : $"Command failed for device \"{latest.Name}\": {(targetIsOn ? "ON" : "OFF")}. {commandResult.Message}",
                deviceId: id,
                roomId: latest.RoomId);
            transaction.Commit();
            SyncLegacyDevicesJson(db);
        }
    }

    private void MarkDeviceCommandPending(SqliteConnection connection, SqliteTransaction transaction, Device device, string message)
    {
        var now = DateTime.UtcNow;
        var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = @"
UPDATE Devices
SET ConnectionStatus = @connectionStatus,
    ConnectionMessage = @connectionMessage,
    LastConnectionCheckAt = @lastConnectionCheckAt,
    UpdatedAt = @updatedAt
WHERE Id = @id;";
        command.Parameters.AddWithValue("@id", device.Id);
        command.Parameters.AddWithValue("@connectionStatus", "pending");
        command.Parameters.AddWithValue("@connectionMessage", message);
        command.Parameters.AddWithValue("@lastConnectionCheckAt", now.ToString("O"));
        command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
        command.ExecuteNonQuery();
    }

    private RuleRun CreatePendingRuleRun(SqliteConnection connection, SqliteTransaction transaction, AutomationRule rule, Device sourceDevice, string eventType, string eventValue, string message)
    {
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
        insertRun.Parameters.AddWithValue("@status", "pending");
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
        updateRule.Parameters.AddWithValue("@lastTriggerStatus", "pending");
        updateRule.Parameters.AddWithValue("@lastTriggerMessage", message);
        updateRule.Parameters.AddWithValue("@updatedAt", triggeredAt.ToString("O"));
        updateRule.Parameters.AddWithValue("@id", rule.Id);
        updateRule.ExecuteNonQuery();

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
            Status = "pending",
            Message = message,
        };
    }

    private RuleRun ReadRuleRunOrThrow(SqliteConnection connection, int runId)
    {
        var command = connection.CreateCommand();
        command.CommandText = @"
SELECT rr.Id, rr.RuleId, ar.Name, rr.SourceDeviceId, d.Name, rr.EventType, rr.EventValue, rr.TriggeredAt, rr.Status, rr.Message
FROM RuleRuns rr
INNER JOIN AutomationRules ar ON ar.Id = rr.RuleId
INNER JOIN Devices d ON d.Id = rr.SourceDeviceId
WHERE rr.Id = @runId;";
        command.Parameters.AddWithValue("@runId", runId);
        using var reader = command.ExecuteReader();
        if (!reader.Read())
        {
            throw new NotFoundProblemException("Запуск правила не найден", "RULE_RUN_NOT_FOUND");
        }

        return new RuleRun
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
        };
    }

    private void FinishRuleRun(SqliteConnection connection, SqliteTransaction transaction, int ruleId, int runId, int sourceDeviceId, string status, string message)
    {
        var now = DateTime.UtcNow;
        var updateRun = connection.CreateCommand();
        updateRun.Transaction = transaction;
        updateRun.CommandText = @"
UPDATE RuleRuns
SET Status = @status,
    Message = @message
WHERE Id = @id;";
        updateRun.Parameters.AddWithValue("@status", status);
        updateRun.Parameters.AddWithValue("@message", message);
        updateRun.Parameters.AddWithValue("@id", runId);
        updateRun.ExecuteNonQuery();

        var updateRule = connection.CreateCommand();
        updateRule.Transaction = transaction;
        updateRule.CommandText = @"
UPDATE AutomationRules
SET LastTriggeredAt = @lastTriggeredAt,
    LastTriggerStatus = @lastTriggerStatus,
    LastTriggerMessage = @lastTriggerMessage,
    UpdatedAt = @updatedAt
WHERE Id = @id;";
        updateRule.Parameters.AddWithValue("@lastTriggeredAt", now.ToString("O"));
        updateRule.Parameters.AddWithValue("@lastTriggerStatus", status);
        updateRule.Parameters.AddWithValue("@lastTriggerMessage", message);
        updateRule.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
        updateRule.Parameters.AddWithValue("@id", ruleId);
        updateRule.ExecuteNonQuery();
    }

    private int CreatePendingSceneRun(SqliteConnection connection, SqliteTransaction transaction, Scene scene, string message)
    {
        var startedAt = DateTime.UtcNow;
        var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = @"
INSERT INTO SceneRuns (SceneId, StartedAt, CompletedAt, Status, Message)
VALUES (@sceneId, @startedAt, NULL, @status, @message);
SELECT last_insert_rowid();";
        command.Parameters.AddWithValue("@sceneId", scene.Id);
        command.Parameters.AddWithValue("@startedAt", startedAt.ToString("O"));
        command.Parameters.AddWithValue("@status", "pending");
        command.Parameters.AddWithValue("@message", message);
        return Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));
    }

    private void UpdateSceneRunState(SqliteConnection connection, SqliteTransaction transaction, int sceneId, DateTime at, string status, string message)
    {
        var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = @"
UPDATE Scenes
SET LastRunAt = @lastRunAt,
    LastRunStatus = @lastRunStatus,
    LastRunMessage = @lastRunMessage,
    UpdatedAt = @updatedAt
WHERE Id = @sceneId;";
        command.Parameters.AddWithValue("@lastRunAt", at.ToString("O"));
        command.Parameters.AddWithValue("@lastRunStatus", status);
        command.Parameters.AddWithValue("@lastRunMessage", message);
        command.Parameters.AddWithValue("@updatedAt", at.ToString("O"));
        command.Parameters.AddWithValue("@sceneId", sceneId);
        command.ExecuteNonQuery();
    }

    private void FinishSceneRun(SqliteConnection connection, SqliteTransaction transaction, int sceneId, int runId, DateTime completedAt, string status, string message)
    {
        var finishRun = connection.CreateCommand();
        finishRun.Transaction = transaction;
        finishRun.CommandText = @"
UPDATE SceneRuns
SET CompletedAt = @completedAt,
    Status = @status,
    Message = @message
WHERE Id = @id;";
        finishRun.Parameters.AddWithValue("@completedAt", completedAt.ToString("O"));
        finishRun.Parameters.AddWithValue("@status", status);
        finishRun.Parameters.AddWithValue("@message", message);
        finishRun.Parameters.AddWithValue("@id", runId);
        finishRun.ExecuteNonQuery();

        UpdateSceneRunState(connection, transaction, sceneId, completedAt, status, message);
    }

    private ScheduleRun CreatePendingScheduleRun(SqliteConnection connection, SqliteTransaction transaction, ScheduleEntry schedule, string slot, string message)
    {
        var triggeredAt = DateTime.UtcNow;
        var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = @"
INSERT INTO ScheduleRuns (ScheduleId, ScheduledSlot, TriggeredAt, Status, Message)
VALUES (@scheduleId, @scheduledSlot, @triggeredAt, @status, @message);
SELECT last_insert_rowid();";
        command.Parameters.AddWithValue("@scheduleId", schedule.Id);
        command.Parameters.AddWithValue("@scheduledSlot", slot);
        command.Parameters.AddWithValue("@triggeredAt", triggeredAt.ToString("O"));
        command.Parameters.AddWithValue("@status", "pending");
        command.Parameters.AddWithValue("@message", message);
        var runId = Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));

        return new ScheduleRun
        {
            Id = runId,
            ScheduleId = schedule.Id,
            ScheduleName = schedule.Name,
            ScheduledSlot = slot,
            TriggeredAt = triggeredAt,
            Status = "pending",
            Message = message,
        };
    }

    private void UpdateScheduleRunState(SqliteConnection connection, SqliteTransaction transaction, int scheduleId, string slot, string status, string message)
    {
        var now = DateTime.UtcNow;
        var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = @"
UPDATE Schedules
SET LastRunAt = @lastRunAt,
    LastRunStatus = @lastRunStatus,
    LastRunMessage = @lastRunMessage,
    LastTriggeredSlot = @lastTriggeredSlot,
    UpdatedAt = @updatedAt
WHERE Id = @id;";
        command.Parameters.AddWithValue("@lastRunAt", now.ToString("O"));
        command.Parameters.AddWithValue("@lastRunStatus", status);
        command.Parameters.AddWithValue("@lastRunMessage", message);
        command.Parameters.AddWithValue("@lastTriggeredSlot", slot);
        command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
        command.Parameters.AddWithValue("@id", scheduleId);
        command.ExecuteNonQuery();
    }

    private void FinishScheduleRun(SqliteConnection connection, SqliteTransaction transaction, int scheduleId, int runId, string slot, string status, string message)
    {
        var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = @"
UPDATE ScheduleRuns
SET Status = @status,
    Message = @message
WHERE Id = @id;";
        command.Parameters.AddWithValue("@status", status);
        command.Parameters.AddWithValue("@message", message);
        command.Parameters.AddWithValue("@id", runId);
        command.ExecuteNonQuery();

        UpdateScheduleRunState(connection, transaction, scheduleId, slot, status, message);
    }

    private static string EventTypeForFailedCommand(DeviceCommandResult result, string failedEventType)
    {
        return IsTimeoutCommandResult(result) ? "DEVICE_COMMAND_TIMEOUT" : failedEventType;
    }

    private static bool IsTimeoutCommandResult(DeviceCommandResult result)
    {
        return string.Equals(result.Status, "timeout", StringComparison.OrdinalIgnoreCase)
            || result.Message.Contains("timeout", StringComparison.OrdinalIgnoreCase)
            || result.Message.Contains("timed out", StringComparison.OrdinalIgnoreCase);
    }
}
