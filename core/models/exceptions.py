from core.errors import ValidationError

class ModelValidationError(ValidationError):
    """
    Raised when a domain model fails structural or semantic validation
    during instantiation or deserialization.
    """
    pass
