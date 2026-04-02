namespace CalHouse.Api.Models;

public class Room
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Zone { get; set; } = string.Empty;
    public int DeviceCount { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
}

public class RoomDetails : Room
{
    public List<Device> Devices { get; set; } = new();
}
