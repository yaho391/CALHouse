using System.Text.Json;
using CalHouse.Api.Models;

namespace CalHouse.Api.Services;

public class RoomStore
{
    private readonly string _filePath;
    private readonly JsonSerializerOptions _jsonOptions = new() { WriteIndented = true };
    private readonly object _sync = new();

    public RoomStore(IWebHostEnvironment environment)
    {
        var appDataDirectory = Path.Combine(environment.ContentRootPath, "App_Data");
        Directory.CreateDirectory(appDataDirectory);

        _filePath = Path.Combine(appDataDirectory, "rooms.json");

        if (!File.Exists(_filePath))
        {
            SaveRooms(new List<Room>
            {
                new() { Id = 1, Name = "Гостиная" },
                new() { Id = 2, Name = "Кухня" },
                new() { Id = 3, Name = "Спальня" }
            });
        }
    }

    public IReadOnlyList<Room> GetAll()
    {
        lock (_sync)
        {
            return ReadRooms();
        }
    }

    public Room? GetById(int id)
    {
        lock (_sync)
        {
            return ReadRooms().FirstOrDefault(r => r.Id == id);
        }
    }

    public Room Add(string name)
    {
        lock (_sync)
        {
            var rooms = ReadRooms();
            var room = new Room
            {
                Id = rooms.Count == 0 ? 1 : rooms.Max(r => r.Id) + 1,
                Name = name.Trim()
            };
            rooms.Add(room);
            SaveRooms(rooms);
            return room;
        }
    }

    public Room? Rename(int id, string name)
    {
        lock (_sync)
        {
            var rooms = ReadRooms();
            var room = rooms.FirstOrDefault(r => r.Id == id);
            if (room is null)
            {
                return null;
            }

            room.Name = name.Trim();
            SaveRooms(rooms);
            return room;
        }
    }

    public Room? Delete(int id)
    {
        lock (_sync)
        {
            var rooms = ReadRooms();
            var room = rooms.FirstOrDefault(r => r.Id == id);
            if (room is null)
            {
                return null;
            }

            rooms.Remove(room);
            SaveRooms(rooms);
            return room;
        }
    }

    public bool NameExists(string name, int? excludingId = null)
    {
        lock (_sync)
        {
            return ReadRooms().Any(r =>
                (!excludingId.HasValue || r.Id != excludingId.Value) &&
                string.Equals(r.Name, name.Trim(), StringComparison.OrdinalIgnoreCase));
        }
    }

    private List<Room> ReadRooms()
    {
        var json = File.ReadAllText(_filePath);
        var rooms = JsonSerializer.Deserialize<List<Room>>(json) ?? new List<Room>();

        var repaired = false;
        for (var i = 0; i < rooms.Count; i++)
        {
            if (rooms[i].Id <= 0)
            {
                rooms[i].Id = i + 1;
                repaired = true;
            }

            if (string.IsNullOrWhiteSpace(rooms[i].Name))
            {
                rooms[i].Name = $"Комната #{rooms[i].Id}";
                repaired = true;
            }
        }

        if (repaired)
        {
            SaveRooms(rooms);
        }

        return rooms;
    }

    private void SaveRooms(List<Room> rooms)
    {
        File.WriteAllText(_filePath, JsonSerializer.Serialize(rooms, _jsonOptions));
    }
}
