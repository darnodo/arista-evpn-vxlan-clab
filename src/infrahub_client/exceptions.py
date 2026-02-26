"""Exception hierarchy for the Infrahub fabric intent client."""


class InfrahubClientError(Exception):
    """Base exception for all Infrahub client errors."""


class InfrahubConnectionError(InfrahubClientError):
    """Raised when the client cannot connect to the Infrahub server."""


class InfrahubQueryError(InfrahubClientError):
    """Raised when a query to the Infrahub server fails."""


class InfrahubNotFoundError(InfrahubClientError):
    """Raised when a requested resource is not found in Infrahub."""
