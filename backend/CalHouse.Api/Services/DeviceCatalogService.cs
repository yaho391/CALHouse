using CalHouse.Api.Infrastructure;
using CalHouse.Api.Models;

namespace CalHouse.Api.Services;

public sealed class DeviceCatalogService
{
    private static readonly string[] RuleOperators = ["=", "!=", ">", ">=", "<", "<=", "contains"];
    private static readonly string[] ActionKinds = ["device_state", "scene_run"];

    private readonly IReadOnlyList<DeviceTypeDefinition> _deviceTypes;
    private readonly IReadOnlyList<ProviderDefinition> _providers;
    private readonly Dictionary<string, string> _typeAliases;
    private readonly Dictionary<string, string> _providerAliases;

    public DeviceCatalogService()
    {
        _deviceTypes = BuildDeviceTypes();
        _providers = BuildProviders();
        _typeAliases = BuildTypeAliases(_deviceTypes);
        _providerAliases = BuildProviderAliases(_providers);
    }

    public DeviceCatalogResponse GetCatalog()
    {
        return new DeviceCatalogResponse
        {
            DeviceTypes = _deviceTypes,
            Providers = _providers,
            RuleOperators = RuleOperators,
            ActionKinds = ActionKinds,
            ScheduleDays =
            [
                new() { Value = 1, Title = "Пн" },
                new() { Value = 2, Title = "Вт" },
                new() { Value = 3, Title = "Ср" },
                new() { Value = 4, Title = "Чт" },
                new() { Value = 5, Title = "Пт" },
                new() { Value = 6, Title = "Сб" },
                new() { Value = 7, Title = "Вс" },
            ],
        };
    }

    public IReadOnlyList<DeviceTypeDefinition> GetDeviceTypes() => _deviceTypes;

    public IReadOnlyList<ProviderDefinition> GetProviders() => _providers;

    public IReadOnlyList<ProviderDefinition> GetProvidersForType(string? typeCode)
    {
        var type = GetDeviceType(typeCode);
        var allowed = type.AllowedProviders.ToHashSet(StringComparer.OrdinalIgnoreCase);
        return _providers.Where(provider => allowed.Contains(provider.Code)).ToList();
    }

    public DeviceFormSchema GetFormSchema(string? typeCode, string? providerCode)
    {
        var type = GetDeviceType(typeCode);
        var provider = GetProvider(providerCode);
        EnsureProviderAllowed(type, provider.Code);

        var required = type.RequiredFields
            .Concat(provider.RequiredFields)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);

        var fields = provider.FormFields
            .Select(field => new DeviceFormFieldDefinition
            {
                Name = field.Name,
                Label = field.Label,
                Kind = field.Kind,
                Required = field.Required || required.Contains(field.Name),
                Secret = field.Secret,
                Placeholder = field.Placeholder,
            })
            .ToList();

        return new DeviceFormSchema
        {
            TypeCode = type.Code,
            ProviderCode = provider.Code,
            Capabilities = type.Capabilities,
            Fields = fields,
            Actions = type.Actions,
        };
    }

    public string NormalizeDeviceTypeCode(string? typeCode)
    {
        var normalized = NormalizeKey(typeCode);
        if (string.IsNullOrWhiteSpace(normalized))
        {
            return "generic";
        }

        return _typeAliases.TryGetValue(normalized, out var canonical)
            ? canonical
            : normalized;
    }

    public string NormalizeProviderCode(string? providerCode)
    {
        var normalized = NormalizeKey(providerCode);
        if (string.IsNullOrWhiteSpace(normalized))
        {
            return "mock";
        }

        return _providerAliases.TryGetValue(normalized, out var canonical)
            ? canonical
            : normalized;
    }

    public string InferProtocol(string? providerCode)
    {
        var provider = GetProvider(providerCode);
        return provider.Protocol;
    }

    public string InferChannel(string? providerCode, string? protocol = null)
    {
        var provider = GetProvider(providerCode);
        if (!string.IsNullOrWhiteSpace(provider.Channel))
        {
            return provider.Channel;
        }

        return NormalizeKey(protocol) switch
        {
            "http" or "https" => "wifi",
            "mqtt" => "mqtt",
            "rtsp" or "tcp" => "lan",
            _ => "local",
        };
    }

    public IReadOnlyList<string> GetRequiredConnectionFields(string? typeCode, string? providerCode, string? protocol)
    {
        var provider = GetProvider(providerCode);
        var type = GetDeviceType(typeCode);
        EnsureProviderAllowed(type, provider.Code);

        return type.RequiredFields
            .Concat(provider.RequiredFields)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    public DeviceTypeDefinition GetDeviceType(string? typeCode)
    {
        var normalized = NormalizeDeviceTypeCode(typeCode);
        return _deviceTypes.FirstOrDefault(type => string.Equals(type.Code, normalized, StringComparison.OrdinalIgnoreCase))
            ?? throw new ValidationProblemException($"Unknown device type: {typeCode}", "DEVICE_TYPE_UNKNOWN");
    }

    public ProviderDefinition GetProvider(string? providerCode)
    {
        var normalized = NormalizeProviderCode(providerCode);
        return _providers.FirstOrDefault(provider => string.Equals(provider.Code, normalized, StringComparison.OrdinalIgnoreCase))
            ?? throw new ValidationProblemException($"Unknown device provider: {providerCode}", "DEVICE_PROVIDER_UNKNOWN");
    }

    public void EnsureProviderAllowed(string? typeCode, string? providerCode)
    {
        var type = GetDeviceType(typeCode);
        var provider = GetProvider(providerCode);
        EnsureProviderAllowed(type, provider.Code);
    }

    private static void EnsureProviderAllowed(DeviceTypeDefinition type, string providerCode)
    {
        if (!type.AllowedProviders.Contains(providerCode, StringComparer.OrdinalIgnoreCase))
        {
            throw new ValidationProblemException($"Provider {providerCode} is not allowed for device type {type.Code}", "DEVICE_PROVIDER_NOT_ALLOWED");
        }
    }

    private static IReadOnlyList<DeviceTypeDefinition> BuildDeviceTypes()
    {
        var controllable = new DeviceCapabilities
        {
            CanToggle = true,
            CanReceiveCommands = true,
            CanEmitEvents = true,
            SupportsSchedule = true,
            SupportsRules = true,
            SupportsMonitoringOnly = false,
        };

        var sensor = new DeviceCapabilities
        {
            CanToggle = false,
            CanReceiveCommands = false,
            CanEmitEvents = true,
            SupportsSchedule = false,
            SupportsRules = true,
            SupportsMonitoringOnly = true,
        };

        var camera = new DeviceCapabilities
        {
            CanToggle = false,
            CanReceiveCommands = false,
            CanEmitEvents = true,
            SupportsSchedule = false,
            SupportsRules = true,
            SupportsMonitoringOnly = true,
        };

        var thermostat = new DeviceCapabilities
        {
            CanToggle = false,
            CanReceiveCommands = true,
            CanEmitEvents = true,
            SupportsSchedule = true,
            SupportsRules = true,
            SupportsMonitoringOnly = false,
        };

        var generic = new DeviceCapabilities
        {
            CanToggle = false,
            CanReceiveCommands = false,
            CanEmitEvents = true,
            SupportsSchedule = false,
            SupportsRules = true,
            SupportsMonitoringOnly = true,
        };

        return
        [
            new()
            {
                Code = "light",
                DisplayName = "Свет",
                Capabilities = controllable,
                AllowedProviders = ["mock", "demo", "mqtt", "zigbee2mqtt", "homeassistant", "tasmota", "shelly", "custom_http"],
                OptionalFields = ["brightness_topic", "state_topic"],
                Actions = [ToggleAction()],
                LegacyNames = ["Свет", "РЎРІРµС‚"],
            },
            new()
            {
                Code = "socket",
                DisplayName = "Розетка",
                Capabilities = controllable,
                AllowedProviders = ["mock", "demo", "mqtt", "zigbee2mqtt", "homeassistant", "tasmota", "shelly", "custom_http"],
                Actions = [ToggleAction()],
                LegacyNames = ["Розетка", "Р РѕР·РµС‚РєР°"],
            },
            new()
            {
                Code = "relay",
                DisplayName = "Реле",
                Capabilities = controllable,
                AllowedProviders = ["mock", "mqtt", "zigbee2mqtt", "homeassistant", "tasmota", "shelly", "custom_http", "custom_tcp"],
                Actions = [ToggleAction(), PulseAction()],
            },
            new()
            {
                Code = "motion_sensor",
                DisplayName = "Датчик движения",
                Capabilities = sensor,
                AllowedProviders = ["mock", "demo", "mqtt", "zigbee2mqtt", "homeassistant"],
                OptionalFields = ["motion_topic", "battery_topic"],
                Actions = [],
                LegacyNames = ["Датчик", "Р”Р°С‚С‡РёРє"],
            },
            new()
            {
                Code = "temperature_sensor",
                DisplayName = "Датчик температуры",
                Capabilities = sensor,
                AllowedProviders = ["mock", "demo", "mqtt", "zigbee2mqtt", "homeassistant"],
                OptionalFields = ["temperature_topic", "humidity_topic", "battery_topic"],
                Actions = [],
                LegacyNames = ["Климат", "РљР»РёРјР°С‚"],
            },
            new()
            {
                Code = "leak_sensor",
                DisplayName = "Датчик протечки",
                Capabilities = sensor,
                AllowedProviders = ["mock", "demo", "mqtt", "zigbee2mqtt", "homeassistant"],
                OptionalFields = ["leak_topic", "battery_topic"],
                Actions = [],
                LegacyNames = ["Датчик протечки"],
            },
            new()
            {
                Code = "thermostat",
                DisplayName = "Термостат",
                Capabilities = thermostat,
                AllowedProviders = ["mock", "mqtt", "zigbee2mqtt", "homeassistant", "custom_http"],
                OptionalFields = ["temperature_topic", "setpoint_topic", "mode_topic"],
                Actions = [SetTemperatureAction()],
                LegacyNames = ["Термостат"],
            },
            new()
            {
                Code = "camera",
                DisplayName = "Камера",
                Capabilities = camera,
                AllowedProviders = ["mock", "homeassistant", "camera_rtsp"],
                RequiredFields = [],
                OptionalFields = ["snapshot_url"],
                Actions = [],
                LegacyNames = ["Камера", "РљР°РјРµСЂР°"],
            },
            new()
            {
                Code = "generic",
                DisplayName = "Другое",
                Capabilities = generic,
                AllowedProviders = ["mock", "mqtt", "homeassistant", "custom_http", "custom_tcp"],
                Actions = [],
                LegacyNames = ["Другое", "Р”СЂСѓРіРѕРµ"],
            },
        ];
    }

    private static IReadOnlyList<ProviderDefinition> BuildProviders()
    {
        return
        [
            new()
            {
                Code = "mock",
                DisplayName = "Локальный тестовый режим",
                Protocol = "manual",
                Channel = "local",
                TestMode = "local",
                SupportsCommands = true,
                SupportsEvents = true,
                FormFields = [],
                Note = "Локальный тестовый режим: сетевые параметры не нужны, команда не отправляется на реальное устройство.",
            },
            new()
            {
                Code = "demo",
                DisplayName = "Визуализация дома",
                Protocol = "demo",
                Channel = "local",
                TestMode = "local",
                SupportsCommands = true,
                SupportsEvents = true,
                FormFields = [],
                Note = "Демо-устройство для визуализации: состояние меняется локально без обращения к реальному оборудованию.",
            },
            new()
            {
                Code = "mqtt",
                DisplayName = "MQTT",
                Protocol = "mqtt",
                Channel = "mqtt",
                TestMode = "tcp",
                SupportsCommands = true,
                SupportsEvents = true,
                RequiredFields = ["host", "port", "topic"],
                OptionalFields = ["username", "password", "state_topic", "payload_on", "payload_off", "payload_template"],
                FormFields = [HostField(), PortField("1883"), TopicField(), UsernameField(), PasswordField(), StateTopicField(), PayloadOnField(), PayloadOffField(), PayloadTemplateField()],
                Note = "MQTT: укажи брокер, порт и topic устройства.",
            },
            new()
            {
                Code = "zigbee2mqtt",
                DisplayName = "Zigbee2MQTT",
                Protocol = "mqtt",
                Channel = "zigbee",
                TestMode = "tcp",
                SupportsCommands = true,
                SupportsEvents = true,
                RequiredFields = ["host", "port", "topic"],
                OptionalFields = ["username", "password", "state_topic", "payload_template"],
                FormFields = [HostField(), PortField("1883"), TopicField("Topic устройства"), StateTopicField(), UsernameField(), PasswordField(), PayloadTemplateField()],
                Note = "Zigbee2MQTT: укажи MQTT-брокер и topic Zigbee-устройства.",
            },
            new()
            {
                Code = "homeassistant",
                DisplayName = "Home Assistant",
                Protocol = "http",
                Channel = "lan",
                TestMode = "http",
                SupportsCommands = true,
                SupportsEvents = true,
                RequiredFields = ["url", "token", "entity_id"],
                OptionalFields = ["state_url"],
                FormFields = [UrlField("URL Home Assistant"), TokenField(), EntityIdField()],
                Note = "Home Assistant: укажи адрес API, токен и entity_id.",
            },
            new()
            {
                Code = "tasmota",
                DisplayName = "Tasmota",
                Protocol = "http",
                Channel = "wifi",
                TestMode = "http",
                SupportsCommands = true,
                SupportsEvents = true,
                RequiredFields = ["host"],
                OptionalFields = ["username", "password", "path"],
                FormFields = [HostField(), PathField("/cm"), UsernameField(), PasswordField()],
                Note = "Tasmota: укажи IP/host устройства. Path можно оставить стандартным.",
            },
            new()
            {
                Code = "shelly",
                DisplayName = "Shelly",
                Protocol = "http",
                Channel = "wifi",
                TestMode = "http",
                SupportsCommands = true,
                SupportsEvents = true,
                RequiredFields = ["host"],
                OptionalFields = ["username", "password", "path"],
                FormFields = [HostField(), PathField("/rpc/Shelly.GetStatus"), UsernameField(), PasswordField()],
                Note = "Shelly: укажи IP/host устройства. Path используется для проверки HTTP-доступности.",
            },
            new()
            {
                Code = "custom_http",
                DisplayName = "Произвольный HTTP",
                Protocol = "http",
                Channel = "lan",
                TestMode = "http",
                SupportsCommands = true,
                SupportsEvents = true,
                RequiredFields = ["url"],
                OptionalFields = ["method", "headers", "body_template"],
                FormFields = [UrlField("URL команды"), MethodField(), HeadersField(), BodyTemplateField()],
                LegacyKeys = ["http"],
                Note = "Произвольный HTTP: укажи URL команды, метод и при необходимости headers/body.",
            },
            new()
            {
                Code = "camera_rtsp",
                DisplayName = "RTSP-камера",
                Protocol = "rtsp",
                Channel = "lan",
                TestMode = "tcp",
                SupportsCommands = false,
                SupportsEvents = true,
                RequiredFields = ["host", "port"],
                OptionalFields = ["username", "password", "path", "snapshot_url"],
                FormFields = [HostField(), PortField("554"), PathField("/stream1"), UsernameField(), PasswordField(), SnapshotUrlField()],
                LegacyKeys = ["camera"],
                Note = "RTSP-камера: укажи host, port и путь потока. Камера работает как устройство мониторинга без Toggle.",
            },
            new()
            {
                Code = "custom_tcp",
                DisplayName = "Произвольный TCP",
                Protocol = "tcp",
                Channel = "lan",
                TestMode = "tcp",
                SupportsCommands = true,
                SupportsEvents = false,
                RequiredFields = ["host", "port"],
                OptionalFields = ["payload_template"],
                FormFields = [HostField(), PortField(), PayloadTemplateField()],
                LegacyKeys = ["custom"],
                Note = "Произвольный TCP: укажи host, port и шаблон payload при необходимости.",
            },
        ];
    }

    private static Dictionary<string, string> BuildTypeAliases(IEnumerable<DeviceTypeDefinition> deviceTypes)
    {
        var aliases = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var type in deviceTypes)
        {
            aliases[NormalizeKey(type.Code)] = type.Code;
            aliases[NormalizeKey(type.DisplayName)] = type.Code;
            foreach (var legacy in type.LegacyNames)
            {
                aliases[NormalizeKey(legacy)] = type.Code;
            }
        }

        aliases[NormalizeKey("\u0421\u0432\u0435\u0442")] = "light";
        aliases[NormalizeKey("\u0420\u043e\u0437\u0435\u0442\u043a\u0430")] = "socket";
        aliases[NormalizeKey("\u0414\u0430\u0442\u0447\u0438\u043a")] = "motion_sensor";
        aliases[NormalizeKey("\u041a\u043b\u0438\u043c\u0430\u0442")] = "temperature_sensor";
        aliases[NormalizeKey("\u0422\u0435\u0440\u043c\u043e\u0441\u0442\u0430\u0442")] = "thermostat";
        aliases[NormalizeKey("\u041a\u0430\u043c\u0435\u0440\u0430")] = "camera";
        aliases[NormalizeKey("\u0414\u0440\u0443\u0433\u043e\u0435")] = "generic";
        aliases[NormalizeKey("\u0417\u0430\u043c\u043e\u043a")] = "generic";
        aliases[NormalizeKey("\u0428\u0442\u043e\u0440\u0430")] = "generic";

        return aliases;
    }

    private static Dictionary<string, string> BuildProviderAliases(IEnumerable<ProviderDefinition> providers)
    {
        var aliases = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var provider in providers)
        {
            aliases[NormalizeKey(provider.Code)] = provider.Code;
            foreach (var legacy in provider.LegacyKeys)
            {
                aliases[NormalizeKey(legacy)] = provider.Code;
            }
        }

        return aliases;
    }

    private static string NormalizeKey(string? value)
    {
        return (value ?? string.Empty).Trim().ToLowerInvariant();
    }

    private static DeviceActionDefinition ToggleAction() => new()
    {
        Code = "set_power",
        DisplayName = "Изменить питание",
        RequiredFields = ["isOn"],
    };

    private static DeviceActionDefinition PulseAction() => new()
    {
        Code = "pulse",
        DisplayName = "Импульс",
        RequiredFields = ["durationMs"],
    };

    private static DeviceActionDefinition SetTemperatureAction() => new()
    {
        Code = "set_temperature",
        DisplayName = "Установить температуру",
        RequiredFields = ["targetTemperature"],
    };

    private static DeviceFormFieldDefinition HostField() => new() { Name = "host", Label = "Host / IP", Kind = "text", Required = true, Placeholder = "192.168.1.50" };
    private static DeviceFormFieldDefinition PortField(string placeholder = "") => new() { Name = "port", Label = "Port", Kind = "number", Required = true, Placeholder = placeholder };
    private static DeviceFormFieldDefinition TopicField(string label = "Topic") => new() { Name = "topic", Label = label, Kind = "text", Required = true, Placeholder = "home/device/set" };
    private static DeviceFormFieldDefinition StateTopicField() => new() { Name = "state_topic", Label = "Topic состояния", Kind = "text", Placeholder = "home/device/state" };
    private static DeviceFormFieldDefinition UsernameField() => new() { Name = "username", Label = "Пользователь", Kind = "text" };
    private static DeviceFormFieldDefinition PasswordField() => new() { Name = "password", Label = "Пароль / ключ устройства", Kind = "password", Secret = true };
    private static DeviceFormFieldDefinition UrlField(string label) => new() { Name = "url", Label = label, Kind = "url", Required = true, Placeholder = "http://host/path" };
    private static DeviceFormFieldDefinition TokenField() => new() { Name = "token", Label = "Токен", Kind = "password", Required = true, Secret = true };
    private static DeviceFormFieldDefinition EntityIdField() => new() { Name = "entity_id", Label = "Entity ID", Kind = "text", Required = true, Placeholder = "light.kitchen" };
    private static DeviceFormFieldDefinition PathField(string placeholder) => new() { Name = "path", Label = "Path", Kind = "text", Placeholder = placeholder };
    private static DeviceFormFieldDefinition MethodField() => new() { Name = "method", Label = "HTTP-метод", Kind = "text", Placeholder = "POST" };
    private static DeviceFormFieldDefinition HeadersField() => new() { Name = "headers", Label = "Заголовки JSON", Kind = "textarea" };
    private static DeviceFormFieldDefinition BodyTemplateField() => new() { Name = "body_template", Label = "Шаблон body", Kind = "textarea" };
    private static DeviceFormFieldDefinition SnapshotUrlField() => new() { Name = "snapshot_url", Label = "URL снимка", Kind = "url" };
    private static DeviceFormFieldDefinition PayloadOnField() => new() { Name = "payload_on", Label = "Payload ON", Kind = "text", Placeholder = "ON" };
    private static DeviceFormFieldDefinition PayloadOffField() => new() { Name = "payload_off", Label = "Payload OFF", Kind = "text", Placeholder = "OFF" };
    private static DeviceFormFieldDefinition PayloadTemplateField() => new() { Name = "payload_template", Label = "Шаблон payload", Kind = "textarea" };
}
