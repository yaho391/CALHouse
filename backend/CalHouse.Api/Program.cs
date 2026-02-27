using CalHouse.Api.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSingleton<DeviceStore>();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();
builder.Services.AddCors(options =>
{
    options.AddPolicy("DevCors", policy =>
    {
        // Development-only permissive CORS policy.
        // For production, replace with WithOrigins("https://your-ui-host") and tighten methods/headers.
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

app.MapGet("/api/devices", (DeviceStore store) => Results.Ok(store.GetAllDevices()))
    .WithName("GetDevices")
    .Produces(StatusCodes.Status200OK);

app.MapGet("/api/devices/{id:int}", (int id, DeviceStore store) =>
{
    var device = store.GetDevice(id);
    return device is null ? Results.NotFound(new { message = "Device not found" }) : Results.Ok(device);
})
.WithName("GetDeviceById")
.Produces(StatusCodes.Status200OK)
.Produces(StatusCodes.Status404NotFound);

app.MapPost("/api/devices", (CreateDeviceRequest request, DeviceStore store) =>
{
    var name = (request.Name ?? string.Empty).Trim();
    var room = (request.Room ?? string.Empty).Trim();

    if (string.IsNullOrWhiteSpace(name) || string.IsNullOrWhiteSpace(room))
    {
        return Results.BadRequest(new { message = "Name and room are required" });
    }

    var created = store.AddDevice(name, room, request.IsOn);
    return Results.Created($"/api/devices/{created.Id}", created);
})
.WithName("CreateDevice")
.Produces(StatusCodes.Status201Created)
.Produces(StatusCodes.Status400BadRequest);

app.MapPut("/api/devices/{id:int}/toggle", (int id, DeviceStore store) =>
{
    var updated = store.ToggleDevice(id);
    return updated is null ? Results.NotFound(new { message = "Device not found" }) : Results.Ok(updated);
})
.WithName("ToggleDevice")
.Produces(StatusCodes.Status200OK)
.Produces(StatusCodes.Status404NotFound);

app.MapDelete("/api/devices/{id:int}", (int id, DeviceStore store) =>
{
    var removed = store.DeleteDevice(id);
    return removed is null ? Results.NotFound(new { message = "Device not found" }) : Results.Ok(removed);
})
.WithName("DeleteDevice")
.Produces(StatusCodes.Status200OK)
.Produces(StatusCodes.Status404NotFound);

app.Run();

internal sealed record CreateDeviceRequest(string? Name, string? Room, bool IsOn = false);
