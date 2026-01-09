APP_NAME = "El Sol Azteca - Analytics Platform"

APP_ICON = "/static/assets/images/isotipo-preferente-color_negativo.PNG"

SQLLAB_ASYNC_TIME_LIMIT_SEC = 60 * 60 * 6 # 6 hours
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
  "ALLOW_ADHOC_SUBQUERY": True
}

# 1. Enable embedding feature flag
  FEATURE_FLAGS = {
      "ALLOW_ADHOC_SUBQUERY": True,
      "EMBEDDED_SUPERSET": True,           # Required for embedding
      "EMBEDDABLE_CHARTS": True,           # Enable chart embedding
  }

  # 2. Guest token for unauthenticated access (optional but recommended)
  GUEST_ROLE_NAME = "Public"
  GUEST_TOKEN_JWT_SECRET = "your-secret-key-here"  # Change this!
  GUEST_TOKEN_JWT_ALGO = "HS256"
  GUEST_TOKEN_HEADER_NAME = "X-GuestToken"
  GUEST_TOKEN_JWT_EXP_SECONDS = 300  # 5 minutes

  # 3. CORS settings (if webapp on different port/domain)
  ENABLE_CORS = True
  CORS_OPTIONS = {
      "supports_credentials": True,
      "allow_headers": ["*"],
      "resources": ["*"],
      "origins": ["http://localhost:9090", "http://localhost:8099"],  # Your webapp URLs
  }

  # Already in your config (good):
  TALISMAN_ENABLED = False
  HTTP_HEADERS = {'X-Frame-Options': 'ALLOWALL'}