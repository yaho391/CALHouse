namespace CalHouse.Api.Models;

public class SceneExecutionLog
{
    public int Id { get; set; }
    public int SceneId { get; set; }
    public string SceneName { get; set; } = string.Empty;
    public DateTimeOffset StartedAtUtc { get; set; }
    public DateTimeOffset? FinishedAtUtc { get; set; }
    public string Status { get; set; } = string.Empty;
    public List<SceneExecutionItem> Results { get; set; } = new();
}

public class SceneExecutionItem
{
    public int DeviceId { get; set; }
    public string DeviceName { get; set; } = string.Empty;
    public string RoomName { get; set; } = string.Empty;
    public bool TargetIsOn { get; set; }
    public bool? AppliedIsOn { get; set; }
    public string Status { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
}
