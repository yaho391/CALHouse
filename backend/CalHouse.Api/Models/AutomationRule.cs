namespace CalHouse.Api.Models;

public class AutomationRule
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public bool IsEnabled { get; set; }
    public int TriggerDeviceId { get; set; }
    public string TriggerDeviceName { get; set; } = string.Empty;
    public string TriggerEventType { get; set; } = string.Empty;
    public string ComparisonOperator { get; set; } = "=";
    public string CompareValue { get; set; } = string.Empty;
    public string ActionKind { get; set; } = "device_state";
    public int? ActionDeviceId { get; set; }
    public string? ActionDeviceName { get; set; }
    public bool? ActionTargetIsOn { get; set; }
    public int? ActionSceneId { get; set; }
    public string? ActionSceneName { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
    public DateTime? LastTriggeredAt { get; set; }
    public string? LastTriggerStatus { get; set; }
    public string? LastTriggerMessage { get; set; }
}

public class RuleRun
{
    public int Id { get; set; }
    public int RuleId { get; set; }
    public string RuleName { get; set; } = string.Empty;
    public int SourceDeviceId { get; set; }
    public string SourceDeviceName { get; set; } = string.Empty;
    public string EventType { get; set; } = string.Empty;
    public string EventValue { get; set; } = string.Empty;
    public DateTime TriggeredAt { get; set; }
    public string Status { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
}

public class DeviceEventResult
{
    public int? SourceDeviceId { get; set; }
    public string? SourceDeviceName { get; set; }
    public string EventType { get; set; } = string.Empty;
    public string EventValue { get; set; } = string.Empty;
    public List<RuleRun> TriggeredRules { get; set; } = new();
    public string Message { get; set; } = string.Empty;
}
