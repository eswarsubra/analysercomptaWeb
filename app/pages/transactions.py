from nicegui import ui
from datetime import date
from app.components.layout import layout
from app.services import BankInstructionService


@ui.page('/transactions')
def transactions_page():
    """View Transactions page - read-only view of bank instructions."""

    # State
    transactions_data = []
    table_ref = {'table': None}
    count_label_ref = {'label': None}

    # Get default date range (previous month)
    default_from, default_to = BankInstructionService.get_default_date_range()

    # Filter state
    filters = {
        'date_from': default_from,
        'date_to': default_to,
        'libelle': None,
        'montant': None,
        'filename': None
    }

    def load_transactions():
        nonlocal transactions_data
        transactions_data = BankInstructionService.get_all(
            date_from=filters['date_from'],
            date_to=filters['date_to'],
            libelle=filters['libelle'] if filters['libelle'] else None,
            montant=filters['montant'],
            filename=filters['filename'] if filters['filename'] else None
        )
        if table_ref['table']:
            table_ref['table'].update_rows(transactions_data)
        update_count()

    def update_count():
        count = len(transactions_data)
        if count_label_ref['label']:
            count_label_ref['label'].set_text(f"Showing {count} transaction(s)")

    def on_date_from_change(value):
        from datetime import datetime
        try:
            filters['date_from'] = datetime.strptime(value, '%Y-%m-%d').date() if value else None
            load_transactions()
        except (ValueError, TypeError):
            pass  # Invalid date format, ignore

    def on_date_to_change(value):
        from datetime import datetime
        try:
            filters['date_to'] = datetime.strptime(value, '%Y-%m-%d').date() if value else None
            load_transactions()
        except (ValueError, TypeError):
            pass  # Invalid date format, ignore

    def on_libelle_change(e):
        filters['libelle'] = e.value if e.value else None
        load_transactions()

    def on_montant_change(e):
        try:
            filters['montant'] = float(e.value) if e.value else None
        except (ValueError, TypeError):
            filters['montant'] = None
        load_transactions()

    def on_filename_change(e):
        filters['filename'] = e.value if e.value else None
        load_transactions()

    def clear_filters():
        filters['date_from'] = default_from
        filters['date_to'] = default_to
        filters['libelle'] = None
        filters['montant'] = None
        filters['filename'] = None
        # Update UI elements
        date_from_input.value = default_from.strftime('%Y-%m-%d')
        date_to_input.value = default_to.strftime('%Y-%m-%d')
        libelle_input.value = ''
        montant_input.value = ''
        filename_select.value = None
        load_transactions()

    with layout('View Transactions'):
        # Filter card
        with ui.card().classes('w-full mb-4'):
            ui.label('Search Filters').classes('text-lg font-semibold mb-2')

            with ui.row().classes('w-full items-end gap-4 flex-wrap'):
                # Date range filters with compact popup pickers
                with ui.input(label='Date From', value=default_from.strftime('%Y-%m-%d'),
                              on_change=lambda e: on_date_from_change(e.value)) as date_from_input:
                    date_from_input.props('mask="####-##-##" debounce=500')
                    with ui.menu().props('no-parent-event') as menu_from:
                        with ui.date(value=default_from, on_change=lambda e: (date_from_input.set_value(e.value), menu_from.close())):
                            pass
                    with date_from_input.add_slot('append'):
                        ui.icon('edit_calendar').on('click', menu_from.open).classes('cursor-pointer')

                with ui.input(label='Date To', value=default_to.strftime('%Y-%m-%d'),
                              on_change=lambda e: on_date_to_change(e.value)) as date_to_input:
                    date_to_input.props('mask="####-##-##" debounce=500')
                    with ui.menu().props('no-parent-event') as menu_to:
                        with ui.date(value=default_to, on_change=lambda e: (date_to_input.set_value(e.value), menu_to.close())):
                            pass
                    with date_to_input.add_slot('append'):
                        ui.icon('edit_calendar').on('click', menu_to.open).classes('cursor-pointer')

                # Libelle search
                libelle_input = ui.input(
                    label='Libelle',
                    placeholder='Search libelle...',
                    on_change=on_libelle_change
                ).classes('w-48').props('debounce=500 clearable')

                # Montant filter
                montant_input = ui.input(
                    label='Montant',
                    placeholder='Amount...',
                    on_change=on_montant_change
                ).classes('w-32').props('debounce=500 clearable type=number')

                # Filename filter
                filenames = BankInstructionService.get_distinct_filenames()
                filename_options = {None: 'All Files'}
                filename_options.update({f: f for f in filenames})
                filename_select = ui.select(
                    label='Filename',
                    options=filename_options,
                    value=None,
                    on_change=on_filename_change
                ).classes('w-48')

                # Clear filters button
                ui.button('Clear Filters', icon='clear', on_click=clear_filters).props('flat')

        # Results count
        count_label_ref['label'] = ui.label('Loading...').classes('text-sm text-gray-500 mb-2')

        # Data table (read-only)
        columns = [
            {'name': 'TransactionID', 'label': 'ID', 'field': 'TransactionID', 'align': 'left', 'sortable': True},
            {'name': 'Compte', 'label': 'Compte', 'field': 'Compte', 'align': 'left', 'sortable': True},
            {'name': 'Date_de_comptabilisation', 'label': 'Date Comptabilisation', 'field': 'Date_de_comptabilisation', 'align': 'center', 'sortable': True},
            {'name': 'Date_operation', 'label': 'Date Operation', 'field': 'Date_operation', 'align': 'center', 'sortable': True},
            {'name': 'Libelle', 'label': 'Libelle', 'field': 'Libelle', 'align': 'left'},
            {'name': 'Reference', 'label': 'Reference', 'field': 'Reference', 'align': 'left'},
            {'name': 'Date_valeur', 'label': 'Date Valeur', 'field': 'Date_valeur', 'align': 'center', 'sortable': True},
            {'name': 'Montant', 'label': 'Montant', 'field': 'Montant', 'align': 'right', 'sortable': True},
            {'name': 'filename', 'label': 'Filename', 'field': 'filename', 'align': 'left', 'sortable': True},
        ]

        table_ref['table'] = ui.table(
            columns=columns,
            rows=[],
            row_key='TransactionID',
            pagination=25
        ).classes('w-full')

        # Custom slot for Montant to format as currency and color
        table_ref['table'].add_slot('body-cell-Montant', '''
            <q-td :props="props" style="user-select: text;">
                <span :class="props.row.Montant < 0 ? 'text-red-600' : 'text-green-600'" class="font-medium">
                    {{ props.row.Montant ? props.row.Montant.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '0.00' }}
                </span>
            </q-td>
        ''')

        # Custom slot for Libelle to allow text selection
        table_ref['table'].add_slot('body-cell-Libelle', '''
            <q-td :props="props" style="user-select: text; cursor: text; max-width: 400px;">
                <span class="text-grey-8">{{ props.row.Libelle || '-' }}</span>
            </q-td>
        ''')

        # Custom slot for filename to allow text selection
        table_ref['table'].add_slot('body-cell-filename', '''
            <q-td :props="props" style="user-select: text; cursor: text;">
                <span class="text-grey-8">{{ props.row.filename || '-' }}</span>
            </q-td>
        ''')

        # Load initial data
        load_transactions()
