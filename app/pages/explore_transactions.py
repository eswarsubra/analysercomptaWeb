from nicegui import ui
from datetime import date
from dateutil.relativedelta import relativedelta
from app.components.layout import layout
from app.services import BankInstructionService


@ui.page('/transactions/explore')
def explore_transactions_page():
    """Explore Transactions page - interactive exploration with summary and details."""

    # Get previous month as default
    today = date.today()
    first_of_current_month = today.replace(day=1)
    last_month = first_of_current_month - relativedelta(months=1)
    default_month = last_month.month
    default_year = last_month.year

    # Get distinct months and years from database
    distinct_data = BankInstructionService.get_distinct_months_years()
    available_months = distinct_data.get('months', list(range(1, 13)))
    available_years = distinct_data.get('years', [default_year])

    # Ensure default values are in available options
    if default_month not in available_months:
        available_months = sorted(set(available_months + [default_month]))
    if default_year not in available_years:
        available_years = sorted(set(available_years + [default_year]))

    # Month names for display
    month_names = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }
    month_options = {m: month_names[m] for m in available_months}
    year_options = {y: str(y) for y in available_years}

    # Page-level state (resets on page refresh)
    state = {
        'month': default_month,
        'year': default_year,
        'summary_data': [],
        'details_data': [],
        'filtered_details': [],
        'selected_category': None,
        'selected_type': None,
        'cb_grouped_mode': False,
        'cb_grouped_data': [],
    }

    # UI references
    refs = {
        'summary_table': None,
        'details_table': None,
        'selection_label': None,
        'status_label': None,
        'drilldown_dialog': None,
        'drilldown_table': None,
        'drilldown_title': None,
        'totals_row': None,
        'total_montant_label': None,
        'total_brut_label': None,
        'total_commission_label': None,
    }

    def update_status(message: str):
        """Update status label."""
        if refs['status_label']:
            refs['status_label'].set_text(message)

    def update_selection_label():
        """Update the selection indicator."""
        if refs['selection_label']:
            if state['cb_grouped_mode']:
                refs['selection_label'].set_text(f"Remise CB (grouped by date) - Click row for details")
                refs['selection_label'].classes(remove='text-gray-500', add='text-blue-600 font-semibold')
            elif state['selected_category']:
                refs['selection_label'].set_text(f"Filtered: {state['selected_type']} - {state['selected_category']}")
                refs['selection_label'].classes(remove='text-gray-500', add='text-blue-600 font-semibold')
            else:
                refs['selection_label'].set_text('Showing all transactions')
                refs['selection_label'].classes(remove='text-blue-600 font-semibold', add='text-gray-500')

    def format_euro(value):
        """Format a number as Euro currency."""
        if value is None:
            return '0.00 €'
        return f"{value:,.2f} €".replace(',', ' ').replace('.', ',')

    def update_totals():
        """Update the totals display based on current filtered data."""
        data = state['filtered_details']

        if state['cb_grouped_mode']:
            # CB grouped mode: sum SumMontant, SumBrutMontant, SumCommisionMontant
            total_montant = sum(row.get('SumMontant', 0) or 0 for row in data)
            total_brut = sum(row.get('SumBrutMontant', 0) or 0 for row in data)
            total_commission = sum(row.get('SumCommisionMontant', 0) or 0 for row in data)

            if refs['total_montant_label']:
                refs['total_montant_label'].set_text(f"Total Montant: {format_euro(total_montant)}")
            if refs['total_brut_label']:
                refs['total_brut_label'].set_text(f"Brut: {format_euro(total_brut)}")
                refs['total_brut_label'].set_visibility(True)
            if refs['total_commission_label']:
                refs['total_commission_label'].set_text(f"Commission: {format_euro(total_commission)}")
                refs['total_commission_label'].set_visibility(True)
        else:
            # Regular mode: sum Montant only
            total_montant = sum(row.get('Montant', 0) or 0 for row in data)

            if refs['total_montant_label']:
                refs['total_montant_label'].set_text(f"Total Montant: {format_euro(total_montant)}")
            if refs['total_brut_label']:
                refs['total_brut_label'].set_visibility(False)
            if refs['total_commission_label']:
                refs['total_commission_label'].set_visibility(False)

    def load_data():
        """Load data for selected month/year."""
        month = state['month']
        year = state['year']

        # Fetch from database
        update_status('Loading from database...')
        state['summary_data'] = BankInstructionService.get_monthly_summary(month, year)
        state['details_data'] = BankInstructionService.get_classified_transactions(month, year)
        update_status(f"Loaded {len(state['details_data'])} transactions")

        # Reset selection
        state['selected_category'] = None
        state['selected_type'] = None
        state['filtered_details'] = state['details_data']
        state['cb_grouped_mode'] = False
        state['cb_grouped_data'] = []

        # Update tables
        update_summary_table()
        update_details_table()
        update_selection_label()

    def update_summary_table():
        """Update summary table with current data."""
        if refs['summary_table']:
            refs['summary_table'].update_rows(state['summary_data'])

    # Column definitions for different views
    regular_columns = [
        {'name': 'Type', 'label': 'Type', 'field': 'Type', 'align': 'center', 'sortable': True},
        {'name': 'Qualifier', 'label': 'Qualifier', 'field': 'Qualifier', 'align': 'left', 'sortable': True},
        {'name': 'Libelle', 'label': 'Libelle', 'field': 'Libelle', 'align': 'left'},
        {'name': 'Montant', 'label': 'Montant', 'field': 'Montant', 'align': 'right', 'sortable': True},
        {'name': 'Date_comptabilisation', 'label': 'Date Compta', 'field': 'Date_comptabilisation', 'align': 'center', 'sortable': True},
        {'name': 'Date_operation', 'label': 'Date Op', 'field': 'Date_operation', 'align': 'center', 'sortable': True},
        {'name': 'Date_valeur', 'label': 'Date Valeur', 'field': 'Date_valeur', 'align': 'center', 'sortable': True},
        {'name': 'TransactionID', 'label': 'ID', 'field': 'TransactionID', 'align': 'left', 'sortable': True},
        {'name': 'Reference', 'label': 'Reference', 'field': 'Reference', 'align': 'left'},
    ]

    cb_grouped_columns = [
        {'name': 'Type', 'label': 'Type', 'field': 'Type', 'align': 'center', 'sortable': True},
        {'name': 'Qualifier', 'label': 'Qualifier', 'field': 'Qualifier', 'align': 'left', 'sortable': True},
        {'name': 'Date_Compta_Range', 'label': 'Date Compta', 'field': 'Date_Compta_Range', 'align': 'center', 'sortable': True},
        {'name': 'Date_operation', 'label': 'Date Op', 'field': 'Date_operation', 'align': 'center', 'sortable': True},
        {'name': 'Date_Valeur_Range', 'label': 'Date Valeur', 'field': 'Date_Valeur_Range', 'align': 'center', 'sortable': True},
        {'name': 'SumMontant', 'label': 'Montant', 'field': 'SumMontant', 'align': 'right', 'sortable': True},
        {'name': 'SumBrutMontant', 'label': 'Brut', 'field': 'SumBrutMontant', 'align': 'right', 'sortable': True},
        {'name': 'SumCommisionMontant', 'label': 'Commission', 'field': 'SumCommisionMontant', 'align': 'right', 'sortable': True},
    ]

    def update_details_table():
        """Update details table with filtered data and appropriate columns."""
        if refs['details_table']:
            # Switch columns based on mode
            if state['cb_grouped_mode']:
                refs['details_table'].columns = cb_grouped_columns
                refs['details_table']._props['row-key'] = 'Date_operation'
            else:
                refs['details_table'].columns = regular_columns
                refs['details_table']._props['row-key'] = 'TransactionID'
            refs['details_table'].update_rows(state['filtered_details'])
        update_totals()

    def on_summary_click(e):
        """Handle click on summary row to filter details."""
        if not e.args:
            return

        row = e.args.get('row') if isinstance(e.args, dict) else e.args[1]  # Get the row data
        clicked_type = row.get('Type')
        clicked_name = row.get('Name')

        # Skip total rows (but allow UNCLASS rows)
        if clicked_name in ['Remise Total', 'TOTAL SORTANT']:
            # Reset to show all transactions
            state['selected_category'] = None
            state['selected_type'] = None
            state['cb_grouped_mode'] = False
            state['cb_grouped_data'] = []
            state['filtered_details'] = state['details_data']
            update_details_table()
            update_selection_label()
            return

        # Toggle selection
        if state['selected_category'] == clicked_name and state['selected_type'] == clicked_type:
            # Deselect - show all
            state['selected_category'] = None
            state['selected_type'] = None
            state['cb_grouped_mode'] = False
            state['cb_grouped_data'] = []
            state['filtered_details'] = state['details_data']
        else:
            # Select - filter by category
            state['selected_category'] = clicked_name
            state['selected_type'] = clicked_type

            # Special handling for Remise CB - show grouped view
            if clicked_name == 'Remise CB':
                state['cb_grouped_mode'] = True
                state['cb_grouped_data'] = BankInstructionService.get_cb_grouped_by_date(
                    state['month'], state['year']
                )
                state['filtered_details'] = state['cb_grouped_data']
            else:
                state['cb_grouped_mode'] = False
                state['cb_grouped_data'] = []

                # Map summary Name to Qualifier in details
                # IN types map to INBOUND, OUT types map to OUTBOUND
                filter_type = 'INBOUND' if clicked_type == 'IN' else 'OUTBOUND'

                # Special mapping for summary names to qualifiers
                # Summary uses display names, qualifiers are from classification rules
                qualifier_map = {
                    # Inbound (summary uses mixed case display names)
                    'Remise CB': 'REMISE CB',
                    'Remise AMEX': 'REMISE AMERICAN EXPRESS',
                    'Remise CTR': 'REMISE CTR',
                    'Remise CASH': 'REMISE CASH',
                    'Remise CHEQUE': 'REM CHEQUE',
                    'Remise UNCLASS': 'UNCLASS INBOUND',
                    # Outbound (summary uses same names as qualifiers)
                    'PAIMENT CB': 'PAIMENT CB',
                    'VIREMENT SALAIRES': 'VIREMENT SALAIRES',
                    'VIREMENT SORTANT': 'VIREMENT SORTANT',
                    'PRELEVEMENT SORTANT': 'PRELEVEMENT SORTANT',
                    'PAIMENT ESPECES': 'PAIMENT ESPECES',
                    'PAIMENT CHEQUE': 'PAIMENT CHEQUE',
                    'FRAIS SORTANT': 'FRAIS SORTANT',
                    'CREDIT REMBOURSEMENT': 'CREDIT REMBOURSEMENT',
                    'UNCLASS SORTANT': 'UNCLASS OUTBOUND',
                }
                qualifier = qualifier_map.get(clicked_name, clicked_name)

                state['filtered_details'] = [
                    row for row in state['details_data']
                    if row.get('Type') == filter_type and row.get('Qualifier') == qualifier
                ]

        update_details_table()
        update_selection_label()

    def on_details_row_click(e):
        """Handle click on details row for drill-down from CB grouped view."""
        if not state['cb_grouped_mode']:
            return  # Only handle clicks in grouped mode

        if not e.args:
            return

        row = e.args.get('row') if isinstance(e.args, dict) else e.args[1]
        clicked_date = row.get('Date_operation')

        if not clicked_date:
            return

        # Get individual CB transactions for this date
        drilldown_data = [
            r for r in state['details_data']
            if r.get('Qualifier') == 'REMISE CB' and str(r.get('Date_operation')) == str(clicked_date)
        ]

        # Update dialog title and table
        if refs['drilldown_title']:
            refs['drilldown_title'].set_text(f"Remise CB - {clicked_date} ({len(drilldown_data)} transactions)")
        if refs['drilldown_table']:
            refs['drilldown_table'].update_rows(drilldown_data)

        # Open the dialog
        if refs['drilldown_dialog']:
            refs['drilldown_dialog'].open()

    def on_month_change(e):
        """Handle month selection change."""
        state['month'] = e.value

    def on_year_change(e):
        """Handle year selection change."""
        state['year'] = e.value

    # Drill-down dialog for CB transactions
    with ui.dialog().props('maximized') as drilldown_dialog:
        refs['drilldown_dialog'] = drilldown_dialog
        with ui.card().classes('w-full h-full overflow-auto'):
            with ui.row().classes('w-full items-center justify-between mb-4'):
                refs['drilldown_title'] = ui.label('CB Transactions').classes('text-xl font-bold')
                ui.button(icon='close', on_click=drilldown_dialog.close).props('flat round')

            refs['drilldown_table'] = ui.table(
                columns=regular_columns,
                rows=[],
                row_key='TransactionID',
                pagination=25
            ).classes('w-full')

            # Custom slot for Type with color coding
            refs['drilldown_table'].add_slot('body-cell-Type', '''
                <q-td :props="props">
                    <q-badge :color="props.row.Type === 'INBOUND' ? 'green' : 'red'">
                        {{ props.row.Type }}
                    </q-badge>
                </q-td>
            ''')

            # Custom slot for Montant with formatting
            refs['drilldown_table'].add_slot('body-cell-Montant', '''
                <q-td :props="props" class="text-right">
                    <span class="font-medium">
                        {{ props.row.Montant ? props.row.Montant.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                    </span>
                </q-td>
            ''')

            # Custom slot for Libelle with text selection
            refs['drilldown_table'].add_slot('body-cell-Libelle', '''
                <q-td :props="props" style="user-select: text; cursor: text; max-width: 400px;">
                    <span class="text-grey-8">{{ props.row.Libelle || '-' }}</span>
                </q-td>
            ''')

    with layout('Explore Transactions'):
        # Filter controls
        with ui.card().classes('w-full mb-4'):
            with ui.row().classes('w-full items-end gap-4'):
                ui.select(
                    label='Month',
                    options=month_options,
                    value=default_month,
                    on_change=on_month_change
                ).classes('w-40')

                ui.select(
                    label='Year',
                    options=year_options,
                    value=default_year,
                    on_change=on_year_change
                ).classes('w-32')

                ui.button('Search', icon='search', on_click=load_data).props('color=primary')

                ui.space()

                refs['status_label'] = ui.label('Select month/year and click Search').classes('text-sm text-gray-500')

        # Side-by-side layout for Summary and Details
        with ui.row().classes('w-full gap-4 items-start'):
            # Summary section (left, narrower)
            with ui.card().classes('w-1/3'):
                with ui.row().classes('w-full items-center justify-between mb-2'):
                    ui.label('Summary').classes('text-lg font-semibold')
                ui.label('Click to filter').classes('text-xs text-gray-500 mb-2')

                summary_columns = [
                    {'name': 'Type', 'label': 'Type', 'field': 'Type', 'align': 'center', 'sortable': True},
                    {'name': 'Name', 'label': 'Category', 'field': 'Name', 'align': 'left', 'sortable': True},
                    {'name': 'Montant', 'label': 'Montant', 'field': 'Montant', 'align': 'right', 'sortable': True},
                ]

                refs['summary_table'] = ui.table(
                    columns=summary_columns,
                    rows=[],
                    row_key='Name',
                ).classes('w-full cursor-pointer')

                # Make rows clickable
                refs['summary_table'].on('rowClick', on_summary_click)

                # Custom body slot for row styling based on Name
                refs['summary_table'].add_slot('body', '''
                    <q-tr :props="props"
                          @click="$parent.$emit('rowClick', {row: props.row})"
                          :class="{
                              'bg-green-100 dark:bg-green-900': props.row.Name === 'Remise Total',
                              'bg-red-100 dark:bg-red-900': props.row.Name === 'TOTAL SORTANT',
                              'bg-amber-100 dark:bg-amber-900': props.row.Name === 'Remise UNCLASS' || props.row.Name === 'UNCLASS SORTANT'
                          }">
                        <q-td key="Type" :props="props">
                            <q-badge :color="props.row.Type === 'IN' ? 'green' : 'red'">
                                {{ props.row.Type }}
                            </q-badge>
                        </q-td>
                        <q-td key="Name" :props="props">
                            <span :class="props.row.Name === 'Remise Total' || props.row.Name === 'TOTAL SORTANT'
                                          ? 'font-bold'
                                          : 'text-blue-600 hover:underline cursor-pointer'">
                                {{ props.row.Name }}
                            </span>
                        </q-td>
                        <q-td key="Montant" :props="props" class="text-right">
                            <span :class="props.row.Name === 'Remise Total' || props.row.Name === 'TOTAL SORTANT' ? 'font-bold' : 'font-medium'">
                                {{ props.row.Montant ? props.row.Montant.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                            </span>
                        </q-td>
                    </q-tr>
                ''')

            # Details section (right, wider)
            with ui.card().classes('flex-grow'):
                with ui.row().classes('w-full items-center justify-between mb-2'):
                    ui.label('Transaction Details').classes('text-lg font-semibold')
                    refs['selection_label'] = ui.label('Showing all transactions').classes('text-sm text-gray-500')

                # Totals row
                with ui.row().classes('w-full gap-6 mb-3 p-2 bg-gray-100 dark:bg-gray-800 rounded'):
                    refs['total_montant_label'] = ui.label('Total Montant: 0.00 €').classes('font-semibold text-green-600')
                    refs['total_brut_label'] = ui.label('Brut: 0.00 €').classes('font-semibold text-blue-600')
                    refs['total_brut_label'].set_visibility(False)
                    refs['total_commission_label'] = ui.label('Commission: 0.00 €').classes('font-semibold text-red-600')
                    refs['total_commission_label'].set_visibility(False)

                refs['details_table'] = ui.table(
                    columns=regular_columns,
                    rows=[],
                    row_key='TransactionID',
                    pagination=50
                ).classes('w-full')

                # Add row click handler for drill-down
                refs['details_table'].on('rowClick', on_details_row_click)

                # Custom slot for Type with color coding
                refs['details_table'].add_slot('body-cell-Type', '''
                    <q-td :props="props">
                        <q-badge :color="props.row.Type === 'INBOUND' ? 'green' : 'red'">
                            {{ props.row.Type }}
                        </q-badge>
                    </q-td>
                ''')

                # Custom slot for Montant with formatting (regular view)
                refs['details_table'].add_slot('body-cell-Montant', '''
                    <q-td :props="props" class="text-right">
                        <span class="font-medium">
                            {{ props.row.Montant ? props.row.Montant.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                        </span>
                    </q-td>
                ''')

                # Custom slot for Libelle with text selection
                refs['details_table'].add_slot('body-cell-Libelle', '''
                    <q-td :props="props" style="user-select: text; cursor: text; max-width: 400px;">
                        <span class="text-grey-8">{{ props.row.Libelle || '-' }}</span>
                    </q-td>
                ''')

                # Custom slots for CB grouped view columns
                refs['details_table'].add_slot('body-cell-SumMontant', '''
                    <q-td :props="props" class="text-right">
                        <span class="font-semibold text-green-600">
                            {{ props.row.SumMontant ? props.row.SumMontant.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                        </span>
                    </q-td>
                ''')

                refs['details_table'].add_slot('body-cell-SumBrutMontant', '''
                    <q-td :props="props" class="text-right">
                        <span class="font-medium text-blue-600">
                            {{ props.row.SumBrutMontant ? props.row.SumBrutMontant.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                        </span>
                    </q-td>
                ''')

                refs['details_table'].add_slot('body-cell-SumCommisionMontant', '''
                    <q-td :props="props" class="text-right">
                        <span class="font-medium text-red-600">
                            {{ props.row.SumCommisionMontant ? props.row.SumCommisionMontant.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' €' : '0.00 €' }}
                        </span>
                    </q-td>
                ''')
