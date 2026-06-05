using System.Collections.Concurrent;
using System.Security.Cryptography;
using System.Text.RegularExpressions;
using CalHouse.Api.Infrastructure;
using CalHouse.Api.Models;
using Microsoft.Data.Sqlite;

namespace CalHouse.Api.Services;

public sealed class AuthStore
{
    private const int PasswordIterations = 120_000;
    private const int SaltSize = 16;
    private const int HashSize = 32;
    private static readonly TimeSpan SessionTouchInterval = TimeSpan.FromSeconds(60);
    private static readonly Regex LoginPattern = new(@"^[A-Za-z0-9._-]+$", RegexOptions.Compiled | RegexOptions.CultureInvariant);
    private readonly string _databasePath;
    private readonly object _sync = new();
    private readonly ConcurrentQueue<AuditLogItem> _auditQueue = new();
    private readonly SemaphoreSlim _auditSignal = new(0);
    private readonly CancellationTokenSource _auditCancellation = new();

    public AuthStore(IWebHostEnvironment environment)
    {
        var appDataDirectory = Path.Combine(environment.ContentRootPath, "App_Data");
        Directory.CreateDirectory(appDataDirectory);
        _databasePath = Path.Combine(appDataDirectory, "calhouse.db");

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureSchema(db);
        }

        _ = Task.Run(ProcessAuditQueueAsync);
    }

    public AuthResult Register(string login, string password, string confirmPassword)
    {
        var cleanLogin = NormalizeLogin(login);
        ValidatePassword(password);
        if (!string.Equals(password, confirmPassword, StringComparison.Ordinal))
        {
            throw new ValidationProblemException("Password confirmation does not match", "AUTH_PASSWORD_CONFIRMATION_MISMATCH");
        }

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureSchema(db);
            EnsureLoginIsUnique(db, cleanLogin);

            var now = DateTime.UtcNow;
            var role = CountUsers(db) == 0 ? "Admin" : "User";
            using var transaction = db.BeginTransaction();
            var insert = db.CreateCommand();
            insert.Transaction = transaction;
            insert.CommandText = @"
INSERT INTO Users (Login, PasswordHash, PasswordPlainText, Role, IsActive, CreatedAt, UpdatedAt)
VALUES (@login, @passwordHash, @passwordPlainText, @role, 1, @createdAt, @updatedAt);
SELECT last_insert_rowid();";
            insert.Parameters.AddWithValue("@login", cleanLogin);
            insert.Parameters.AddWithValue("@passwordHash", HashPassword(password));
            insert.Parameters.AddWithValue("@passwordPlainText", password);
            insert.Parameters.AddWithValue("@role", role);
            insert.Parameters.AddWithValue("@createdAt", now.ToString("O"));
            insert.Parameters.AddWithValue("@updatedAt", now.ToString("O"));
            var userId = Convert.ToInt32((long)(insert.ExecuteScalar() ?? 0));

            var token = CreateSession(db, transaction, userId);
            LogEvent(db, transaction, cleanLogin, "AUTH_REGISTER", $"User \"{cleanLogin}\" registered with role {role}");
            transaction.Commit();

            return new AuthResult { Token = token, Login = cleanLogin, Role = role };
        }
    }

    public AuthResult Login(string login, string password)
    {
        var cleanLogin = NormalizeLogin(login);
        ValidatePassword(password);

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureSchema(db);
            var user = ReadUserByLogin(db, cleanLogin) ?? throw new ValidationProblemException("Invalid login or password", "AUTH_INVALID_CREDENTIALS");
            if (!user.IsActive)
            {
                throw new ValidationProblemException("User is blocked", "AUTH_USER_BLOCKED");
            }

            var passwordHash = ReadPasswordHash(db, user.Id);
            if (!VerifyPassword(password, passwordHash))
            {
                throw new ValidationProblemException("Invalid login or password", "AUTH_INVALID_CREDENTIALS");
            }

            using var transaction = db.BeginTransaction();
            var token = CreateSession(db, transaction, user.Id);
            LogEvent(db, transaction, user.Login, "AUTH_LOGIN", $"User \"{user.Login}\" logged in");
            transaction.Commit();

            return new AuthResult { Token = token, Login = user.Login, Role = user.Role };
        }
    }

    public AuthenticatedUser? Authenticate(string? token)
    {
        if (string.IsNullOrWhiteSpace(token))
        {
            return null;
        }

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureSchema(db);
            var tokenHash = HashToken(token.Trim());
            var command = db.CreateCommand();
            command.CommandText = @"
SELECT u.Id, u.Login, u.Role, u.IsActive, s.LastSeenAt
FROM UserSessions s
INNER JOIN Users u ON u.Id = s.UserId
WHERE s.TokenHash = @tokenHash AND s.ExpiresAt > @now
LIMIT 1;";
            command.Parameters.AddWithValue("@tokenHash", tokenHash);
            var now = DateTime.UtcNow;
            command.Parameters.AddWithValue("@now", now.ToString("O"));
            using var reader = command.ExecuteReader();
            if (!reader.Read())
            {
                return null;
            }

            var user = new AuthenticatedUser
            {
                Id = reader.GetInt32(0),
                Login = reader.GetString(1),
                Role = reader.GetString(2),
                IsActive = reader.GetInt32(3) == 1,
            };
            var rawLastSeenAt = reader.GetString(4);
            if (!user.IsActive)
            {
                return null;
            }

            reader.Close();
            if (!DateTime.TryParse(rawLastSeenAt, null, System.Globalization.DateTimeStyles.RoundtripKind, out var lastSeenAt)
                || now - lastSeenAt.ToUniversalTime() >= SessionTouchInterval)
            {
                var touch = db.CreateCommand();
                touch.CommandText = "UPDATE UserSessions SET LastSeenAt = @lastSeenAt WHERE TokenHash = @tokenHash;";
                touch.Parameters.AddWithValue("@lastSeenAt", now.ToString("O"));
                touch.Parameters.AddWithValue("@tokenHash", tokenHash);
                touch.ExecuteNonQuery();
            }
            return user;
        }
    }

    public IReadOnlyList<AuthUserDto> GetUsers()
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureSchema(db);
            var command = db.CreateCommand();
            command.CommandText = "SELECT Id, Login, Role, IsActive, CreatedAt, UpdatedAt FROM Users ORDER BY CreatedAt, Id;";
            return ReadUsers(command);
        }
    }

    public AuthUserDto SetRole(int id, string role)
    {
        var cleanRole = NormalizeRole(role);
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureSchema(db);
            var user = ReadUserById(db, id) ?? throw new NotFoundProblemException("User not found", "USER_NOT_FOUND");
            if (string.Equals(user.Role, "Admin", StringComparison.OrdinalIgnoreCase) && cleanRole == "User" && CountActiveAdmins(db) <= 1)
            {
                throw new ValidationProblemException("Cannot demote the last active admin", "AUTH_LAST_ADMIN");
            }

            using var transaction = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "UPDATE Users SET Role = @role, UpdatedAt = @updatedAt WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@role", cleanRole);
            command.Parameters.AddWithValue("@updatedAt", DateTime.UtcNow.ToString("O"));
            command.ExecuteNonQuery();
            LogEvent(db, transaction, user.Login, "USER_ROLE_CHANGED", $"User \"{user.Login}\" role changed to {cleanRole}");
            transaction.Commit();
            return ReadUserById(db, id)!;
        }
    }

    public AuthUserDto SetActive(int id, bool isActive)
    {
        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureSchema(db);
            var user = ReadUserById(db, id) ?? throw new NotFoundProblemException("User not found", "USER_NOT_FOUND");
            if (!isActive && string.Equals(user.Role, "Admin", StringComparison.OrdinalIgnoreCase) && CountActiveAdmins(db) <= 1)
            {
                throw new ValidationProblemException("Cannot block the last active admin", "AUTH_LAST_ADMIN");
            }

            using var transaction = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "UPDATE Users SET IsActive = @isActive, UpdatedAt = @updatedAt WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@isActive", isActive ? 1 : 0);
            command.Parameters.AddWithValue("@updatedAt", DateTime.UtcNow.ToString("O"));
            command.ExecuteNonQuery();
            if (!isActive)
            {
                var revoke = db.CreateCommand();
                revoke.Transaction = transaction;
                revoke.CommandText = "DELETE FROM UserSessions WHERE UserId = @userId;";
                revoke.Parameters.AddWithValue("@userId", id);
                revoke.ExecuteNonQuery();
            }
            LogEvent(db, transaction, user.Login, isActive ? "USER_UNBLOCKED" : "USER_BLOCKED", $"User \"{user.Login}\" active={isActive}");
            transaction.Commit();
            return ReadUserById(db, id)!;
        }
    }

    public AuthUserDto ResetPassword(int id, string password, string confirmPassword, string changedByLogin)
    {
        ValidatePassword(password);
        if (!string.Equals(password, confirmPassword, StringComparison.Ordinal))
        {
            throw new ValidationProblemException("Password confirmation does not match", "AUTH_PASSWORD_CONFIRMATION_MISMATCH");
        }

        lock (_sync)
        {
            using var db = OpenConnection();
            EnsureSchema(db);
            var user = ReadUserById(db, id) ?? throw new NotFoundProblemException("User not found", "USER_NOT_FOUND");

            using var transaction = db.BeginTransaction();
            var command = db.CreateCommand();
            command.Transaction = transaction;
            command.CommandText = "UPDATE Users SET PasswordHash = @passwordHash, PasswordPlainText = @passwordPlainText, UpdatedAt = @updatedAt WHERE Id = @id;";
            command.Parameters.AddWithValue("@id", id);
            command.Parameters.AddWithValue("@passwordHash", HashPassword(password));
            command.Parameters.AddWithValue("@passwordPlainText", password);
            command.Parameters.AddWithValue("@updatedAt", DateTime.UtcNow.ToString("O"));
            command.ExecuteNonQuery();

            var revoke = db.CreateCommand();
            revoke.Transaction = transaction;
            revoke.CommandText = "DELETE FROM UserSessions WHERE UserId = @userId;";
            revoke.Parameters.AddWithValue("@userId", id);
            revoke.ExecuteNonQuery();

            LogEvent(db, transaction, changedByLogin, "USER_PASSWORD_RESET", $"Пользователь {changedByLogin} сбросил пароль пользователя \"{user.Login}\"");
            transaction.Commit();
            return ReadUserById(db, id)!;
        }
    }

    public void LogAudit(string login, string method, string path)
    {
        _auditQueue.Enqueue(new AuditLogItem(login, method, path));
        _auditSignal.Release();
    }

    private async Task ProcessAuditQueueAsync()
    {
        while (!_auditCancellation.IsCancellationRequested)
        {
            try
            {
                await _auditSignal.WaitAsync(_auditCancellation.Token);
            }
            catch (OperationCanceledException)
            {
                break;
            }

            while (_auditQueue.TryDequeue(out var item))
            {
                WriteAuditLog(item);
            }
        }
    }

    private void WriteAuditLog(AuditLogItem item)
    {
        try
        {
            lock (_sync)
            {
                using var db = OpenConnection();
                EnsureSchema(db);
                using var transaction = db.BeginTransaction();
                LogEvent(db, transaction, item.Login, "USER_API_ACTION", $"Пользователь {item.Login} выполнил действие: {DescribeApiAction(item.Method, item.Path)}");
                transaction.Commit();
            }
        }
        catch
        {
            // Audit logging must not break a successful API request.
        }
    }
    private SqliteConnection OpenConnection()
    {
        var connection = new SqliteConnection($"Data Source={_databasePath}");
        connection.Open();
        return connection;
    }

    private static void EnsureSchema(SqliteConnection connection)
    {
        var command = connection.CreateCommand();
        command.CommandText = @"
CREATE TABLE IF NOT EXISTS Users (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Login TEXT UNIQUE NOT NULL,
    PasswordHash TEXT NOT NULL,
    PasswordPlainText TEXT NULL,
    Role TEXT NOT NULL,
    IsActive INTEGER NOT NULL,
    CreatedAt TEXT NOT NULL,
    UpdatedAt TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS UserSessions (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    UserId INTEGER NOT NULL,
    TokenHash TEXT UNIQUE NOT NULL,
    CreatedAt TEXT NOT NULL,
    ExpiresAt TEXT NOT NULL,
    LastSeenAt TEXT NOT NULL,
    FOREIGN KEY(UserId) REFERENCES Users(Id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS EventLogs (
    Id INTEGER PRIMARY KEY AUTOINCREMENT,
    Ts TEXT NOT NULL,
    Severity TEXT NOT NULL,
    Source TEXT NOT NULL,
    EventType TEXT NOT NULL,
    Message TEXT NOT NULL,
    UserId TEXT NULL,
    DeviceId INTEGER NULL,
    RoomId INTEGER NULL,
    SceneId INTEGER NULL,
    RunId INTEGER NULL
);";
        command.ExecuteNonQuery();
        EnsureColumn(connection, "Users", "PasswordPlainText", "TEXT NULL");
    }

    private static void EnsureColumn(SqliteConnection connection, string tableName, string columnName, string columnDefinition)
    {
        var check = connection.CreateCommand();
        check.CommandText = $"PRAGMA table_info({tableName});";
        using (var reader = check.ExecuteReader())
        {
            while (reader.Read())
            {
                if (string.Equals(reader.GetString(1), columnName, StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }
            }
        }

        var alter = connection.CreateCommand();
        alter.CommandText = $"ALTER TABLE {tableName} ADD COLUMN {columnName} {columnDefinition};";
        alter.ExecuteNonQuery();
    }

    private static string NormalizeLogin(string login)
    {
        var clean = (login ?? string.Empty).Trim();
        if (clean.Length < 3 || clean.Length > 50)
        {
            throw new ValidationProblemException("Login must be 3-50 characters", "AUTH_LOGIN_INVALID");
        }
        if (!LoginPattern.IsMatch(clean))
        {
            throw new ValidationProblemException("Login can contain only latin letters, digits, dot, underscore and hyphen", "AUTH_LOGIN_INVALID");
        }
        return clean;
    }

    private static void ValidatePassword(string password)
    {
        if (string.IsNullOrEmpty(password) || password.Length < 6 || password.Length > 100)
        {
            throw new ValidationProblemException("Password must be 6-100 characters", "AUTH_PASSWORD_INVALID");
        }
    }

    private static string NormalizeRole(string role)
    {
        var clean = (role ?? string.Empty).Trim();
        if (string.Equals(clean, "Admin", StringComparison.OrdinalIgnoreCase))
        {
            return "Admin";
        }
        if (string.Equals(clean, "User", StringComparison.OrdinalIgnoreCase))
        {
            return "User";
        }
        throw new ValidationProblemException("Role must be Admin or User", "USER_ROLE_INVALID");
    }

    private static string HashPassword(string password)
    {
        var salt = RandomNumberGenerator.GetBytes(SaltSize);
        var hash = Rfc2898DeriveBytes.Pbkdf2(password, salt, PasswordIterations, HashAlgorithmName.SHA256, HashSize);
        return $"pbkdf2-sha256:{PasswordIterations}:{Base64Url(salt)}:{Base64Url(hash)}";
    }

    private static bool VerifyPassword(string password, string storedHash)
    {
        var parts = storedHash.Split(':');
        if (parts.Length != 4 || parts[0] != "pbkdf2-sha256" || !int.TryParse(parts[1], out var iterations))
        {
            return false;
        }

        var salt = Base64UrlDecode(parts[2]);
        var expected = Base64UrlDecode(parts[3]);
        var actual = Rfc2898DeriveBytes.Pbkdf2(password, salt, iterations, HashAlgorithmName.SHA256, expected.Length);
        return CryptographicOperations.FixedTimeEquals(actual, expected);
    }

    private static string CreateRawToken()
    {
        return Base64Url(RandomNumberGenerator.GetBytes(32));
    }

    private static string HashToken(string token)
    {
        return Convert.ToHexString(SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(token)));
    }

    private static string Base64Url(byte[] bytes)
    {
        return Convert.ToBase64String(bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_');
    }

    private static byte[] Base64UrlDecode(string value)
    {
        var padded = value.Replace('-', '+').Replace('_', '/');
        padded = padded.PadRight(padded.Length + (4 - padded.Length % 4) % 4, '=');
        return Convert.FromBase64String(padded);
    }

    private static int CountUsers(SqliteConnection connection)
    {
        var command = connection.CreateCommand();
        command.CommandText = "SELECT COUNT(*) FROM Users;";
        return Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));
    }

    private static int CountActiveAdmins(SqliteConnection connection)
    {
        var command = connection.CreateCommand();
        command.CommandText = "SELECT COUNT(*) FROM Users WHERE Role = 'Admin' AND IsActive = 1;";
        return Convert.ToInt32((long)(command.ExecuteScalar() ?? 0));
    }

    private static void EnsureLoginIsUnique(SqliteConnection connection, string login)
    {
        var command = connection.CreateCommand();
        command.CommandText = "SELECT Id FROM Users WHERE lower(Login) = lower(@login) LIMIT 1;";
        command.Parameters.AddWithValue("@login", login);
        if (command.ExecuteScalar() is not null)
        {
            throw new ConflictProblemException("Login already exists", "AUTH_LOGIN_EXISTS");
        }
    }

    private static string CreateSession(SqliteConnection connection, SqliteTransaction transaction, int userId)
    {
        var now = DateTime.UtcNow;
        var token = CreateRawToken();
        var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = @"
INSERT INTO UserSessions (UserId, TokenHash, CreatedAt, ExpiresAt, LastSeenAt)
VALUES (@userId, @tokenHash, @createdAt, @expiresAt, @lastSeenAt);";
        command.Parameters.AddWithValue("@userId", userId);
        command.Parameters.AddWithValue("@tokenHash", HashToken(token));
        command.Parameters.AddWithValue("@createdAt", now.ToString("O"));
        command.Parameters.AddWithValue("@expiresAt", now.AddDays(30).ToString("O"));
        command.Parameters.AddWithValue("@lastSeenAt", now.ToString("O"));
        command.ExecuteNonQuery();
        return token;
    }

    private static AuthUserDto? ReadUserByLogin(SqliteConnection connection, string login)
    {
        var command = connection.CreateCommand();
        command.CommandText = "SELECT Id, Login, Role, IsActive, CreatedAt, UpdatedAt FROM Users WHERE lower(Login) = lower(@login) LIMIT 1;";
        command.Parameters.AddWithValue("@login", login);
        return ReadUsers(command).FirstOrDefault();
    }

    private static AuthUserDto? ReadUserById(SqliteConnection connection, int id)
    {
        var command = connection.CreateCommand();
        command.CommandText = "SELECT Id, Login, Role, IsActive, CreatedAt, UpdatedAt FROM Users WHERE Id = @id LIMIT 1;";
        command.Parameters.AddWithValue("@id", id);
        return ReadUsers(command).FirstOrDefault();
    }

    private static string ReadPasswordHash(SqliteConnection connection, int userId)
    {
        var command = connection.CreateCommand();
        command.CommandText = "SELECT PasswordHash FROM Users WHERE Id = @id LIMIT 1;";
        command.Parameters.AddWithValue("@id", userId);
        return Convert.ToString(command.ExecuteScalar()) ?? string.Empty;
    }

    private static List<AuthUserDto> ReadUsers(SqliteCommand command)
    {
        var users = new List<AuthUserDto>();
        using var reader = command.ExecuteReader();
        while (reader.Read())
        {
            users.Add(new AuthUserDto
            {
                Id = reader.GetInt32(0),
                Login = reader.GetString(1),
                Role = reader.GetString(2),
                IsActive = reader.GetInt32(3) == 1,
                CreatedAt = DateTime.Parse(reader.GetString(4), null, System.Globalization.DateTimeStyles.RoundtripKind),
                UpdatedAt = DateTime.Parse(reader.GetString(5), null, System.Globalization.DateTimeStyles.RoundtripKind),
            });
        }
        return users;
    }

    private static void LogEvent(SqliteConnection connection, SqliteTransaction transaction, string login, string eventType, string message)
    {
        var command = connection.CreateCommand();
        command.Transaction = transaction;
        command.CommandText = @"
INSERT INTO EventLogs (Ts, Severity, Source, EventType, Message, UserId, DeviceId, RoomId, SceneId, RunId)
VALUES (@ts, @severity, @source, @eventType, @message, @userId, NULL, NULL, NULL, NULL);";
        command.Parameters.AddWithValue("@ts", DateTime.UtcNow.ToString("O"));
        command.Parameters.AddWithValue("@severity", "info");
        command.Parameters.AddWithValue("@source", "auth");
        command.Parameters.AddWithValue("@eventType", eventType);
        command.Parameters.AddWithValue("@message", message);
        command.Parameters.AddWithValue("@userId", login);
        command.ExecuteNonQuery();
    }

    private sealed record AuditLogItem(string Login, string Method, string Path);

    private static string DescribeApiAction(string method, string path)
    {
        var upperMethod = method.ToUpperInvariant();
        if (upperMethod == "PUT" && Regex.IsMatch(path, "^/api/devices/[0-9]+/toggle$", RegexOptions.IgnoreCase))
        {
            return $"переключение устройства ({path})";
        }
        if (upperMethod == "POST" && Regex.IsMatch(path, "^/api/scenes/[0-9]+/run$", RegexOptions.IgnoreCase))
        {
            return $"запуск сценария ({path})";
        }
        if (upperMethod == "POST" && string.Equals(path, "/api/events", StringComparison.OrdinalIgnoreCase))
        {
            return "отправка события";
        }
        if (path.StartsWith("/api/users", StringComparison.OrdinalIgnoreCase))
        {
            return $"управление пользователями ({upperMethod} {path})";
        }
        return $"{upperMethod} {path}";
    }
}

