from nicegui import ui
from app.components.layout import layout
from app.services import SupplierService, ProductService, FactureService, NewProductsService


@ui.page('/')
def dashboard_page():
    """Dashboard page with summary statistics."""

    def load_data():
        suppliers = SupplierService.get_all()
        products = ProductService.get_all()
        facture_summary = FactureService.get_summary()
        recent_factures = FactureService.get_recent(5)
        pending_count = NewProductsService.get_pending_count()
        status_counts = NewProductsService.get_status_counts()
        return suppliers, products, facture_summary, recent_factures, pending_count, status_counts

    with layout('Dashboard'):
        suppliers, products, facture_summary, recent_factures, pending_count, status_counts = load_data()

        # Summary cards row
        with ui.row().classes('w-full gap-4 flex-wrap'):
            _stat_card('Suppliers', len(suppliers), 'business', 'blue', '/suppliers')
            _stat_card('Products', len(products), 'inventory', 'green', '/products')
            _stat_card('Factures', facture_summary['count'], 'receipt_long', 'purple', '/factures')
            _stat_card('Pending Review', pending_count, 'rate_review', 'amber', '/review')

        ui.separator().classes('my-6')

        # Two column layout
        with ui.row().classes('w-full gap-6'):
            # Recent factures
            with ui.card().classes('flex-1'):
                ui.label('Recent Factures').classes('text-lg font-semibold mb-4')
                if recent_factures:
                    columns = [
                        {'name': 'factNum', 'label': 'Number', 'field': 'factNum', 'align': 'left'},
                        {'name': 'supplier_name', 'label': 'Supplier', 'field': 'supplier_name', 'align': 'left'},
                        {'name': 'factDate', 'label': 'Date', 'field': 'factDate', 'align': 'left'},
                        {'name': 'factmontantttc', 'label': 'TTC', 'field': 'factmontantttc', 'align': 'right'},
                    ]
                    ui.table(columns=columns, rows=recent_factures).classes('w-full')
                else:
                    ui.label('No factures found').classes('text-gray-500')

            # Status breakdown
            with ui.card().classes('w-80'):
                ui.label('Review Status Breakdown').classes('text-lg font-semibold mb-4')
                if status_counts:
                    for status, count in status_counts.items():
                        with ui.row().classes('w-full justify-between items-center py-1'):
                            _status_label(status)
                            ui.badge(str(count)).props('color=grey')
                else:
                    ui.label('No pending items').classes('text-gray-500')

        ui.separator().classes('my-6')

        # Totals summary
        with ui.card().classes('w-full'):
            ui.label('Factures Summary').classes('text-lg font-semibold mb-4')
            with ui.row().classes('gap-8'):
                with ui.column():
                    ui.label('Total HT').classes('text-sm text-gray-500')
                    ui.label(f"{facture_summary['total_ht']:,.2f} EUR").classes('text-xl font-bold text-blue-600')
                with ui.column():
                    ui.label('Total TVA').classes('text-sm text-gray-500')
                    ui.label(f"{facture_summary['total_tva']:,.2f} EUR").classes('text-xl font-bold text-amber-600')
                with ui.column():
                    ui.label('Total TTC').classes('text-sm text-gray-500')
                    ui.label(f"{facture_summary['total_ttc']:,.2f} EUR").classes('text-xl font-bold text-green-600')


def _stat_card(title: str, value: int, icon: str, color: str, link: str):
    """Create a statistics card."""
    with ui.card().classes(f'cursor-pointer hover:shadow-lg transition-shadow').on('click', lambda: ui.navigate.to(link)):
        with ui.row().classes('items-center gap-4 p-2'):
            ui.icon(icon, size='lg').classes(f'text-{color}-500')
            with ui.column().classes('gap-0'):
                ui.label(str(value)).classes('text-2xl font-bold')
                ui.label(title).classes('text-sm text-gray-500')


def _status_label(status: str):
    """Create a status label with color."""
    colors = {
        'CLOSED': 'green',
        'CREATE PRODUCT': 'blue',
        'IGNORE PRODUCT': 'amber',
        'FULL IGNORE': 'red',
        'OBSOLETE': 'gray',
        'INCOMPLETE': 'pink'
    }
    color = colors.get(status, 'gray')
    ui.label(status).classes(f'text-{color}-600 text-sm')
