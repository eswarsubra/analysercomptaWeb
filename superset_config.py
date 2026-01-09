APP_NAME = "El Sol Azteca - Analytics Platform"

APP_ICON = "/static/assets/images/isotipo-preferente-color_negativo.PNG"

SQLLAB_ASYNC_TIME_LIMIT_SEC = 60 * 60 * 6  # 6 hours
SUPERSET_WEBSERVER_TIMEOUT = 3600
ROW_LIMIT = 50000000
VIZ_ROW_LIMIT = 50000000
SAMPLES_ROW_LIMIT = 50000000
FILTER_SELECT_ROW_LIMIT = 50000000
QUERY_SEARCH_LIMIT = 50000000
SQL_MAX_ROW = 500000000
DISPLAY_MAX_ROW = 50000000
DEFAULT_SQLLAB_LIMIT = 50000000

FEATURE_FLAGS = {
    "ALLOW_ADHOC_SUBQUERY": True,
    "EMBEDDED_SUPERSET": True,
    "EMBEDDABLE_CHARTS": True,
}

# Guest token configuration for secure embedding
GUEST_ROLE_NAME = "Gamma"
GUEST_TOKEN_JWT_SECRET = "azteca-superset-embed-secret-2026"
GUEST_TOKEN_JWT_ALGO = "HS256"
GUEST_TOKEN_JWT_EXP_SECONDS = 3600  # 1 hour

# Disable Talisman security headers for embedding
TALISMAN_ENABLED = False

# Allow framing from any origin
HTTP_HEADERS = {"X-Frame-Options": "ALLOWALL"}
