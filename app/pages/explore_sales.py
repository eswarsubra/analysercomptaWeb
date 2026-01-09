from nicegui import ui
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from app.components.layout import layout
from app.services import SalesService


@ui.page('/sales/explore')
def explore_sales_page():
    """Explore Sales page - interactive exploration with payments and product summary."""

    # Get previous month as default date range
    today = date.today()
    first_of_current_month = today.replace(day=1)
    last_month_end = first_of_current_month - relativedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    # Page-level state
    state = {
        'date_from': last_month_start,
        'date_to': last_month_end,
        'payments_data': [],
        'products_data': [],
        'selected_date': None,
    }

    # UI references
    refs = {
        'payments_table': None,
        'products_table': None,
        'selection_label': None,
        'status_label': None,
    }

    def update_status(message: str):
        """Update status label."""
        if refs['status_label']:
            refs['status_label'].set_text(message)

    def update_selection_label():
        """Update the selection indicator."""
        if refs['selection_label']:
            if state['selected_date']:
                refs['selection_label'].set_text(f"Filtered: {state['selected_date']}")
                refs['selection_label'].classes(remove='text-gray-500', add='text-blue-600 font-semibold')
            else:
                refs['selection_label'].set_text('Showing all products for period')
                refs['selection_label'].classes(remove='text-blue-600 font-semibold', add='text-gray-500')

    def load_data():
        """Load data for selected date range."""
        date_from = state['date_from']
        date_to = state['date_to']

        # Fetch payments from database
        update_status('Loading payments...')
        state['payments_data'] = SalesService.get_payments_for_date_range(date_from, date_to)

        # Fetch product summary (all for period initially)
        state['products_data'] = SalesService.get_product_sales_summary(date_from, date_to)
        update_status(f"Loaded {len(state['payments_data'])} payment days, {len(state['products_data'])} products")

        # Reset selection
        state['selected_date'] = None

        # Update tables
        update_payments_table()
        update_products_table()
        update_selection_label()

    def update_payments_table():
        """Update payments table with current data."""
        if refs['payments_table']:
            refs['payments_table'].update_rows(state['payments_data'])

    def update_products_table():
        """Update products table with current data."""
        if refs['products_table']:
            refs['products_table'].update_rows(state['products_data'])

    def on_payment_click(e):
        """Handle click on payment row to filter products by date."""
        if not e.args:
            return

        row = e.args.get('row') if isinstance(e.args, dict) else e.args[1]
        clicked_date_str = row.get('startDate')

        if not clicked_date_str:
            return

        # Parse the date string
        clicked_date = datetime.strptime(clicked_date_str, '%Y-%m-%d').date()

        # Toggle selection
        if state['selected_date'] == clicked_date:
            # Deselect - show all products for period
            state['selected_date'] = None
            state['products_data'] = SalesService.get_product_sales_summary(
                state['date_from'], state['date_to']
            )
        else:
            # Select - filter by specific date
            state['selected_date'] = clicked_date
            state['products_data'] = SalesService.get_product_sales_summary(
                state['date_from'], state['date_to'], target_date=clicked_date
            )

        update_products_table()
        update_selection_label()

    def on_date_from_change(e):
        """Handle date from change."""
        if e.value:
            state['date_from'] = datetime.strptime(e.value, '%Y-%m-%d').date()

    def on_date_to_change(e):
        """Handle date to change."""
        if e.value:
            state['date_to'] = datetime.strptime(e.value, '%Y-%m-%d').date()

    with layout('Explore Sales'):
        # Filter controls
        with ui.card().classes('w-full mb-4'):
            with ui.row().classes('w-full items-end gap-4'):
                ui.input(
                    label='From',
                    value=last_month_start.strftime('%Y-%m-%d'),
                    on_change=on_date_from_change
                ).props('type=date').classes('w-40')

                ui.input(
                    label='To',
                    value=last_month_end.strftime('%Y-%m-%d'),
                    on_change=on_date_to_change
                ).props('type=date').classes('w-40')

                ui.button('Search', icon='search', on_click=load_data).props('color=primary')

                ui.space()

                refs['status_label'] = ui.label('Select date range and click Search').classes('text-sm text-gray-500')

        # Side-by-side layout for Payments and Products
        with ui.row().classes('w-full gap-4 items-start'):
            # Payments section (left)
            with ui.card().classes('w-1/2'):
                with ui.row().classes('w-full items-center justify-between mb-2'):
                    ui.label('Daily Sales Payments').classes('text-lg font-semibold')
                ui.label('Click to filter products by date').classes('text-xs text-gray-500 mb-2')

                payments_columns = [
                    {'name': 'startDate', 'label': 'Date', 'field': 'startDate', 'align': 'center', 'sortable': True},
                    {'name': 'AdditionID', 'label': 'Addition ID', 'field': 'AdditionID', 'align': 'left', 'sortable': True},
                    {'name': 'TotalCaisse', 'label': 'Total Caisse', 'field': 'TotalCaisse', 'align': 'right', 'sortable': True},
                    {'name': 'CB', 'label': 'CB', 'field': 'CB', 'align': 'right', 'sortable': True},
                    {'name': 'CHEQUE', 'label': 'Cheque', 'field': 'CHEQUE', 'align': 'right', 'sortable': True},
                    {'name': 'CASH', 'label': 'Cash', 'field': 'CASH', 'align': 'right', 'sortable': True},
                    {'name': 'TR', 'label': 'TR', 'field': 'TR', 'align': 'right', 'sortable': True},
                    {'name': 'AX', 'label': 'AX', 'field': 'AX', 'align': 'right', 'sortable': True},
                    {'name': 'CTR', 'label': 'CTR', 'field': 'CTR', 'align': 'right', 'sortable': True},
                ]

                refs['payments_table'] = ui.table(
                    columns=payments_columns,
                    rows=[],
                    row_key='SalesPaymentsID',
                    pagination=50
                ).classes('w-full cursor-pointer')

                # Make rows clickable
                refs['payments_table'].on('rowClick', on_payment_click)

                # Custom body slot for row styling and click handling
                refs['payments_table'].add_slot('body', '''
                    <q-tr :props="props"
                          @click="$parent.$emit('rowClick', {row: props.row})"
                          class="cursor-pointer hover:bg-blue-50 dark:hover:bg-gray-700">
                        <q-td key="startDate" :props="props">
                            <span class="font-medium">{{ props.row.startDate }}</span>
                        </q-td>
                        <q-td key="AdditionID" :props="props">
                            {{ props.row.AdditionID }}
                        </q-td>
                        <q-td key="TotalCaisse" :props="props" class="text-right">
                            <span class="font-semibold text-green-600">
                                {{ props.row.TotalCaisse ? props.row.TotalCaisse.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                            </span>
                        </q-td>
                        <q-td key="CB" :props="props" class="text-right">
                            {{ props.row.CB ? props.row.CB.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                        </q-td>
                        <q-td key="CHEQUE" :props="props" class="text-right">
                            {{ props.row.CHEQUE ? props.row.CHEQUE.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                        </q-td>
                        <q-td key="CASH" :props="props" class="text-right">
                            {{ props.row.CASH ? props.row.CASH.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                        </q-td>
                        <q-td key="TR" :props="props" class="text-right">
                            {{ props.row.TR ? props.row.TR.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                        </q-td>
                        <q-td key="AX" :props="props" class="text-right">
                            {{ props.row.AX ? props.row.AX.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                        </q-td>
                        <q-td key="CTR" :props="props" class="text-right">
                            {{ props.row.CTR ? props.row.CTR.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                        </q-td>
                    </q-tr>
                ''')

            # Products section (right)
            with ui.card().classes('flex-grow'):
                with ui.row().classes('w-full items-center justify-between mb-2'):
                    ui.label('Product Sales Summary').classes('text-lg font-semibold')
                    refs['selection_label'] = ui.label('Showing all products for period').classes('text-sm text-gray-500')

                products_columns = [
                    {'name': 'ProductName', 'label': 'Product Name', 'field': 'ProductName', 'align': 'left', 'sortable': True},
                    {'name': 'Quantity', 'label': 'Quantity', 'field': 'Quantity', 'align': 'right', 'sortable': True},
                    {'name': 'TotalSales', 'label': 'Total Sales', 'field': 'TotalSales', 'align': 'right', 'sortable': True},
                ]

                refs['products_table'] = ui.table(
                    columns=products_columns,
                    rows=[],
                    row_key='ProductName',
                    pagination=50
                ).classes('w-full')

                # Custom slot for Quantity formatting
                refs['products_table'].add_slot('body-cell-Quantity', '''
                    <q-td :props="props" class="text-right">
                        <span class="font-medium">
                            {{ props.row.Quantity ? props.row.Quantity.toLocaleString('fr-FR', {minimumFractionDigits: 0, maximumFractionDigits: 2}) : '0' }}
                        </span>
                    </q-td>
                ''')

                # Custom slot for TotalSales with currency formatting
                refs['products_table'].add_slot('body-cell-TotalSales', '''
                    <q-td :props="props" class="text-right">
                        <span class="font-semibold text-green-600">
                            {{ props.row.TotalSales ? props.row.TotalSales.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                        </span>
                    </q-td>
                ''')
