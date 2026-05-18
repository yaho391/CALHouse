using Microsoft.Extensions.Hosting;

namespace CalHouse.Api.Services;

public sealed class ScheduleBackgroundService : BackgroundService
{
    private readonly DeviceStore _store;
    private readonly ILogger<ScheduleBackgroundService> _logger;

    public ScheduleBackgroundService(DeviceStore store, ILogger<ScheduleBackgroundService> logger)
    {
        _store = store;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var result = _store.RunDueSchedules();
                if (result.Runs.Count > 0)
                {
                    _logger.LogInformation("Запущено расписаний: {Count} для слота {Slot}", result.Runs.Count, result.Slot);
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Ошибка фоновой проверки расписаний");
            }

            await Task.Delay(TimeSpan.FromSeconds(20), stoppingToken);
        }
    }
}
