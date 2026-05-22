namespace CalHouse.Api.Models;

public class SceneExecutionItem
{
    public int DeviceId { get; set; }
    public string DeviceName { get; set; } = string.Empty;
    public string RoomName { get; set; } = string.Empty;
    public bool TargetIsOn { get; set; }
    public bool RequestedState { get; set; }
    public bool? AppliedIsOn { get; set; }
    public string Status { get; set; } = "applied";
    public string Message { get; set; } = string.Empty;
}
