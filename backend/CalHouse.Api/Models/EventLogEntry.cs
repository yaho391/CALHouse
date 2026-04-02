namespace CalHouse.Api.Models;

public class EventLogEntry
{
    public int Id { get; set; }
    public DateTime Ts { get; set; }
    public string Severity { get; set; } = string.Empty;
    public string Source { get; set; } = string.Empty;
    public string EventType { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
    public string? UserId { get; set; }
    public int? DeviceId { get; set; }
    public int? RoomId { get; set; }
    public int? SceneId { get; set; }
    public int? RunId { get; set; }
}
