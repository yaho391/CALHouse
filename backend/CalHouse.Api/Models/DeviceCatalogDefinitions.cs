namespace CalHouse.Api.Models;

public sealed class DeviceCatalogResponse
{
    public IReadOnlyList<DeviceTypeDefinition> DeviceTypes { get; init; } = [];
    public IReadOnlyList<ProviderDefinition> Providers { get; init; } = [];
    public IReadOnlyList<string> RuleOperators { get; init; } = [];
    public IReadOnlyList<string> ActionKinds { get; init; } = [];
    public IReadOnlyList<ScheduleDayDefinition> ScheduleDays { get; init; } = [];
}

public sealed class DeviceTypeDefinition
{
    public string Code { get; init; } = string.Empty;
    public string DisplayName { get; init; } = string.Empty;
    public DeviceCapabilities Capabilities { get; init; } = new();
    public IReadOnlyList<string> AllowedProviders { get; init; } = [];
    public IReadOnlyList<string> RequiredFields { get; init; } = [];
    public IReadOnlyList<string> OptionalFields { get; init; } = [];
    public IReadOnlyList<DeviceActionDefinition> Actions { get; init; } = [];
    public IReadOnlyList<string> LegacyNames { get; init; } = [];
}

public sealed class DeviceCapabilities
{
    public bool CanToggle { get; init; }
    public bool CanReceiveCommands { get; init; }
    public bool CanEmitEvents { get; init; }
    public bool SupportsSchedule { get; init; }
    public bool SupportsRules { get; init; }
    public bool SupportsMonitoringOnly { get; init; }
}

public sealed class DeviceActionDefinition
{
    public string Code { get; init; } = string.Empty;
    public string DisplayName { get; init; } = string.Empty;
    public IReadOnlyList<string> RequiredFields { get; init; } = [];
}

public sealed class ProviderDefinition
{
    public string Code { get; init; } = string.Empty;
    public string Key => Code;
    public string DisplayName { get; init; } = string.Empty;
    public string Title => DisplayName;
    public string Protocol { get; init; } = "manual";
    public string Channel { get; init; } = "local";
    public string TestMode { get; init; } = "local";
    public bool SupportsCommands { get; init; }
    public bool SupportsEvents { get; init; }
    public IReadOnlyList<string> RequiredFields { get; init; } = [];
    public IReadOnlyList<string> OptionalFields { get; init; } = [];
    public IReadOnlyList<DeviceFormFieldDefinition> FormFields { get; init; } = [];
    public IReadOnlyList<string> LegacyKeys { get; init; } = [];
    public string Note { get; init; } = string.Empty;
}

public sealed class DeviceFormFieldDefinition
{
    public string Name { get; init; } = string.Empty;
    public string Label { get; init; } = string.Empty;
    public string Kind { get; init; } = "text";
    public bool Required { get; init; }
    public bool Secret { get; init; }
    public string Placeholder { get; init; } = string.Empty;
}

public sealed class DeviceFormSchema
{
    public string TypeCode { get; init; } = string.Empty;
    public string ProviderCode { get; init; } = string.Empty;
    public DeviceCapabilities Capabilities { get; init; } = new();
    public IReadOnlyList<DeviceFormFieldDefinition> Fields { get; init; } = [];
    public IReadOnlyList<DeviceActionDefinition> Actions { get; init; } = [];
}

public sealed class ScheduleDayDefinition
{
    public int Value { get; init; }
    public string Title { get; init; } = string.Empty;
}
