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
    }

    # UI references
    refs = {
        'summary_table': None,
        'details_table': None,
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
            if state['selected_category']:
                refs['selection_label'].set_text(f"Filtered: {state['selected_type']} - {state['selected_category']}")
                refs['selection_label'].classes(remove='text-gray-500', add='text-blue-600 font-semibold')
            else:
                refs['selection_label'].set_text('Showing all transactions')
                refs['selection_label'].classes(remove='text-blue-600 font-semibold', add='text-gray-500')

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

        # Update tables
        update_summary_table()
        update_details_table()
        update_selection_label()

    def update_summary_table():
        """Update summary table with current data."""
        if refs['summary_table']:
            refs['summary_table'].update_rows(state['summary_data'])

    def update_details_table():
        """Update details table with filtered data."""
        if refs['details_table']:
            refs['details_table'].update_rows(state['filtered_details'])

    def on_summary_click(e):
        """Handle click on summary row to filter details."""
        if not e.args:
            return

        row = e.args.get('row') if isinstance(e.args, dict) else e.args[1]  # Get the row data
        clicked_type = row.get('Type')
        clicked_name = row.get('Name')

        # Skip total rows (but allow UNCLASS rows)
        if clicked_name in ['Remise Total', 'TOTAL SORTANT']:
            return

        # Toggle selection
        if state['selected_category'] == clicked_name and state['selected_type'] == clicked_type:
            # Deselect - show all
            state['selected_category'] = None
            state['selected_type'] = None
            state['filtered_details'] = state['details_data']
        else:
            # Select - filter by category
            state['selected_category'] = clicked_name
            state['selected_type'] = clicked_type

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

    def on_month_change(e):
        """Handle month selection change."""
        state['month'] = e.value

    def on_year_change(e):
        """Handle year selection change."""
        state['year'] = e.value

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

                details_columns = [
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

                refs['details_table'] = ui.table(
                    columns=details_columns,
                    rows=[],
                    row_key='TransactionID',
                    pagination=50
                ).classes('w-full')

                # Custom slot for Type with color coding
                refs['details_table'].add_slot('body-cell-Type', '''
                    <q-td :props="props">
                        <q-badge :color="props.row.Type === 'INBOUND' ? 'green' : 'red'">
                            {{ props.row.Type }}
                        </q-badge>
                    </q-td>
                ''')

                # Custom slot for Montant with formatting
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
