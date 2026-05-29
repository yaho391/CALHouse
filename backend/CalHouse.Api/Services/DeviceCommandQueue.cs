using System.Threading.Channels;

namespace CalHouse.Api.Services;

public sealed class DeviceCommandQueue
{
    private readonly Channel<Func<CancellationToken, ValueTask>> _queue = Channel.CreateUnbounded<Func<CancellationToken, ValueTask>>(
        new UnboundedChannelOptions
        {
            SingleReader = true,
            SingleWriter = false,
        });

    public ValueTask QueueAsync(Func<CancellationToken, ValueTask> workItem)
    {
        ArgumentNullException.ThrowIfNull(workItem);
        return _queue.Writer.WriteAsync(workItem);
    }

    public void Queue(Func<CancellationToken, ValueTask> workItem)
    {
        ArgumentNullException.ThrowIfNull(workItem);
        if (!_queue.Writer.TryWrite(workItem))
        {
            throw new InvalidOperationException("Device command queue is not accepting work items.");
        }
    }

    public ValueTask<Func<CancellationToken, ValueTask>> DequeueAsync(CancellationToken cancellationToken)
    {
        return _queue.Reader.ReadAsync(cancellationToken);
    }
}

public sealed class DeviceCommandBackgroundService : BackgroundService
{
    private readonly DeviceCommandQueue _queue;
    private readonly ILogger<DeviceCommandBackgroundService> _logger;

    public DeviceCommandBackgroundService(DeviceCommandQueue queue, ILogger<DeviceCommandBackgroundService> logger)
    {
        _queue = queue;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var workItem = await _queue.DequeueAsync(stoppingToken);
                await workItem(stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Device command background job failed");
            }
        }
    }
}
