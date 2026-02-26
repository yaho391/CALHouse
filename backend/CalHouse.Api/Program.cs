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

app.MapPut("/api/devices/{id:int}/toggle", (int id, DeviceStore store) =>
{
    var updated = store.ToggleDevice(id);
    return updated is null ? Results.NotFound(new { message = "Device not found" }) : Results.Ok(updated);
})
.WithName("ToggleDevice")
.Produces(StatusCodes.Status200OK)
.Produces(StatusCodes.Status404NotFound);

app.Run();
