using Microsoft.Extensions.Hosting;

namespace CalHouse.Api.Services;

public sealed class ScheduleBackgroundService : BackgroundService
{
    private readonly DeviceStore _store;
    private readonly DeviceCommandQueue _queue;
    private readonly ILogger<ScheduleBackgroundService> _logger;

    public ScheduleBackgroundService(DeviceStore store, DeviceCommandQueue queue, ILogger<ScheduleBackgroundService> logger)
    {
        _store = store;
        _queue = queue;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var result = _store.QueueDueSchedules(_queue);
                if (result.Runs.Count > 0)
                {
                    _logger.LogInformation("Queued schedules: {Count} for slot {Slot}", result.Runs.Count, result.Slot);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Scheduled background check failed");
            }

            await Task.Delay(TimeSpan.FromSeconds(20), stoppingToken);
        }
    }
}
