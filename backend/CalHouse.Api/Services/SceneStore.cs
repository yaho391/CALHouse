using System.Text.Json;
using CalHouse.Api.Models;

namespace CalHouse.Api.Services;

public class SceneStore
{
    private readonly string _scenesPath;
    private readonly string _logsPath;
    private readonly JsonSerializerOptions _jsonOptions = new() { WriteIndented = true };
    private readonly object _sync = new();

    public SceneStore(IWebHostEnvironment environment)
    {
        var appDataDirectory = Path.Combine(environment.ContentRootPath, "App_Data");
        Directory.CreateDirectory(appDataDirectory);

        _scenesPath = Path.Combine(appDataDirectory, "scenes.json");
        _logsPath = Path.Combine(appDataDirectory, "scene_executions.json");

        if (!File.Exists(_scenesPath))
        {
            SaveScenes(new List<Scene>());
        }

        if (!File.Exists(_logsPath))
        {
            SaveLogs(new List<SceneExecutionLog>());
        }
    }

    public IReadOnlyList<Scene> GetAllScenes()
    {
        lock (_sync)
        {
            return ReadScenes();
        }
    }

    public Scene? GetScene(int id)
    {
        lock (_sync)
        {
            return ReadScenes().FirstOrDefault(s => s.Id == id);
        }
    }

    public Scene AddScene(string name, string? description, List<SceneAction> actions)
    {
        lock (_sync)
        {
            var scenes = ReadScenes();
            var scene = new Scene
            {
                Id = scenes.Count == 0 ? 1 : scenes.Max(s => s.Id) + 1,
                Name = name.Trim(),
                Description = string.IsNullOrWhiteSpace(description) ? string.Empty : description.Trim(),
                Actions = actions
            };

            scenes.Add(scene);
            SaveScenes(scenes);
            return scene;
        }
    }

    public Scene? UpdateScene(int id, string name, string? description, List<SceneAction> actions)
    {
        lock (_sync)
        {
            var scenes = ReadScenes();
            var scene = scenes.FirstOrDefault(s => s.Id == id);
            if (scene is null)
            {
                return null;
            }

            scene.Name = name.Trim();
            scene.Description = string.IsNullOrWhiteSpace(description) ? string.Empty : description.Trim();
            scene.Actions = actions;
            SaveScenes(scenes);
            return scene;
        }
    }

    public Scene? DeleteScene(int id)
    {
        lock (_sync)
        {
            var scenes = ReadScenes();
            var scene = scenes.FirstOrDefault(s => s.Id == id);
            if (scene is null)
            {
                return null;
            }

            scenes.Remove(scene);
            SaveScenes(scenes);
            return scene;
        }
    }

    public SceneExecutionLog AddExecutionLog(int sceneId, string sceneName, List<SceneExecutionItem> items)
    {
        lock (_sync)
        {
            var logs = ReadLogs();
            var now = DateTimeOffset.UtcNow;
            var log = new SceneExecutionLog
            {
                Id = logs.Count == 0 ? 1 : logs.Max(l => l.Id) + 1,
                SceneId = sceneId,
                SceneName = sceneName,
                StartedAtUtc = now,
                FinishedAtUtc = now,
                Status = items.All(i => i.Status == "applied") ? "completed" : "completed_with_warnings",
                Results = items
            };

            logs.Add(log);
            SaveLogs(logs);
            return log;
        }
    }

    public IReadOnlyList<SceneExecutionLog> GetExecutionLogs(int? sceneId = null)
    {
        lock (_sync)
        {
            var logs = ReadLogs().OrderByDescending(l => l.Id).ToList();
            if (sceneId.HasValue)
            {
                logs = logs.Where(l => l.SceneId == sceneId.Value).ToList();
            }

            return logs;
        }
    }

    private List<Scene> ReadScenes()
    {
        return JsonSerializer.Deserialize<List<Scene>>(File.ReadAllText(_scenesPath)) ?? new List<Scene>();
    }

    private List<SceneExecutionLog> ReadLogs()
    {
        return JsonSerializer.Deserialize<List<SceneExecutionLog>>(File.ReadAllText(_logsPath)) ?? new List<SceneExecutionLog>();
    }

    private void SaveScenes(List<Scene> scenes)
    {
        File.WriteAllText(_scenesPath, JsonSerializer.Serialize(scenes, _jsonOptions));
    }

    private void SaveLogs(List<SceneExecutionLog> logs)
    {
        File.WriteAllText(_logsPath, JsonSerializer.Serialize(logs, _jsonOptions));
    }
}
