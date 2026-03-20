using CalHouse.Api.Models;
using CalHouse.Api.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSingleton<DeviceStore>();
builder.Services.AddSingleton<RoomStore>();
builder.Services.AddSingleton<SceneStore>();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddCors(options =>
{
    options.AddPolicy("DevCors", policy =>
    {
        policy.AllowAnyOrigin()
            .AllowAnyMethod()
            .AllowAnyHeader();
    });
});

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseCors("DevCors");

app.MapGet("/", () => Results.Text("CalHouse API is running"));

app.MapGet("/api/devices", (DeviceStore store) => Results.Ok(store.GetAllDevices()));

app.MapGet("/api/devices/{id:int}", (int id, DeviceStore store) =>
{
    var device = store.GetDevice(id);
    return device is null ? Results.NotFound(new { message = "Device not found" }) : Results.Ok(device);
});

app.MapPost("/api/devices", (CreateDeviceRequest request, DeviceStore deviceStore, RoomStore roomStore) =>
{
    var name = (request.Name ?? string.Empty).Trim();
    var room = (request.Room ?? string.Empty).Trim();

    if (string.IsNullOrWhiteSpace(name) || string.IsNullOrWhiteSpace(room))
    {
        return Results.BadRequest(new { message = "Name and room are required" });
    }

    if (!roomStore.NameExists(room))
    {
        roomStore.Add(room);
    }

    var created = deviceStore.AddDevice(name, room, request.IsOn);
    return Results.Created($"/api/devices/{created.Id}", created);
});

app.MapPut("/api/devices/{id:int}/toggle", (int id, DeviceStore store) =>
{
    var updated = store.ToggleDevice(id);
    return updated is null ? Results.NotFound(new { message = "Device not found" }) : Results.Ok(updated);
});

app.MapPut("/api/devices/{id:int}/room", (int id, ReassignDeviceRoomRequest request, DeviceStore deviceStore, RoomStore roomStore) =>
{
    var room = roomStore.GetById(request.RoomId);
    if (room is null)
    {
        return Results.NotFound(new { message = "Room not found" });
    }

    var updated = deviceStore.ReassignDeviceRoom(id, room.Name);
    return updated is null ? Results.NotFound(new { message = "Device not found" }) : Results.Ok(updated);
});

app.MapDelete("/api/devices/{id:int}", (int id, DeviceStore store) =>
{
    var removed = store.DeleteDevice(id);
    return removed is null ? Results.NotFound(new { message = "Device not found" }) : Results.Ok(removed);
});

app.MapGet("/api/rooms", (RoomStore roomStore) => Results.Ok(roomStore.GetAll()));

app.MapGet("/api/rooms/{id:int}", (int id, RoomStore roomStore) =>
{
    var room = roomStore.GetById(id);
    return room is null ? Results.NotFound(new { message = "Room not found" }) : Results.Ok(room);
});

app.MapGet("/api/rooms/{id:int}/devices", (int id, RoomStore roomStore, DeviceStore deviceStore) =>
{
    var room = roomStore.GetById(id);
    if (room is null)
    {
        return Results.NotFound(new { message = "Room not found" });
    }

    return Results.Ok(deviceStore.GetDevicesByRoom(room.Name));
});

app.MapPost("/api/rooms", (RoomWriteRequest request, RoomStore roomStore) =>
{
    var name = (request.Name ?? string.Empty).Trim();
    if (string.IsNullOrWhiteSpace(name))
    {
        return Results.BadRequest(new { message = "Room name is required" });
    }

    if (roomStore.NameExists(name))
    {
        return Results.Conflict(new { message = "Room name already exists", code = "ROOM_ALREADY_EXISTS" });
    }

    var created = roomStore.Add(name);
    return Results.Created($"/api/rooms/{created.Id}", created);
});

app.MapPut("/api/rooms/{id:int}", (int id, RoomWriteRequest request, RoomStore roomStore, DeviceStore deviceStore) =>
{
    var name = (request.Name ?? string.Empty).Trim();
    if (string.IsNullOrWhiteSpace(name))
    {
        return Results.BadRequest(new { message = "Room name is required" });
    }

    var existing = roomStore.GetById(id);
    if (existing is null)
    {
        return Results.NotFound(new { message = "Room not found" });
    }

    if (roomStore.NameExists(name, id))
    {
        return Results.Conflict(new { message = "Room name already exists", code = "ROOM_ALREADY_EXISTS" });
    }

    var oldName = existing.Name;
    var updated = roomStore.Rename(id, name)!;
    deviceStore.RenameRoomForDevices(oldName, updated.Name);
    return Results.Ok(updated);
});

app.MapDelete("/api/rooms/{id:int}", (int id, RoomStore roomStore, DeviceStore deviceStore) =>
{
    var room = roomStore.GetById(id);
    if (room is null)
    {
        return Results.NotFound(new { message = "Room not found" });
    }

    if (deviceStore.CountDevicesInRoom(room.Name) > 0)
    {
        return Results.Conflict(new { message = "Room has devices", code = "ROOM_NOT_EMPTY" });
    }

    roomStore.Delete(id);
    return Results.NoContent();
});

app.MapGet("/api/scenes", (SceneStore store) => Results.Ok(store.GetAllScenes()));

app.MapGet("/api/scenes/{id:int}", (int id, SceneStore store) =>
{
    var scene = store.GetScene(id);
    return scene is null ? Results.NotFound(new { message = "Scene not found" }) : Results.Ok(scene);
});

app.MapPost("/api/scenes", (SceneWriteRequest request, SceneStore sceneStore, DeviceStore deviceStore) =>
{
    var validationError = ValidateSceneRequest(request, deviceStore);
    if (validationError is not null)
    {
        return validationError;
    }

    var created = sceneStore.AddScene(request.Name!.Trim(), request.Description, request.Actions!);
    return Results.Created($"/api/scenes/{created.Id}", created);
});

app.MapPut("/api/scenes/{id:int}", (int id, SceneWriteRequest request, SceneStore sceneStore, DeviceStore deviceStore) =>
{
    var validationError = ValidateSceneRequest(request, deviceStore);
    if (validationError is not null)
    {
        return validationError;
    }

    var updated = sceneStore.UpdateScene(id, request.Name!.Trim(), request.Description, request.Actions!);
    return updated is null ? Results.NotFound(new { message = "Scene not found" }) : Results.Ok(updated);
});

app.MapDelete("/api/scenes/{id:int}", (int id, SceneStore sceneStore) =>
{
    var deleted = sceneStore.DeleteScene(id);
    return deleted is null ? Results.NotFound(new { message = "Scene not found" }) : Results.NoContent();
});

app.MapPost("/api/scenes/{id:int}/run", (int id, SceneStore sceneStore, DeviceStore deviceStore) =>
{
    var scene = sceneStore.GetScene(id);
    if (scene is null)
    {
        return Results.NotFound(new { message = "Scene not found" });
    }

    var executionItems = new List<SceneExecutionItem>();

    foreach (var action in scene.Actions)
    {
        var device = deviceStore.SetDeviceState(action.DeviceId, action.IsOn);
        executionItems.Add(new SceneExecutionItem
        {
            DeviceId = action.DeviceId,
            RequestedState = action.IsOn,
            Status = device is null ? "device_not_found" : "applied"
        });
    }

    var log = sceneStore.AddExecutionLog(scene.Id, scene.Name, executionItems);
    return Results.Ok(log);
});

app.MapGet("/api/scenes/executions", (int? sceneId, SceneStore sceneStore) => Results.Ok(sceneStore.GetExecutionLogs(sceneId)));

app.Run();

static IResult? ValidateSceneRequest(SceneWriteRequest request, DeviceStore deviceStore)
{
    if (string.IsNullOrWhiteSpace(request.Name))
    {
        return Results.BadRequest(new { message = "Scene name is required" });
    }

    if (request.Actions is null || request.Actions.Count == 0)
    {
        return Results.BadRequest(new { message = "Scene should contain at least one action" });
    }

    var allDevices = deviceStore.GetAllDevices();
    var missingDeviceId = request.Actions.Select(a => a.DeviceId).FirstOrDefault(id => allDevices.All(d => d.Id != id));
    if (missingDeviceId != 0)
    {
        return Results.BadRequest(new { message = $"Device with id {missingDeviceId} not found" });
    }

    return null;
}

internal sealed record CreateDeviceRequest(string? Name, string? Room, bool IsOn = false);
internal sealed record ReassignDeviceRoomRequest(int RoomId);
internal sealed record RoomWriteRequest(string? Name);
internal sealed record SceneWriteRequest(string? Name, string? Description, List<SceneAction>? Actions);
