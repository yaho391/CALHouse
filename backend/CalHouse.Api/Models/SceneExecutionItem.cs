namespace CalHouse.Api.Models;

public class SceneExecutionItem
{
    public int DeviceId { get; set; }
    public bool RequestedState { get; set; }
    public string Status { get; set; } = "applied";
}
