namespace CalHouse.Api.Models;

public class AutomationRule
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public bool IsEnabled { get; set; }
    public int SourceDeviceId { get; set; }
    public string SourceDeviceName { get; set; } = string.Empty;
    public string EventType { get; set; } = "state";
    public string Operator { get; set; } = "eq";
    public string CompareValue { get; set; } = string.Empty;
    public string ActionType { get; set; } = "scene";
    public int? ActionSceneId { get; set; }
    public int? ActionDeviceId { get; set; }
    public bool? ActionTargetIsOn { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
    public DateTime? LastTriggeredAt { get; set; }
    public int TriggerCount { get; set; }
}
