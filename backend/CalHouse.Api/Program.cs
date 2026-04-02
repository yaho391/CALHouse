using CalHouse.Api.Infrastructure;
using CalHouse.Api.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSingleton<DeviceStore>();
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

var api = app.MapGroup("/api");

api.MapGet("/devices", (int? roomId, DeviceStore store) => Results.Ok(store.GetAllDevices(roomId)));

api.MapGet("/devices/{id:int}", (int id, DeviceStore store) =>
    Handle(() => Results.Ok(store.GetDevice(id))));

api.MapPost("/devices", (CreateDeviceRequest request, DeviceStore store) =>
    Handle(() =>
    {
        var created = store.AddDevice(
            request.Name,
            request.Room,
            request.RoomId,
            request.IsOn,
            request.Type,
            request.Provider,
            request.Identifier,
            request.Connection);
        return Results.Created($"/api/devices/{created.Id}", created);
    }));

api.MapPut("/devices/{id:int}", (int id, UpdateDeviceRequest request, DeviceStore store) =>
    Handle(() => Results.Ok(store.UpdateDevice(id, request.Name, request.Room, request.RoomId, request.IsOn, request.Type, request.Provider, request.Identifier, request.Connection))));

api.MapPut("/devices/{id:int}/toggle", (int id, DeviceStore store) =>
    Handle(() => Results.Ok(store.ToggleDevice(id))));

api.MapPut("/devices/{id:int}/room", (int id, AssignDeviceRoomRequest request, DeviceStore store) =>
    Handle(() => Results.Ok(store.AssignDeviceToRoom(id, request.RoomId))));

api.MapDelete("/devices/{id:int}", (int id, DeviceStore store) =>
    Handle(() => Results.Ok(store.DeleteDevice(id))));

api.MapPost("/devices/validate-connection", (ValidateConnectionRequest request, DeviceStore store) =>
    Handle(() =>
    {
        var result = store.ValidateDeviceConnection(request.Provider, request.Connection);
        return Results.Ok(new { ok = result.Ok, message = result.Message });
    }));

api.MapGet("/rooms", (DeviceStore store) => Results.Ok(store.GetAllRooms()));
api.MapGet("/rooms/{id:int}", (int id, DeviceStore store) => Handle(() => Results.Ok(store.GetRoom(id))));
api.MapGet("/rooms/{id:int}/devices", (int id, DeviceStore store) => Handle(() =>
{
    _ = store.GetRoom(id);
    return Results.Ok(store.GetAllDevices(id));
}));
api.MapPost("/rooms", (CreateRoomRequest request, DeviceStore store) => Handle(() =>
{
    var created = store.CreateRoom(request.Name, request.Zone);
    return Results.Created($"/api/rooms/{created.Id}", created);
}));
api.MapPut("/rooms/{id:int}", (int id, UpdateRoomRequest request, DeviceStore store) =>
    Handle(() => Results.Ok(store.UpdateRoom(id, request.Name, request.Zone))));
api.MapDelete("/rooms/{id:int}", (int id, DeviceStore store) =>
    Handle(() =>
    {
        store.DeleteRoom(id);
        return Results.NoContent();
    }));

api.MapGet("/scenes", (DeviceStore store) => Results.Ok(store.GetAllScenes()));
api.MapGet("/scenes/{id:int}", (int id, DeviceStore store) => Handle(() => Results.Ok(store.GetScene(id))));
api.MapGet("/scenes/{id:int}/runs", (int id, int? limit, DeviceStore store) =>
    Handle(() => Results.Ok(store.GetSceneRuns(id, limit ?? 20))));
api.MapPost("/scenes", (CreateSceneRequest request, DeviceStore store) => Handle(() =>
{
    var actions = (request.Actions ?? new List<SceneActionRequest>())
        .Select((action, index) => new SceneActionInput(action.DeviceId, action.TargetIsOn, action.SortOrder ?? index + 1))
        .ToList();
    var created = store.CreateScene(request.Name, request.Description, actions);
    return Results.Created($"/api/scenes/{created.Id}", created);
}));
api.MapPut("/scenes/{id:int}", (int id, UpdateSceneRequest request, DeviceStore store) => Handle(() =>
{
    var actions = (request.Actions ?? new List<SceneActionRequest>())
        .Select((action, index) => new SceneActionInput(action.DeviceId, action.TargetIsOn, action.SortOrder ?? index + 1))
        .ToList();
    return Results.Ok(store.UpdateScene(id, request.Name, request.Description, actions));
}));
api.MapDelete("/scenes/{id:int}", (int id, DeviceStore store) => Handle(() =>
{
    store.DeleteScene(id);
    return Results.NoContent();
}));
api.MapPost("/scenes/{id:int}/run", (int id, DeviceStore store) =>
    Handle(() => Results.Ok(store.RunScene(id))));


api.MapGet("/rules", (DeviceStore store) => Results.Ok(store.GetRules()));
api.MapPost("/rules", (CreateRuleRequest request, DeviceStore store) => Handle(() =>
{
    var created = store.CreateRule(request.Name, request.IsEnabled, request.SourceDeviceId, request.EventType, request.Operator, request.CompareValue, request.ActionType, request.ActionSceneId, request.ActionDeviceId, request.ActionTargetIsOn);
    return Results.Created($"/api/rules/{created.Id}", created);
}));
api.MapDelete("/rules/{id:int}", (int id, DeviceStore store) => Handle(() =>
{
    store.DeleteRule(id);
    return Results.NoContent();
}));
api.MapGet("/rules/triggers", (int? limit, DeviceStore store) => Results.Ok(store.GetRuleTriggerLogs(limit ?? 50)));
api.MapPost("/rules/process-event", (RuleEventRequest request, DeviceStore store) => Handle(() => Results.Ok(store.ProcessEvent(request.DeviceId, request.EventType, request.Value))));

api.MapGet("/schedules", (DeviceStore store) => Results.Ok(store.GetSchedules()));
api.MapPost("/schedules", (CreateScheduleRequest request, DeviceStore store) => Handle(() =>
{
    var created = store.CreateSchedule(request.Name, request.IsEnabled, request.DaysOfWeek, request.TimeOfDay, request.ActionType, request.ActionSceneId, request.ActionDeviceId, request.ActionTargetIsOn);
    return Results.Created($"/api/schedules/{created.Id}", created);
}));
api.MapDelete("/schedules/{id:int}", (int id, DeviceStore store) => Handle(() =>
{
    store.DeleteSchedule(id);
    return Results.NoContent();
}));
api.MapGet("/schedules/runs", (int? limit, DeviceStore store) => Results.Ok(store.GetScheduleRuns(limit ?? 50)));
api.MapPost("/schedules/run-due", (RunDueSchedulesRequest? request, DeviceStore store) => Handle(() =>
{
    var now = request?.UtcNow ?? DateTime.UtcNow;
    return Results.Ok(store.RunDueSchedules(now));
}));

api.MapGet("/logs", (int? limit, DeviceStore store) => Results.Ok(store.GetLogs(limit ?? 50)));

app.Run();

static IResult Handle(Func<IResult> action)
{
    try
    {
        return action();
    }
    catch (ApiProblemException problem)
    {
        return Results.Json(new { error = problem.Message, code = problem.Code, message = problem.Message }, statusCode: problem.StatusCode);
    }
    catch (Exception ex)
    {
        return Results.Json(new { error = ex.Message, code = "INTERNAL_ERROR", message = ex.Message }, statusCode: StatusCodes.Status500InternalServerError);
    }
}

internal sealed record CreateDeviceRequest(
    string Name,
    string? Room,
    int? RoomId,
    bool IsOn = false,
    string? Type = "Другое",
    string? Provider = "mock",
    string? Identifier = null,
    Dictionary<string, string>? Connection = null);

internal sealed record UpdateDeviceRequest(
    string? Name,
    string? Room,
    int? RoomId,
    bool? IsOn,
    string? Type,
    string? Provider,
    string? Identifier,
    Dictionary<string, string>? Connection);

internal sealed record AssignDeviceRoomRequest(int RoomId);
internal sealed record ValidateConnectionRequest(string? Provider, Dictionary<string, string>? Connection);
internal sealed record CreateRoomRequest(string Name, string? Zone);
internal sealed record UpdateRoomRequest(string Name, string? Zone);
internal sealed record SceneActionRequest(int DeviceId, bool TargetIsOn, int? SortOrder);
internal sealed record CreateSceneRequest(string Name, string? Description, List<SceneActionRequest>? Actions);
internal sealed record UpdateSceneRequest(string Name, string? Description, List<SceneActionRequest>? Actions);
internal sealed record CreateRuleRequest(string Name, bool IsEnabled, int SourceDeviceId, string EventType, string Operator, string CompareValue, string ActionType, int? ActionSceneId, int? ActionDeviceId, bool? ActionTargetIsOn);
internal sealed record RuleEventRequest(int DeviceId, string EventType, string Value);
internal sealed record CreateScheduleRequest(string Name, bool IsEnabled, string DaysOfWeek, string TimeOfDay, string ActionType, int? ActionSceneId, int? ActionDeviceId, bool? ActionTargetIsOn);
internal sealed record RunDueSchedulesRequest(DateTime? UtcNow);
