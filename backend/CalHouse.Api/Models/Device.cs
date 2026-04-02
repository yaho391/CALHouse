namespace CalHouse.Api.Models;

public class Device
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public int? RoomId { get; set; }
    public string Room { get; set; } = string.Empty;
    public bool IsOn { get; set; }
    public string Type { get; set; } = "Другое";
    public string Provider { get; set; } = "mock";
    public string? Identifier { get; set; }
    public string ConnectionStatus { get; set; } = "unknown";
    public DateTime? LastSeenAt { get; set; }
    public Dictionary<string, string> Connection { get; set; } = new(StringComparer.OrdinalIgnoreCase);
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
}
