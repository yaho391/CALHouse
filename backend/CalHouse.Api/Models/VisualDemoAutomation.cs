namespace CalHouse.Api.Models;

public class VisualDemoAutomationResult
{
    public string Status { get; set; } = "completed";
    public string Message { get; set; } = string.Empty;
    public List<Device> Devices { get; set; } = new();
    public List<VisualDemoAutomationLog> Automations { get; set; } = new();
}

public class VisualDemoAutomationLog
{
    public string Kind { get; set; } = "rule";
    public string Name { get; set; } = string.Empty;
    public string Source { get; set; } = "visual_demo";
    public string Action { get; set; } = string.Empty;
    public string Status { get; set; } = "completed";
    public string Message { get; set; } = string.Empty;
    public string? DemoTime { get; set; }
}
