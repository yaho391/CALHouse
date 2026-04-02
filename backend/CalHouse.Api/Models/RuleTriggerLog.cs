namespace CalHouse.Api.Models;

public class RuleTriggerLog
{
    public int Id { get; set; }
    public int RuleId { get; set; }
    public string RuleName { get; set; } = string.Empty;
    public DateTime TriggeredAt { get; set; }
    public string EventType { get; set; } = string.Empty;
    public string EventValue { get; set; } = string.Empty;
    public string Status { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
}
