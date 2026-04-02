namespace CalHouse.Api.Models;

public class SceneAction
{
    public int Id { get; set; }
    public int SceneId { get; set; }
    public int DeviceId { get; set; }
    public string DeviceName { get; set; } = string.Empty;
    public string RoomName { get; set; } = string.Empty;
    public bool TargetIsOn { get; set; }
    public int SortOrder { get; set; }
}
