"""Constants for the eToll România (TollRo) integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "etoll_ro"
MANUFACTURER: Final = "CNAIR – eToll România"

# Portal / API
PORTAL_URL: Final = "https://portal.etoll.ro"
API_BASE: Final = "https://portal.etoll.ro/api"

# Keycloak (realm "external", public client with PKCE – same as the web portal)
SSO_REALM_URL: Final = "https://sso.etoll.ro/auth/realms/external"
AUTH_URL: Final = f"{SSO_REALM_URL}/protocol/openid-connect/auth"
TOKEN_URL: Final = f"{SSO_REALM_URL}/protocol/openid-connect/token"
CLIENT_ID: Final = "ddcm-authz-client"
REDIRECT_URI: Final = "https://portal.etoll.ro/portal-extern/authentication/login-callback"
SCOPE: Final = "openid profile"

CONF_SCAN_INTERVAL: Final = "scan_interval"
DEFAULT_SCAN_INTERVAL_MIN: Final = 30
MIN_SCAN_INTERVAL_MIN: Final = 10
MAX_SCAN_INTERVAL_MIN: Final = 720

DEFAULT_SCAN_INTERVAL: Final = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MIN)

# Toll (service) types used by the portal
TOLL_TYPE_VIGNETTE: Final = "VIGNETTE"
TOLL_TYPE_PEAJ: Final = "PEAJ"  # TollRo credits (prepaid wallet)
TOLL_TYPE_ROUTE: Final = "ROUTE_TICKET"
TOLL_TYPE_BRIDGE: Final = "BRIDGE"

# Public status page (Cachet 3) – times are Europe/Bucharest local time
STATUS_API_BASE: Final = "https://portal.etoll.ro/status/api"
STATUS_TZ: Final = "Europe/Bucharest"
STATUS_PAGE_URL: Final = "https://portal.etoll.ro/status/"

EVENT_NOTIFICATION: Final = f"{DOMAIN}_notification"

# Notification types seen in the portal application
NOTIFICATION_TYPES: Final = [
    "VIGNETTE_WILL_EXPIRE",
    "VIGNETTE_EXPIRED",
    "LOW_BALANCE",
    "ROUTE_TICKET_WILL_EXPIRE",
    "ROUTE_TICKET_EXPIRED",
    "ALTERED_ROUTE",
    "BRIDGE_WILL_EXPIRE",
    "BRIDGE_EXPIRED",
    "BRIDGE_CROSSING_CONSUMED",
    "BRIDGE_CROSSING_MISSING_TOLL",
    "SESSION_STOP_EXPIRED",
    "SESSION_STOP_INACTIVE",
    "SESSION_STOP_INSUFFICIENT_BALANCE",
    "SESSION_LOCATION_MISSING_WARNING",
    "SESSION_STOPPED_NO_LOCATION",
    "PENDING_SHARED_BALANCE",
    "ACCEPTED_SHARED_BALANCE",
    "DECLINED_SHARED_BALANCE",
    "CANCELLED_SHARED_BALANCE",
    "OTHER",
]
