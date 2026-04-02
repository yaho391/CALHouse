namespace CalHouse.Api.Models;

public class ScheduleEntry
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public bool IsEnabled { get; set; }
    public string DaysOfWeek { get; set; } = "";
    public string TimeOfDay { get; set; } = "00:00";
    public string ActionType { get; set; } = "scene";
    public int? ActionSceneId { get; set; }
    public int? ActionDeviceId { get; set; }
    public bool? ActionTargetIsOn { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
    public DateTime? LastRunAt { get; set; }
}
