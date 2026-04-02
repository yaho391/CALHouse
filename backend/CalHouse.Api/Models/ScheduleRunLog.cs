namespace CalHouse.Api.Models;

public class ScheduleRunLog
{
    public int Id { get; set; }
    public int ScheduleId { get; set; }
    public string ScheduleName { get; set; } = string.Empty;
    public DateTime StartedAt { get; set; }
    public string Status { get; set; } = string.Empty;
    public string Message { get; set; } = string.Empty;
}
