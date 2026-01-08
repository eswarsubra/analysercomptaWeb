#!/usr/bin/env python3
"""
AnalyzerComptaWeb - Supplier Management Web Application
Main entry point
"""

# Initialize logging first
from app.logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)

from nicegui import ui, app

# Import all pages to register routes
from app.pages import (
    dashboard_page,
    suppliers_page,
    products_page,
    factures_page,
    review_page,
    transactions_page
)

# Configure app
app.native.window_args['resizable'] = True
app.native.start_args['debug'] = False
app.add_static_files('/static', 'app')


def main():
    """Run the application."""
    import os
    # Use port 8099 for production, 9090 for development
    port = 8099 if os.environ.get('APP_ENV') == 'production' else 9090
    show_browser = os.environ.get('APP_ENV') != 'production'

    logger.info(f"Starting AnalyzerComptaWeb on port {port}")
    ui.run(
        title='AnalyzerCompta - Supplier Management',
        favicon='app/isotipo-preferente-color_positivo.png',
        dark=None,  # Auto-detect system preference
        port=port,
        reload=False,  # Disabled for now
        show=show_browser,  # Don't open browser in production
    )


if __name__ in {'__main__', '__mp_main__'}:
    main()
