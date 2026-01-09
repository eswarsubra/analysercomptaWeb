from nicegui import ui
from app.components.layout import layout
from app.services import SupersetService
from app.logging_config import get_logger

logger = get_logger(__name__)

# Superset configuration
SUPERSET_URL = 'http://localhost:8088'
SUPERSET_DASHBOARD_SLUG = 'monthlydash'


@ui.page('/')
def dashboard_page():
    """Dashboard page with embedded Superset dashboard."""

    def get_superset_embed_config() -> dict | None:
        """Get Superset embedding configuration with guest token."""
        try:
            # Get dashboard UUID from slug
            dashboard_uuid = SupersetService.get_dashboard_uuid(SUPERSET_DASHBOARD_SLUG)
            if not dashboard_uuid:
                logger.error(f'Dashboard not found: {SUPERSET_DASHBOARD_SLUG}')
                return None

            # Get guest token
            guest_token = SupersetService.get_guest_token(dashboard_uuid)
            return {
                'uuid': dashboard_uuid,
                'token': guest_token,
            }
        except Exception as e:
            logger.error(f'Failed to get Superset embed config: {e}')
            return None

    with layout('Dashboard'):
        # Embedded Superset Dashboard
        with ui.card().classes('w-full h-full').style('min-height: calc(100vh - 180px)'):
            with ui.row().classes('w-full items-center justify-between mb-2'):
                ui.label('Monthly Dashboard').classes('text-lg font-semibold')
                ui.link(
                    'Open in Superset',
                    f'{SUPERSET_URL}/superset/dashboard/{SUPERSET_DASHBOARD_SLUG}/',
                    new_tab=True
                ).classes('text-sm text-blue-600')

            # Container for embedded dashboard - fills remaining space
            embed_container = ui.element('div').props('id="superset-embed-container"').classes(
                'w-full rounded-lg bg-gray-100'
            ).style('height: calc(100vh - 230px); min-height: 400px')

            # Get embed config
            embed_config = get_superset_embed_config()

            if embed_config:
                # Load Superset Embedded SDK from jsdelivr
                ui.add_head_html('''
                    <script src="https://cdn.jsdelivr.net/npm/@superset-ui/embedded-sdk@0.1.0-alpha.10/bundle/index.min.js"></script>
                ''')

                # Container for the embedded dashboard
                with embed_container:
                    pass  # SDK will mount here

                ui.run_javascript(f'''
                    (async function() {{
                        // Wait for SDK and container
                        await new Promise(r => setTimeout(r, 500));

                        const container = document.getElementById('superset-embed-container');
                        console.log('Container found:', !!container);
                        console.log('SDK loaded:', !!window.supersetEmbeddedSdk);

                        if (!container || !window.supersetEmbeddedSdk) {{
                            console.error('Missing container or SDK');
                            container.innerHTML = '<p style="color:red;padding:20px;">Failed to load Superset SDK</p>';
                            return;
                        }}

                        try {{
                            await window.supersetEmbeddedSdk.embedDashboard({{
                                id: "{embed_config['uuid']}",
                                supersetDomain: "{SUPERSET_URL}",
                                mountPoint: container,
                                fetchGuestToken: () => "{embed_config['token']}",
                                dashboardUiConfig: {{
                                    hideTitle: true,
                                    hideChartControls: false,
                                    hideTab: true,
                                    filters: {{ visible: true, expanded: false }}
                                }},
                            }});
                            console.log('Dashboard embedded successfully');

                            // Style the iframe to fill container
                            const iframe = container.querySelector('iframe');
                            if (iframe) {{
                                iframe.style.width = '100%';
                                iframe.style.height = '100%';
                                iframe.style.border = 'none';
                            }}
                        }} catch (err) {{
                            console.error('Embed error:', err);
                            container.innerHTML = '<p style="color:red;padding:20px;">Error: ' + err.message + '</p>';
                        }}
                    }})();
                ''')
            else:
                with embed_container:
                    ui.label('Failed to load dashboard. Check Superset connection.').classes(
                        'text-red-500 p-4'
                    )
