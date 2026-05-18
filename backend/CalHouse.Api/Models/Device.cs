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
    public string Protocol { get; set; } = "manual";
    public string Channel { get; set; } = "local";
    public string ExternalId { get; set; } = string.Empty;
    public string Manufacturer { get; set; } = string.Empty;
    public string Model { get; set; } = string.Empty;
    public Dictionary<string, string> Connection { get; set; } = new(StringComparer.OrdinalIgnoreCase);
    public string ConnectionStatus { get; set; } = "unknown";
    public string ConnectionMessage { get; set; } = string.Empty;
    public DateTime? LastConnectionCheckAt { get; set; }
    public DateTime? LastSeenAt { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
}
