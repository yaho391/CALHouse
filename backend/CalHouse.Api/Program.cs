using CalHouse.Api.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddSingleton<DeviceStore>();
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

app.UseCors("DevCors");

app.MapGet("/api/devices", (DeviceStore store) => Results.Ok(store.GetAllDevices()));

app.MapPut("/api/devices/{id:int}/toggle", (int id, DeviceStore store) =>
{
    var updated = store.ToggleDevice(id);
    return updated is null ? Results.NotFound(new { message = "Device not found" }) : Results.Ok(updated);
});

app.Run();
