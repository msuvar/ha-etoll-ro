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
