namespace CalHouse.Api.Models;

public class ScheduleEntry
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public bool IsEnabled { get; set; }
    public string TimeOfDay { get; set; } = "08:00";
    public List<int> DaysOfWeek { get; set; } = new();
    public string ActionKind { get; set; } = "device_state";
    public int? ActionDeviceId { get; set; }
    public string? ActionDeviceName { get; set; }
    public bool? ActionTargetIsOn { get; set; }
    public int? ActionSceneId { get; set; }
    public string? ActionSceneName { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
    public DateTime? LastRunAt { get; set; }
    public string? LastRunStatus { get; set; }
    public string? LastRunMessage { get; set; }
    public string LastTriggeredSlot { get; set; } = string.Empty;
}

public class ScheduleRun
{
    public int Id { get; set; }
    public int ScheduleId { get; set; }
    public string ScheduleName { get; set; } = string.Empty;
    public string ScheduledSlot { get; set; } = string.Empty;
    public DateTime TriggeredAt { get; set; }
    public string Status { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
}

public class ScheduleRunBatchResult
{
    public string Slot { get; set; } = string.Empty;
    public List<ScheduleRun> Runs { get; set; } = new();
    public string Message { get; set; } = string.Empty;
}
