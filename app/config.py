import yaml
import os
from pathlib import Path


class Config:
    """Configuration loader from YAML file."""

    _instance = None
    _config = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if Config._config is None:
            self._load_config()

    def _load_config(self):
        """Load configuration from YAML file."""
        config_path = Path(__file__).parent.parent / 'config-webapp.yaml'

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path, 'r') as file:
            Config._config = yaml.safe_load(file)

    def get_env(self) -> str:
        """Get current environment from ENV variable or default to development."""
        return os.environ.get('APP_ENV', 'development')

    def get_database_config(self) -> dict:
        """Get database configuration for current environment."""
        env = self.get_env()
        return Config._config[env]['database']

    def get_connection_string(self) -> str:
        """Get SQLAlchemy connection string."""
        db = self.get_database_config()
        return f"mysql+pymysql://{db['username']}:{db['password']}@{db['host']}:{db['port']}/{db['database']}"


# Global config instance
config = Config()
