namespace CalHouse.Api.Models;

public sealed class AuthenticatedUser
{
    public int Id { get; set; }
    public string Login { get; set; } = string.Empty;
    public string Role { get; set; } = "User";
    public bool IsActive { get; set; }
}

public sealed class AuthUserDto
{
    public int Id { get; set; }
    public string Login { get; set; } = string.Empty;
    public string Role { get; set; } = "User";
    public bool IsActive { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
}

public sealed class AuthResult
{
    public string Token { get; set; } = string.Empty;
    public string Login { get; set; } = string.Empty;
    public string Role { get; set; } = "User";
}
