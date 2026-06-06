using CalHouse.Api.Infrastructure;
using CalHouse.Api.Models;
using Microsoft.Data.Sqlite;
using System.Globalization;

namespace CalHouse.Api.Services;

public partial class DeviceStore
{
    public VisualDemoAutomationResult ProcessVisualDemoEvent(int roomId, int sourceDeviceId, string eventType, string value, string? demoTime)
    {
        var cleanEventType = NormalizeVisualEventType(eventType);
        var cleanValue = NormalizeOptional(value, "").Trim();
        var result = new VisualDemoAutomationResult { Message = "Visual demo event processed" };

        lock (_sync)
        {
            using var db = OpenConnection();
            _ = ReadRoomSummaryOrThrow(db, roomId);
            var sourceDevice = ReadDeviceOrThrow(db, sourceDeviceId);
            EnsureVisualDemoDeviceInRoom(sourceDevice, roomId);
            var demoDevices = ReadDevices(db, roomId).Where(IsVisualDemoDevice).ToList();

            using var transaction = db.BeginTransaction();
            if (cleanEventType == "motion" && IsTrueValue(cleanValue))
            {
                TriggerVisualRule(db, transaction, result, demoDevices, "Движение включает свет", "motion=true", "light", true, demoTime);
            }
            else if (cleanEventType == "water_leak" && IsTrueValue(cleanValue))
            {
                TriggerVisualRule(db, transaction, result, demoDevices, "Протечка выключает розетку", "leak=true", "socket", false, demoTime);
            }
            else if (cleanEventType == "temperature" && TryParseVisualNumber(cleanValue, out var temperature) && temperature > 28)
            {
                TriggerVisualRule(db, transaction, result, demoDevices, "Высокая температура включает розетку", $"temperature={temperature:0.#}", "socket", true, demoTime);
            }

            if (result.Automations.Count == 0)
            {
                result.Status = "skipped";
                result.Message = "Подходящих visual rules не найдено";
            }

            transaction.Commit();
            result.Devices = result.Devices.Select(device => ReadDeviceOrThrow(db, device.Id)).ToList();
            SyncLegacyDevicesJson(db);
        }

        return result;
    }

    public VisualDemoAutomationResult ProcessVisualDemoTimeChanged(int roomId, string demoTime, string? phase)
    {
        var cleanPhase = NormalizeOptional(phase, "").Trim().ToLowerInvariant();
        var result = new VisualDemoAutomationResult { Message = "Visual demo time processed" };

        lock (_sync)
        {
            using var db = OpenConnection();
            _ = ReadRoomSummaryOrThrow(db, roomId);
            var demoDevices = ReadDevices(db, roomId).Where(IsVisualDemoDevice).ToList();
            using var transaction = db.BeginTransaction();

            if (cleanPhase == "evening")
            {
                TriggerVisualRule(db, transaction, result, demoDevices, "Вечером включить свет", $"demo-time={demoTime}", "light", true, demoTime);
            }
            else if (cleanPhase == "night")
            {
                TriggerVisualRule(db, transaction, result, demoDevices, "Ночью выключить розетку", $"demo-time={demoTime}", "socket", false, demoTime);
            }

            if (result.Automations.Count == 0)
            {
                result.Status = "skipped";
                result.Message = "Для этой фазы visual rules не сработали";
            }

            transaction.Commit();
            result.Devices = result.Devices.Select(device => ReadDeviceOrThrow(db, device.Id)).ToList();
            SyncLegacyDevicesJson(db);
        }

        return result;
    }

    public VisualDemoAutomationResult RunVisualDemoScenario(int roomId, string scenarioId)
    {
        var cleanScenario = NormalizeOptional(scenarioId, "").Trim().ToLowerInvariant();
        var result = new VisualDemoAutomationResult { Message = "Visual demo scenario processed" };

        lock (_sync)
        {
            using var db = OpenConnection();
            _ = ReadRoomSummaryOrThrow(db, roomId);
            var demoDevices = ReadDevices(db, roomId).Where(IsVisualDemoDevice).ToList();
            using var transaction = db.BeginTransaction();

            switch (cleanScenario)
            {
                case "evening_mode":
                    RunVisualScenarioAction(db, transaction, result, demoDevices, "Вечерний режим", "light", true);
                    break;
                case "night_mode":
                    RunVisualScenarioAction(db, transaction, result, demoDevices, "Ночной режим", "socket", false);
                    RunVisualScenarioAction(db, transaction, result, demoDevices, "Ночной режим", "light", true);
                    break;
                case "safety":
                    RunVisualScenarioAction(db, transaction, result, demoDevices, "Безопасность", "socket", false);
                    break;
                case "all_off":
                    RunVisualScenarioAction(db, transaction, result, demoDevices, "Все выключить", "light", false);
                    RunVisualScenarioAction(db, transaction, result, demoDevices, "Все выключить", "socket", false);
                    break;
                default:
                    throw new ValidationProblemException("Неизвестный visual demo сценарий", "VISUAL_DEMO_SCENARIO_UNKNOWN");
            }

            if (result.Automations.Count == 0)
            {
                result.Status = "skipped";
                result.Message = "В комнате нет подходящих demo-устройств";
            }

            transaction.Commit();
            result.Devices = result.Devices.Select(device => ReadDeviceOrThrow(db, device.Id)).ToList();
            SyncLegacyDevicesJson(db);
        }

        return result;
    }

    private void TriggerVisualRule(
        SqliteConnection db,
        SqliteTransaction transaction,
        VisualDemoAutomationResult result,
        IReadOnlyList<Device> demoDevices,
        string ruleName,
        string condition,
        string targetType,
        bool targetState,
        string? demoTime)
    {
        var target = FindVisualDemoDevice(demoDevices, targetType);
        if (target is null)
        {
            AddVisualAutomationLog(result, "rule", ruleName, $"Цель {targetType} не найдена", "skipped", condition, demoTime);
            return;
        }

        ApplyVisualDemoDeviceState(db, transaction, target, targetState, $"Visual rule: {ruleName}", result);
        AddVisualAutomationLog(result, "rule", ruleName, targetState ? $"{target.Name} включено" : $"{target.Name} выключено", "completed", condition, demoTime);
        LogEvent(db, transaction, "info", "visual_demo", "VISUAL_RULE_TRIGGERED", $"visual_demo: сработало правило «{ruleName}». {condition}", deviceId: target.Id, roomId: target.RoomId);
    }

    private void RunVisualScenarioAction(
        SqliteConnection db,
        SqliteTransaction transaction,
        VisualDemoAutomationResult result,
        IReadOnlyList<Device> demoDevices,
        string scenarioName,
        string targetType,
        bool targetState)
    {
        var targets = demoDevices.Where(device => DeviceTypeMatches(device, targetType)).ToList();
        foreach (var target in targets)
        {
            ApplyVisualDemoDeviceState(db, transaction, target, targetState, $"Visual scenario: {scenarioName}", result);
        }

        if (targets.Count > 0)
        {
            AddVisualAutomationLog(result, "scenario", scenarioName, $"{targetType}: {(targetState ? "ON" : "OFF")}", "completed", "scenario action", null);
            LogEvent(db, transaction, "info", "visual_demo", "VISUAL_SCENARIO_RUN", $"visual_demo: запущен сценарий «{scenarioName}»", roomId: targets[0].RoomId);
        }
    }

    private void ApplyVisualDemoDeviceState(SqliteConnection db, SqliteTransaction transaction, Device device, bool isOn, string message, VisualDemoAutomationResult result)
    {
        EnsureVisualDemoDevice(device);
        var now = DateTime.UtcNow;
        var command = db.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = @"
UPDATE Devices
SET IsOn = @isOn,
    ConnectionStatus = 'connected',
    ConnectionMessage = @message,
    LastSeenAt = @lastSeenAt,
    LastConnectionCheckAt = @lastConnectionCheckAt,
    UpdatedAt = @updatedAt
WHERE Id = @id;";
        command.Parameters.AddWithValue("@id", device.Id);
        command.Parameters.AddWithValue("@isOn", isOn ? 1 : 0);
        command.Parameters.AddWithValue("@message", message);
        command.Parameters.AddWithValue("@lastSeenAt", now.ToString("O"));
        command.Parameters.AddWithValue("@lastConnectionCheckAt", now.ToString("O"));
        command.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
        command.ExecuteNonQuery();

        if (result.Devices.All(existing => existing.Id != device.Id))
        {
            result.Devices.Add(device);
        }
    }

    private static void AddVisualAutomationLog(VisualDemoAutomationResult result, string kind, string name, string action, string status, string message, string? demoTime)
    {
        result.Automations.Add(new VisualDemoAutomationLog
        {
            Kind = kind,
            Name = name,
            Action = action,
            Status = status,
            Message = message,
            DemoTime = demoTime,
        });
        result.Status = result.Automations.Any(item => item.Status == "completed") ? "completed" : status;
        result.Message = action;
    }

    private void EnsureVisualDemoDeviceInRoom(Device device, int roomId)
    {
        EnsureVisualDemoDevice(device);
        if (device.RoomId != roomId)
        {
            throw new ValidationProblemException("Demo-устройство не относится к выбранной комнате", "VISUAL_DEMO_ROOM_MISMATCH");
        }
    }

    private void EnsureVisualDemoDevice(Device device)
    {
        if (!IsVisualDemoDevice(device))
        {
            throw new ValidationProblemException("Visual demo automation работает только с demo-устройствами", "VISUAL_DEMO_DEVICE_REQUIRED");
        }
    }

    private bool IsVisualDemoDevice(Device device)
    {
        var provider = NormalizeOptional(device.Provider, "").Trim().ToLowerInvariant();
        var protocol = NormalizeOptional(device.Protocol, "").Trim().ToLowerInvariant();
        return provider == "demo" || protocol == "demo" || device.Connection.ContainsKey("demoType");
    }

    private Device? FindVisualDemoDevice(IEnumerable<Device> devices, string typeCode)
    {
        return devices.FirstOrDefault(device => DeviceTypeMatches(device, typeCode));
    }

    private bool DeviceTypeMatches(Device device, string typeCode)
    {
        return string.Equals(_catalog.NormalizeDeviceTypeCode(device.Type), typeCode, StringComparison.OrdinalIgnoreCase);
    }

    private static string NormalizeVisualEventType(string eventType)
    {
        return NormalizeOptional(eventType, "").Trim().ToLowerInvariant() switch
        {
            "leak" => "water_leak",
            "temperature_changed" => "temperature",
            var value => value,
        };
    }

    private static bool IsTrueValue(string value)
    {
        return value.Trim().Equals("true", StringComparison.OrdinalIgnoreCase)
            || value.Trim().Equals("1", StringComparison.OrdinalIgnoreCase)
            || value.Trim().Equals("on", StringComparison.OrdinalIgnoreCase);
    }

    private static bool TryParseVisualNumber(string value, out double number)
    {
        return double.TryParse(value.Replace(',', '.'), NumberStyles.Float, CultureInfo.InvariantCulture, out number);
    }
}
