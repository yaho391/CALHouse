using System.Text.Json;
using CalHouse.Api.Models;

namespace CalHouse.Api.Services;

public class DeviceStore
{
    private readonly string _filePath;
    private readonly ILogger<DeviceStore> _logger;
    private readonly JsonSerializerOptions _jsonOptions = new() { WriteIndented = true };
    private readonly object _sync = new();
    private static readonly HashSet<string> InvalidNameValues = new(StringComparer.OrdinalIgnoreCase)
    {
        "on",
        "off",
        "вкл",
        "выкл"
    };

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

    public Device? GetDevice(int id)
    {
        lock (_sync)
        {
            var devices = ReadDevices();
            return devices.FirstOrDefault(d => d.Id == id);
        }
    }

    public Device AddDevice(string name, string room, bool isOn)
    {
        lock (_sync)
        {
            var devices = ReadDevices();
            var nextId = devices.Count == 0 ? 1 : devices.Max(d => d.Id) + 1;

            var device = new Device
            {
                Id = nextId,
                Name = name.Trim(),
                Room = room.Trim(),
                IsOn = isOn
            };

            devices.Add(device);
            SaveDevices(devices);

            _logger.LogInformation("Device {DeviceId} added: {Name} ({Room})", device.Id, device.Name, device.Room);

            return device;
        }
    }

    public Device? DeleteDevice(int id)
    {
        lock (_sync)
        {
            var devices = ReadDevices();
            var device = devices.FirstOrDefault(d => d.Id == id);

            if (device is null)
            {
                return null;
            }

            devices.Remove(device);
            SaveDevices(devices);

            _logger.LogInformation("Device {DeviceId} deleted: {Name}", device.Id, device.Name);

            return device;
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
        var devices = JsonSerializer.Deserialize<List<Device>>(json) ?? new List<Device>();

        var requiresIdRepair = devices.Any(d => d.Id <= 0) || devices
            .GroupBy(d => d.Id)
            .Any(group => group.Key > 0 && group.Count() > 1);

        var requiresTextRepair = devices.Any(d =>
            string.IsNullOrWhiteSpace(d.Name) ||
            InvalidNameValues.Contains(d.Name.Trim()) ||
            string.IsNullOrWhiteSpace(d.Room));

        if (!requiresIdRepair && !requiresTextRepair)
        {
            return devices;
        }

        if (requiresIdRepair)
        {
            _logger.LogInformation("Device data had missing or duplicate ids. Reassigning ids sequentially.");

            for (var i = 0; i < devices.Count; i++)
            {
                devices[i].Id = i + 1;
            }
        }

        if (requiresTextRepair)
        {
            _logger.LogInformation("Device data had empty or invalid name/room values. Applying safe defaults.");

            foreach (var device in devices)
            {
                if (string.IsNullOrWhiteSpace(device.Name) || InvalidNameValues.Contains(device.Name.Trim()))
                {
                    device.Name = $"Устройство #{device.Id}";
                }

                if (string.IsNullOrWhiteSpace(device.Room))
                {
                    device.Room = "Комната не указана";
                }
            }
        }

        SaveDevices(devices);

        return devices;
    }

    private void SaveDevices(List<Device> devices)
    {
        var json = JsonSerializer.Serialize(devices, _jsonOptions);
        File.WriteAllText(_filePath, json);
    }
}
