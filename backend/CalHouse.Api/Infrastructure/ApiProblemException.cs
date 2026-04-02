namespace CalHouse.Api.Infrastructure;

public class ApiProblemException : Exception
{
    public ApiProblemException(string message, string code, int statusCode) : base(message)
    {
        Code = code;
        StatusCode = statusCode;
    }

    public string Code { get; }
    public int StatusCode { get; }
}

public sealed class ValidationProblemException : ApiProblemException
{
    public ValidationProblemException(string message, string code = "VALIDATION_ERROR")
        : base(message, code, StatusCodes.Status400BadRequest)
    {
    }
}

public sealed class NotFoundProblemException : ApiProblemException
{
    public NotFoundProblemException(string message, string code = "NOT_FOUND")
        : base(message, code, StatusCodes.Status404NotFound)
    {
    }
}

public sealed class ConflictProblemException : ApiProblemException
{
    public ConflictProblemException(string message, string code = "CONFLICT")
        : base(message, code, StatusCodes.Status409Conflict)
    {
    }
}
