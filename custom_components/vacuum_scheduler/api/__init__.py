"""
API package for vacuum_scheduler.

Architecture:
    Three-layer data flow: Entities → Coordinator → API Client.
    Only the coordinator should call the API client. Entities must never
    import or call the API client directly.

Exception hierarchy:
    VacuumSchedulerApiClientError (base)
    ├── VacuumSchedulerApiClientCommunicationError (network/timeout)
    └── VacuumSchedulerApiClientAuthenticationError (401/403)

Coordinator exception mapping:
    ApiClientAuthenticationError → ConfigEntryAuthFailed (triggers reauth)
    ApiClientCommunicationError → UpdateFailed (auto-retry)
    ApiClientError             → UpdateFailed (auto-retry)
"""

from .client import (
    VacuumSchedulerApiClient,
    VacuumSchedulerApiClientAuthenticationError,
    VacuumSchedulerApiClientCommunicationError,
    VacuumSchedulerApiClientError,
)

__all__ = [
    "VacuumSchedulerApiClient",
    "VacuumSchedulerApiClientAuthenticationError",
    "VacuumSchedulerApiClientCommunicationError",
    "VacuumSchedulerApiClientError",
]
