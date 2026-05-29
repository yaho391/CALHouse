using CalHouse.Api.Infrastructure;
using CalHouse.Api.Models;
using CalHouse.Api.Services;
using System.Text.RegularExpressions;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSingleton<DeviceCatalogService>();
builder.Services.AddSingleton<AuthStore>();
builder.Services.AddSingleton<DeviceStore>();
builder.Services.AddSingleton<DeviceCommandQueue>();
builder.Services.AddHostedService<DeviceCommandBackgroundService>();
builder.Services.AddHostedService<ScheduleBackgroundService>();
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
app.Use(async (context, next) =>
{
    var path = context.Request.Path.Value ?? string.Empty;
    if (HttpMethods.IsOptions(context.Request.Method) || !path.StartsWith("/api/", StringComparison.OrdinalIgnoreCase) || IsPublicAuthPath(path))
    {
        await next();
        return;
    }

    var auth = context.RequestServices.GetRequiredService<AuthStore>();
    var user = auth.Authenticate(ReadBearerToken(context.Request));
    if (user is null)
    {
        await WriteAuthError(context, StatusCodes.Status401Unauthorized, "AUTH_REQUIRED", "Authorization required");
        return;
    }

    context.Items["CurrentUser"] = user;
    if (!IsAuthorized(user, context.Request.Method, path))
    {
        await WriteAuthError(context, StatusCodes.Status403Forbidden, "FORBIDDEN", "Not enough permissions");
        return;
    }

    await next();

    if (context.Response.StatusCode < 400 && ShouldAudit(context.Request.Method, path))
    {
        auth.LogAudit(user.Login, context.Request.Method, path);
    }
});

app.MapGet("/", () => Results.Text("CalHouse API is running"));

var api = app.MapGroup("/api");

api.MapPost("/auth/register", (RegisterRequest request, AuthStore auth) => Handle(() => Results.Ok(auth.Register(request.Login, request.Password, request.ConfirmPassword))));
api.MapPost("/auth/login", (LoginRequest request, AuthStore auth) => Handle(() => Results.Ok(auth.Login(request.Login, request.Password))));
api.MapGet("/auth/me", (HttpContext context) => Results.Ok(CurrentUser(context)));

api.MapGet("/users", (AuthStore auth) => Handle(() => Results.Ok(auth.GetUsers())));
api.MapPut("/users/{id:int}/role", (int id, UpdateUserRoleRequest request, AuthStore auth) => Handle(() => Results.Ok(auth.SetRole(id, request.Role))));
api.MapPut("/users/{id:int}/active", (int id, UpdateUserActiveRequest request, AuthStore auth) => Handle(() => Results.Ok(auth.SetActive(id, request.IsActive))));
api.MapPut("/users/{id:int}/password", (int id, ResetUserPasswordRequest request, HttpContext context, AuthStore auth) =>
    Handle(() => Results.Ok(auth.ResetPassword(id, request.Password, request.ConfirmPassword, CurrentUser(context).Login))));

api.MapGet("/device-catalog", (DeviceCatalogService catalog) => Results.Ok(catalog.GetCatalog()));
api.MapGet("/device-catalog/types", (DeviceCatalogService catalog) => Results.Ok(catalog.GetDeviceTypes()));
api.MapGet("/device-catalog/providers", (DeviceCatalogService catalog) => Results.Ok(catalog.GetProviders()));
api.MapGet("/device-catalog/types/{typeCode}/providers", (string typeCode, DeviceCatalogService catalog) => Handle(() => Results.Ok(catalog.GetProvidersForType(typeCode))));
api.MapGet("/device-catalog/form-schema", (string typeCode, string providerCode, DeviceCatalogService catalog) => Handle(() => Results.Ok(catalog.GetFormSchema(typeCode, providerCode))));

api.MapGet("/devices", (int? roomId, DeviceStore store) => Results.Ok(store.GetAllDevices(roomId)));
api.MapGet("/devices/{id:int}", (int id, DeviceStore store) => Handle(() => Results.Ok(store.GetDevice(id))));
api.MapPost("/devices", (CreateDeviceRequest request, DeviceStore store) => Handle(() =>
{
    var created = store.AddDevice(
        request.Name,
        request.Room,
        request.RoomId,
        request.IsOn,
        request.Type,
        request.Provider,
        request.Protocol,
        request.Channel,
        request.ExternalId,
        request.Manufacturer,
        request.Model,
        request.Connection);
    return Results.Created($"/api/devices/{created.Id}", created);
}));
api.MapPut("/devices/{id:int}", (int id, UpdateDeviceRequest request, DeviceStore store) => Handle(() => Results.Ok(store.UpdateDevice(
    id,
    request.Name,
    request.Room,
    request.RoomId,
    request.IsOn,
    request.Type,
    request.Provider,
    request.Protocol,
    request.Channel,
    request.ExternalId,
    request.Manufacturer,
    request.Model,
    request.Connection))));
api.MapPut("/devices/{id:int}/toggle", (int id, DeviceStore store, DeviceCommandQueue queue) => Handle(() => Results.Ok(store.QueueToggleDevice(id, queue))));
api.MapPut("/devices/{id:int}/room", (int id, AssignDeviceRoomRequest request, DeviceStore store) => Handle(() => Results.Ok(store.AssignDeviceToRoom(id, request.RoomId))));
api.MapDelete("/devices/{id:int}", (int id, DeviceStore store) => Handle(() => Results.Ok(store.DeleteDevice(id))));
api.MapPost("/devices/validate-connection", (ValidateConnectionRequest request, DeviceStore store) => Handle(() => Results.Ok(store.ValidateConnection(request.Provider, request.Protocol, request.Connection))));
api.MapPost("/events", (DeviceEventRequest request, DeviceStore store, DeviceCommandQueue queue) => Handle(() => Results.Ok(store.ProcessIncomingEventQueued(request.DeviceId, request.DeviceExternalId, request.EventType, request.Value, request.Message, queue))));

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
api.MapPut("/rooms/{id:int}", (int id, UpdateRoomRequest request, DeviceStore store) => Handle(() => Results.Ok(store.UpdateRoom(id, request.Name, request.Zone))));
api.MapDelete("/rooms/{id:int}", (int id, DeviceStore store) => Handle(() =>
{
    store.DeleteRoom(id);
    return Results.NoContent();
}));

api.MapGet("/scenes", (DeviceStore store) => Results.Ok(store.GetAllScenes()));
api.MapGet("/scenes/{id:int}", (int id, DeviceStore store) => Handle(() => Results.Ok(store.GetScene(id))));
api.MapGet("/scenes/{id:int}/runs", (int id, int? limit, DeviceStore store) => Handle(() => Results.Ok(store.GetSceneRuns(id, limit ?? 20))));
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
api.MapPost("/scenes/{id:int}/run", (int id, DeviceStore store, DeviceCommandQueue queue) => Handle(() => Results.Ok(store.QueueSceneRun(id, queue))));

api.MapGet("/rules", (DeviceStore store) => Results.Ok(store.GetAllRules()));
api.MapGet("/rules/{id:int}", (int id, DeviceStore store) => Handle(() => Results.Ok(store.GetRule(id))));
api.MapGet("/rules/{id:int}/runs", (int id, int? limit, DeviceStore store) => Handle(() => Results.Ok(store.GetRuleRuns(id, limit ?? 20))));
api.MapPost("/rules", (CreateRuleRequest request, DeviceStore store) => Handle(() =>
{
    var created = store.CreateRule(
        request.Name,
        request.Description,
        request.IsEnabled,
        request.TriggerDeviceId,
        request.EventType,
        request.ComparisonOperator,
        request.CompareValue,
        request.ActionKind,
        request.ActionDeviceId,
        request.ActionTargetIsOn,
        request.ActionSceneId);
    return Results.Created($"/api/rules/{created.Id}", created);
}));
api.MapPut("/rules/{id:int}", (int id, UpdateRuleRequest request, DeviceStore store) => Handle(() => Results.Ok(store.UpdateRule(
    id,
    request.Name,
    request.Description,
    request.IsEnabled,
    request.TriggerDeviceId,
    request.EventType,
    request.ComparisonOperator,
    request.CompareValue,
    request.ActionKind,
    request.ActionDeviceId,
    request.ActionTargetIsOn,
    request.ActionSceneId))));
api.MapPut("/rules/{id:int}/enabled", (int id, SetEnabledRequest request, DeviceStore store) => Handle(() => Results.Ok(store.SetRuleEnabled(id, request.IsEnabled))));
api.MapDelete("/rules/{id:int}", (int id, DeviceStore store) => Handle(() =>
{
    store.DeleteRule(id);
    return Results.NoContent();
}));

api.MapGet("/schedules", (DeviceStore store) => Results.Ok(store.GetAllSchedules()));
api.MapGet("/schedules/{id:int}", (int id, DeviceStore store) => Handle(() => Results.Ok(store.GetSchedule(id))));
api.MapGet("/schedules/{id:int}/runs", (int id, int? limit, DeviceStore store) => Handle(() => Results.Ok(store.GetScheduleRuns(id, limit ?? 20))));
api.MapPost("/schedules", (CreateScheduleRequest request, DeviceStore store) => Handle(() =>
{
    var created = store.CreateSchedule(
        request.Name,
        request.Description,
        request.IsEnabled,
        request.TimeOfDay,
        request.DaysOfWeek,
        request.ActionKind,
        request.ActionDeviceId,
        request.ActionTargetIsOn,
        request.ActionSceneId);
    return Results.Created($"/api/schedules/{created.Id}", created);
}));
api.MapPut("/schedules/{id:int}", (int id, UpdateScheduleRequest request, DeviceStore store) => Handle(() => Results.Ok(store.UpdateSchedule(
    id,
    request.Name,
    request.Description,
    request.IsEnabled,
    request.TimeOfDay,
    request.DaysOfWeek,
    request.ActionKind,
    request.ActionDeviceId,
    request.ActionTargetIsOn,
    request.ActionSceneId))));
api.MapPut("/schedules/{id:int}/enabled", (int id, SetEnabledRequest request, DeviceStore store) => Handle(() => Results.Ok(store.SetScheduleEnabled(id, request.IsEnabled))));
api.MapPost("/schedules/run-due", (DeviceStore store, DeviceCommandQueue queue) => Handle(() => Results.Ok(store.QueueDueSchedules(queue))));
api.MapDelete("/schedules/{id:int}", (int id, DeviceStore store) => Handle(() =>
{
    store.DeleteSchedule(id);
    return Results.NoContent();
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

static bool IsPublicAuthPath(string path)
{
    return string.Equals(path, "/api/auth/register", StringComparison.OrdinalIgnoreCase)
        || string.Equals(path, "/api/auth/login", StringComparison.OrdinalIgnoreCase);
}

static string? ReadBearerToken(HttpRequest request)
{
    var header = request.Headers.Authorization.ToString();
    const string prefix = "Bearer ";
    if (header.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
    {
        return header[prefix.Length..].Trim();
    }
    return null;
}

static bool IsAuthorized(AuthenticatedUser user, string method, string path)
{
    if (string.Equals(user.Role, "Admin", StringComparison.OrdinalIgnoreCase))
    {
        return true;
    }

    if (path.StartsWith("/api/users", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }

    if (HttpMethods.IsGet(method))
    {
        return true;
    }

    if (HttpMethods.IsPut(method) && Regex.IsMatch(path, "^/api/devices/[0-9]+/toggle$", RegexOptions.IgnoreCase))
    {
        return true;
    }

    if (HttpMethods.IsPost(method) && Regex.IsMatch(path, "^/api/scenes/[0-9]+/run$", RegexOptions.IgnoreCase))
    {
        return true;
    }

    if (HttpMethods.IsPost(method) && string.Equals(path, "/api/events", StringComparison.OrdinalIgnoreCase))
    {
        return true;
    }

    return false;
}

static bool ShouldAudit(string method, string path)
{
    if (path.StartsWith("/api/auth", StringComparison.OrdinalIgnoreCase))
    {
        return false;
    }
    return !HttpMethods.IsGet(method);
}

static AuthenticatedUser CurrentUser(HttpContext context)
{
    return context.Items.TryGetValue("CurrentUser", out var value) && value is AuthenticatedUser user
        ? user
        : throw new ApiProblemException("Authorization required", "AUTH_REQUIRED", StatusCodes.Status401Unauthorized);
}

static async Task WriteAuthError(HttpContext context, int statusCode, string code, string message)
{
    context.Response.StatusCode = statusCode;
    context.Response.ContentType = "application/json";
    await context.Response.WriteAsJsonAsync(new { error = message, code, message });
}

internal sealed record RegisterRequest(string Login, string Password, string ConfirmPassword);
internal sealed record LoginRequest(string Login, string Password);
internal sealed record UpdateUserRoleRequest(string Role);
internal sealed record UpdateUserActiveRequest(bool IsActive);
internal sealed record ResetUserPasswordRequest(string Password, string ConfirmPassword);
internal sealed record CreateDeviceRequest(
    string Name,
    string? Room,
    int? RoomId,
    bool IsOn = false,
    string? Type = "Другое",
    string? Provider = "mock",
    string? Protocol = null,
    string? Channel = null,
    string? ExternalId = null,
    string? Manufacturer = null,
    string? Model = null,
    Dictionary<string, string>? Connection = null);

internal sealed record UpdateDeviceRequest(
    string? Name,
    string? Room,
    int? RoomId,
    bool? IsOn,
    string? Type,
    string? Provider,
    string? Protocol,
    string? Channel,
    string? ExternalId,
    string? Manufacturer,
    string? Model,
    Dictionary<string, string>? Connection);

internal sealed record AssignDeviceRoomRequest(int RoomId);
internal sealed record ValidateConnectionRequest(string? Provider, string? Protocol, Dictionary<string, string>? Connection);
internal sealed record DeviceEventRequest(int? DeviceId, string? DeviceExternalId, string EventType, string Value, string? Message);
internal sealed record CreateRoomRequest(string Name, string? Zone);
internal sealed record UpdateRoomRequest(string Name, string? Zone);
internal sealed record SceneActionRequest(int DeviceId, bool TargetIsOn, int? SortOrder);
internal sealed record CreateSceneRequest(string Name, string? Description, List<SceneActionRequest>? Actions);
internal sealed record UpdateSceneRequest(string Name, string? Description, List<SceneActionRequest>? Actions);
internal sealed record CreateRuleRequest(string Name, string? Description, bool IsEnabled, int TriggerDeviceId, string EventType, string ComparisonOperator, string CompareValue, string ActionKind, int? ActionDeviceId, bool? ActionTargetIsOn, int? ActionSceneId);
internal sealed record UpdateRuleRequest(string Name, string? Description, bool IsEnabled, int TriggerDeviceId, string EventType, string ComparisonOperator, string CompareValue, string ActionKind, int? ActionDeviceId, bool? ActionTargetIsOn, int? ActionSceneId);
internal sealed record CreateScheduleRequest(string Name, string? Description, bool IsEnabled, string TimeOfDay, List<int> DaysOfWeek, string ActionKind, int? ActionDeviceId, bool? ActionTargetIsOn, int? ActionSceneId);
internal sealed record UpdateScheduleRequest(string Name, string? Description, bool IsEnabled, string TimeOfDay, List<int> DaysOfWeek, string ActionKind, int? ActionDeviceId, bool? ActionTargetIsOn, int? ActionSceneId);
internal sealed record SetEnabledRequest(bool IsEnabled);
