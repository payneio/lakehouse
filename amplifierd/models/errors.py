"""Error models for amplifierd API.

Pydantic models for error responses.
"""

from pydantic import Field

from amplifierd.models.base import CamelCaseModel


class ValidationErrorDetail(CamelCaseModel):
    """Detail about a validation error.

    Attributes:
        loc: Location of the error (field path)
        msg: Error message
        type: Error type
    """

    loc: list[str] = Field(..., description="Location of the error")
    msg: str = Field(..., description="Error message")
    type: str = Field(..., description="Error type")


class ErrorResponse(CamelCaseModel):
    """Standard error response.

    Attributes:
        error: Error message
        detail: Optional additional details
        validation_errors: Optional validation error details
    """

    error: str = Field(..., description="Error message")
    detail: str | None = Field(default=None, description="Additional error details")
    validation_errors: list[ValidationErrorDetail] | None = Field(default=None, description="Validation error details")
