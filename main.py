#!/usr/bin/env python3
"""
AnalyzerComptaWeb - Supplier Management Web Application
Main entry point
"""

# Initialize logging first
from app.logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)

# Initialize Core's ConfigLoader so Core services (ArchiveService, etc.) work
import os
from pathlib import Path
from analysercomptacore.config import ConfigLoader
_env = os.environ.get('APP_ENV', 'development')
_config_path = str(Path(__file__).parent / 'config-webapp.yaml')
ConfigLoader.load(_config_path, _env)
logger.info(f"Core ConfigLoader initialized (env={_env})")

from nicegui import ui, app

# Import all pages to register routes
from app.pages import (
    dashboard_page,
    suppliers_page,
    products_page,
    factures_page,
    review_page,
    transactions_page,
    explore_transactions_page,
    reconciliation_page,
    outbound_page,
)

# Configure app
app.native.window_args['resizable'] = True
app.native.start_args['debug'] = False
app.add_static_files('/static', 'app')

# Register mobile scan API routes (FastAPI endpoints on same server)
from app.api.mobile_scan import register_mobile_scan_routes
register_mobile_scan_routes()


def main():
    """Run the application."""
    # Use port 8099 for production, 9090 for development
    port = 8099 if os.environ.get('APP_ENV') == 'production' else 9090
    show_browser = os.environ.get('APP_ENV') != 'production'

    logger.info(f"Starting AnalyzerComptaWeb on port {port}")
    ui.run(
        title='AnalyzerCompta - Supplier Management',
        favicon='app/isotipo-preferente-color_positivo.png',
        dark=None,  # Auto-detect system preference
        host='0.0.0.0',  # Bind to all interfaces (needed for phone/LAN access)
        port=port,
        reload=False,  # Disabled for now
        show=show_browser,  # Don't open browser in production
        storage_secret='analyzercompta-web-storage-secret',
    )


if __name__ in {'__main__', '__mp_main__'}:
    main()
