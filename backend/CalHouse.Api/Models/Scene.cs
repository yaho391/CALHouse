namespace CalHouse.Api.Models;

public class Scene
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string? Description { get; set; }
    public List<SceneAction> Actions { get; set; } = new();
}

public class SceneAction
{
    public int DeviceId { get; set; }
    public bool IsOn { get; set; }
}

public class SceneExecutionLog
{
    public int Id { get; set; }
    public int SceneId { get; set; }
    public string SceneName { get; set; } = string.Empty;
    public DateTimeOffset StartedAtUtc { get; set; }
    public DateTimeOffset FinishedAtUtc { get; set; }
    public string Status { get; set; } = "completed";
    public List<SceneExecutionItem> Results { get; set; } = new();
}

public class SceneExecutionItem
{
    public int DeviceId { get; set; }
    public bool RequestedState { get; set; }
    public string Status { get; set; } = "applied";
}
