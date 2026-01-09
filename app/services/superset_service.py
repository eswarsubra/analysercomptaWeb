"""Service for Superset API integration and guest token generation."""
import requests
from app.logging_config import get_logger
from app.config import config

logger = get_logger(__name__)

# Superset configuration from YAML
_superset_config = config.get_superset_config()
SUPERSET_URL = _superset_config['url']
SUPERSET_USERNAME = _superset_config['username']
SUPERSET_PASSWORD = _superset_config['password']


class SupersetService:
    """Service for interacting with Superset API."""

    _session: requests.Session | None = None
    _access_token: str | None = None
    _csrf_token: str | None = None

    @classmethod
    def _get_session(cls) -> requests.Session:
        """Get or create a requests session."""
        if cls._session is None:
            cls._session = requests.Session()
        return cls._session

    @classmethod
    def _get_access_token(cls) -> str:
        """Get access token from Superset API."""
        if cls._access_token:
            return cls._access_token

        session = cls._get_session()
        login_url = f'{SUPERSET_URL}/api/v1/security/login'
        payload = {
            'username': SUPERSET_USERNAME,
            'password': SUPERSET_PASSWORD,
            'provider': 'db',
            'refresh': True,
        }

        try:
            response = session.post(login_url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            cls._access_token = data['access_token']
            session.headers['Authorization'] = f'Bearer {cls._access_token}'
            logger.info('Superset access token obtained')
            return cls._access_token
        except requests.RequestException as e:
            logger.error(f'Failed to get Superset access token: {e}')
            raise

    @classmethod
    def _get_csrf_token(cls) -> str:
        """Get CSRF token from Superset API."""
        if cls._csrf_token:
            return cls._csrf_token

        cls._get_access_token()  # Ensure we have access token
        session = cls._get_session()
        csrf_url = f'{SUPERSET_URL}/api/v1/security/csrf_token/'

        try:
            response = session.get(csrf_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            cls._csrf_token = data['result']
            session.headers['X-CSRFToken'] = cls._csrf_token
            logger.info('Superset CSRF token obtained')
            return cls._csrf_token
        except requests.RequestException as e:
            logger.error(f'Failed to get Superset CSRF token: {e}')
            raise

    @classmethod
    def get_guest_token(cls, dashboard_id: str, user: dict | None = None) -> str:
        """
        Get a guest token for embedding a dashboard.

        Args:
            dashboard_id: The UUID of the dashboard to embed
            user: Optional user info dict with 'username' and 'first_name'

        Returns:
            Guest token string for embedding
        """
        cls._get_access_token()  # Ensure we have access token
        cls._get_csrf_token()  # Ensure we have CSRF token
        session = cls._get_session()

        guest_token_url = f'{SUPERSET_URL}/api/v1/security/guest_token/'

        # Default user if not provided
        if user is None:
            user = {'username': 'guest', 'first_name': 'Guest', 'last_name': 'User'}

        payload = {
            'user': user,
            'resources': [
                {'type': 'dashboard', 'id': dashboard_id}
            ],
            'rls': [],  # Row-level security rules (empty for full access)
        }

        try:
            response = session.post(guest_token_url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            logger.info(f'Guest token generated for dashboard {dashboard_id}')
            return data['token']
        except requests.RequestException as e:
            logger.error(f'Failed to get Superset guest token: {e}')
            raise

    @classmethod
    def get_dashboard_uuid(cls, dashboard_slug: str) -> str | None:
        """
        Get the embedded UUID of a dashboard by its slug.

        Args:
            dashboard_slug: The slug/name of the dashboard

        Returns:
            Dashboard embedded UUID or None if not found
        """
        cls._get_access_token()  # Ensure we have access token
        session = cls._get_session()

        try:
            # Get all dashboards and find by slug
            dashboard_url = f'{SUPERSET_URL}/api/v1/dashboard/'
            response = session.get(dashboard_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Find dashboard by slug
            dashboard_id = None
            for dashboard in data.get('result', []):
                if dashboard.get('slug') == dashboard_slug:
                    dashboard_id = dashboard['id']
                    break

            if not dashboard_id:
                logger.warning(f'Dashboard with slug "{dashboard_slug}" not found')
                return None

            # Get the embedded UUID from the embedded endpoint
            embedded_url = f'{SUPERSET_URL}/api/v1/dashboard/{dashboard_id}/embedded'
            response = session.get(embedded_url, timeout=10)

            if response.status_code == 404:
                logger.warning(f'Dashboard "{dashboard_slug}" does not have embedding enabled')
                return None

            response.raise_for_status()
            embedded_data = response.json()

            uuid = embedded_data['result'].get('uuid')
            logger.info(f'Found dashboard "{dashboard_slug}" with embedded UUID: {uuid}')
            return uuid
        except requests.RequestException as e:
            logger.error(f'Failed to get dashboard UUID: {e}')
            return None

    @classmethod
    def clear_tokens(cls):
        """Clear cached tokens and session (useful if they expire)."""
        cls._access_token = None
        cls._csrf_token = None
        cls._session = None
