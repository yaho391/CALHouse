namespace CalHouse.Api.Models;

public class SceneRun
{
    public int Id { get; set; }
    public int SceneId { get; set; }
    public string SceneName { get; set; } = string.Empty;
    public DateTime StartedAt { get; set; }
    public DateTime? CompletedAt { get; set; }
    public string Status { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
}
