using System.Text.Json;
using CalHouse.Api.Models;

namespace CalHouse.Api.Services;

public class DeviceStore
{
    private readonly string _filePath;
    private readonly ILogger<DeviceStore> _logger;
    private readonly JsonSerializerOptions _jsonOptions = new() { WriteIndented = true };
    private readonly object _sync = new();

    public DeviceStore(IWebHostEnvironment environment, ILogger<DeviceStore> logger)
    {
        _logger = logger;

        var appDataDirectory = Path.Combine(environment.ContentRootPath, "App_Data");
        Directory.CreateDirectory(appDataDirectory);

        _filePath = Path.Combine(appDataDirectory, "devices.json");

        if (!File.Exists(_filePath))
        {
            var seedDevices = new List<Device>
            {
                new() { Id = 1, Name = "Термостат", Room = "Гостиная", IsOn = false },
                new() { Id = 2, Name = "Освещение", Room = "Кухня", IsOn = true },
                new() { Id = 3, Name = "Камера", Room = "Вход", IsOn = true }
            };

            SaveDevices(seedDevices);
        }
    }

    public IReadOnlyList<Device> GetAllDevices()
    {
        lock (_sync)
        {
            return ReadDevices();
        }
    }

    public Device? ToggleDevice(int id)
    {
        lock (_sync)
        {
            var devices = ReadDevices();
            var device = devices.FirstOrDefault(d => d.Id == id);

            if (device is null)
            {
                return null;
            }

            device.IsOn = !device.IsOn;
            SaveDevices(devices);

            _logger.LogInformation("Device {DeviceId} toggled to {State}", device.Id, device.IsOn ? "ON" : "OFF");

            return device;
        }
    }

    private List<Device> ReadDevices()
    {
        var json = File.ReadAllText(_filePath);
        return JsonSerializer.Deserialize<List<Device>>(json) ?? new List<Device>();
    }

    private void SaveDevices(List<Device> devices)
    {
        var json = JsonSerializer.Serialize(devices, _jsonOptions);
        File.WriteAllText(_filePath, json);
    }
}
