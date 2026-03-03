"""Reconciliation page - bank vs sales delta analysis by payment type."""
from nicegui import ui
from datetime import date
from dateutil.relativedelta import relativedelta
from app.components.layout import layout
from app.services import ReconciliationService, BankInstructionService


@ui.page('/analytics/reconciliation')
def reconciliation_page():
    """Reconciliation analytics page."""

    # Default to previous month
    today = date.today()
    last_month = today.replace(day=1) - relativedelta(months=1)
    default_month = last_month.month
    default_year = last_month.year

    # Get available months/years
    distinct_data = BankInstructionService.get_distinct_months_years()
    available_months = distinct_data.get('months', list(range(1, 13)))
    available_years = distinct_data.get('years', [default_year])
    if default_month not in available_months:
        available_months = sorted(set(available_months + [default_month]))
    if default_year not in available_years:
        available_years = sorted(set(available_years + [default_year]))

    month_names = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December'
    }
    month_options = {m: month_names[m] for m in available_months}
    year_options = {y: str(y) for y in available_years}

    # State
    state = {
        'month': default_month,
        'year': default_year,
        'summary_data': [],
        'month_status': 'OPEN',
        'month_id': None,
        'selected_payment_type': None,
        'bank_daily': [],
        'sales_daily': [],
        'adjustments': [],
        'all_justifications': [],
    }

    refs = {
        'summary_table': None,
        'status_badge': None,
        'close_btn': None,
        'reopen_btn': None,
        'drilldown_container': None,
        'bank_daily_table': None,
        'sales_daily_table': None,
        'adj_table': None,
        'justification_textarea': None,
        'justified_at_label': None,
        'drilldown_title': None,
        'status_label': None,
        'month_summary_container': None,
        'month_summary_content': None,
        'month_summary_textarea': None,
        'month_summary_saved_label': None,
        'month_progress_label': None,
    }

    def format_euro(value):
        if value is None:
            return '0.00'
        return f"{value:,.2f}".replace(',', ' ')

    def load_data():
        month = state['month']
        year = state['year']

        # Load summary
        state['summary_data'] = ReconciliationService.get_summary(month, year)

        # Add total row
        total = {
            'payment_type': 'TOTAL',
            'bank_total': sum(r['bank_total'] for r in state['summary_data']),
            'sales_total': sum(r['sales_total'] for r in state['summary_data']),
            'adjustments_total': sum(r['adjustments_total'] for r in state['summary_data']),
            'delta': sum(r['delta'] for r in state['summary_data']),
            'justification': None,
            'justified_at': None,
        }

        # Load month status
        month_status = ReconciliationService.get_month_status(month, year)
        state['month_status'] = month_status.get('status', 'OPEN')
        state['month_id'] = month_status.get('id')

        # Update summary table
        rows = state['summary_data'] + [total]
        if refs['summary_table']:
            refs['summary_table'].update_rows(rows)

        # Update status
        _update_status_ui()

        # Reset drilldown, show month summary
        state['selected_payment_type'] = None
        if refs['drilldown_container']:
            refs['drilldown_container'].set_visibility(False)

        if refs['status_label']:
            refs['status_label'].set_text(f"Loaded {month_names[month]} {year}")

        # Auto-show month summary panel
        _load_month_summary()

    def _update_status_ui():
        is_closed = state['month_status'] == 'CLOSED'
        if refs['status_badge']:
            refs['status_badge'].set_text(state['month_status'])
            if is_closed:
                refs['status_badge'].props('color=green')
            else:
                refs['status_badge'].props('color=orange')
        if refs['close_btn']:
            refs['close_btn'].set_visibility(not is_closed)
        if refs['reopen_btn']:
            refs['reopen_btn'].set_visibility(is_closed)

    def on_close_month():
        result = ReconciliationService.close_month(state['month'], state['year'])
        if result['success']:
            ui.notify(result['message'], type='positive')
            load_data()
        else:
            ui.notify(result['message'], type='warning')

    def on_reopen_month():
        result = ReconciliationService.reopen_month(state['month'], state['year'])
        if result['success']:
            ui.notify(result['message'], type='positive')
            load_data()
        else:
            ui.notify(result['message'], type='negative')

    def on_summary_click(e):
        if not e.args:
            return
        row = e.args.get('row') if isinstance(e.args, dict) else e.args[1]
        pt = row.get('payment_type')
        if not pt:
            return

        if pt == 'TOTAL':
            state['selected_payment_type'] = None
            if refs['drilldown_container']:
                refs['drilldown_container'].set_visibility(False)
            _load_month_summary()
            return

        state['selected_payment_type'] = pt
        if refs['month_summary_container']:
            refs['month_summary_container'].set_visibility(False)
        _load_drilldown(pt)

    def _load_drilldown(payment_type):
        month = state['month']
        year = state['year']

        # Load daily breakdown
        breakdown = ReconciliationService.get_daily_breakdown(month, year, payment_type)
        state['bank_daily'] = breakdown.get('bank_daily', [])
        state['sales_daily'] = breakdown.get('sales_daily', [])

        # Load adjustments
        state['adjustments'] = ReconciliationService.get_adjustments(month, year, payment_type)

        # Load justification
        justif = ReconciliationService.get_justification(month, year, payment_type)

        # Update tables
        bank_rows = state['bank_daily'] + [{'date': 'TOTAL', 'amount': sum(r['amount'] for r in state['bank_daily'])}]
        sales_rows = state['sales_daily'] + [{'date': 'TOTAL', 'amount': sum(r['amount'] for r in state['sales_daily'])}]

        if refs['bank_daily_table']:
            refs['bank_daily_table'].update_rows(bank_rows)
        if refs['sales_daily_table']:
            refs['sales_daily_table'].update_rows(sales_rows)
        if refs['adj_table']:
            refs['adj_table'].update_rows(state['adjustments'])
        if refs['drilldown_title']:
            refs['drilldown_title'].set_text(f'{payment_type} - Daily Breakdown')
        if refs['justification_textarea']:
            refs['justification_textarea'].value = justif.get('justification', '') if justif else ''
            refs['justification_textarea'].set_enabled(state['month_status'] != 'CLOSED')
        if refs['justified_at_label']:
            jat = justif.get('justified_at') if justif else None
            refs['justified_at_label'].set_text(f'Last saved: {jat}' if jat else '')

        if refs['drilldown_container']:
            refs['drilldown_container'].set_visibility(True)

    def on_save_justification():
        pt = state['selected_payment_type']
        if not pt:
            return

        text = refs['justification_textarea'].value if refs['justification_textarea'] else ''
        if not text.strip():
            ui.notify('Justification text cannot be empty', type='warning')
            return

        # Find current totals from summary
        pt_data = next((s for s in state['summary_data'] if s['payment_type'] == pt), None)
        if not pt_data:
            return

        result = ReconciliationService.save_justification(
            state['month'], state['year'], pt,
            text, pt_data['bank_total'], pt_data['sales_total'], pt_data['delta']
        )

        if result['success']:
            ui.notify(f'{pt} justification saved', type='positive')
            if refs['justified_at_label']:
                refs['justified_at_label'].set_text(f"Last saved: {result.get('justified_at', '')}")
            # Reload summary to update justified_at in table
            load_data()
            # Re-select the payment type
            state['selected_payment_type'] = pt
            _load_drilldown(pt)
        else:
            ui.notify(result['message'], type='negative')

    def on_generate_ai(provider: str):
        pt = state['selected_payment_type']
        if not pt:
            return

        ui.notify(f'Generating with {provider}...', type='info')
        try:
            text = ReconciliationService.generate_ai_justification(
                state['month'], state['year'], pt, provider
            )
            if refs['justification_textarea']:
                refs['justification_textarea'].value = text
            ui.notify('Draft generated', type='positive')
        except RuntimeError as e:
            ui.notify(str(e), type='negative')

    def on_add_adjustment():
        pt = state['selected_payment_type']
        if not pt:
            return
        adj_dialog.open()

    def on_confirm_add_adjustment():
        pt = state['selected_payment_type']
        if not pt:
            return

        label_val = adj_fields['label'].value
        amount_val = adj_fields['amount'].value
        date_val = adj_fields['date'].value

        if not label_val or not label_val.strip():
            ui.notify('Label is required', type='warning')
            return
        if amount_val is None or amount_val == 0:
            ui.notify('Amount is required and cannot be zero', type='warning')
            return

        entry_date = None
        if date_val:
            try:
                from datetime import date as date_cls
                entry_date = date_cls.fromisoformat(date_val)
            except (ValueError, TypeError):
                pass

        result = ReconciliationService.add_adjustment(
            state['month'], state['year'], pt,
            label_val.strip(), float(amount_val), entry_date
        )

        if result['success']:
            ui.notify('Adjustment added', type='positive')
            adj_dialog.close()
            # Clear fields
            adj_fields['label'].value = ''
            adj_fields['amount'].value = 0
            adj_fields['date'].value = ''
            # Reload
            load_data()
            state['selected_payment_type'] = pt
            _load_drilldown(pt)
        else:
            ui.notify(result['message'], type='negative')

    def on_delete_adjustment(adj_id):
        result = ReconciliationService.delete_adjustment(adj_id)
        if result['success']:
            ui.notify('Adjustment deleted', type='positive')
            pt = state['selected_payment_type']
            load_data()
            if pt:
                state['selected_payment_type'] = pt
                _load_drilldown(pt)
        else:
            ui.notify(result['message'], type='negative')

    # ==================== MONTH SUMMARY FUNCTIONS ====================

    def _load_month_summary():
        """Load and display the monthly summary panel with all justifications."""
        month = state['month']
        year = state['year']

        # Load all justifications with adjustments
        all_justifs = ReconciliationService.get_all_justifications(month, year)
        state['all_justifications'] = all_justifs

        # Load existing month summary
        existing_summary = ReconciliationService.get_month_summary(month, year)

        # Count justified
        justified_count = sum(1 for j in all_justifs if j.get('justified_at'))

        # Update progress label
        if refs['month_progress_label']:
            refs['month_progress_label'].set_text(f'{justified_count}/5 justified')

        # Dynamically build the payment type cards
        if refs['month_summary_content']:
            refs['month_summary_content'].clear()
            with refs['month_summary_content']:
                for pt_justif in all_justifs:
                    pt = pt_justif['payment_type']
                    # Get live totals from summary_data
                    pt_summary = next(
                        (s for s in state['summary_data'] if s['payment_type'] == pt), {}
                    )
                    bank = pt_summary.get('bank_total', 0)
                    sales = pt_summary.get('sales_total', 0)
                    delta = pt_summary.get('delta', 0)
                    adj_total = pt_summary.get('adjustments_total', 0)
                    adjustments = pt_justif.get('adjustments', [])
                    justif_text = pt_justif.get('justification', '')
                    justified_at = pt_justif.get('justified_at')

                    # Color for delta
                    delta_color = 'text-green-600' if abs(delta) < 0.01 else 'text-red-600'

                    with ui.card().classes('w-full mb-3'):
                        # Header with payment type name
                        with ui.row().classes('w-full items-center justify-between'):
                            ui.label(pt).classes('text-lg font-bold text-blue-700')
                            if justified_at:
                                ui.badge('Justified', color='green').props('outline')
                            else:
                                ui.badge('Not justified', color='red').props('outline')

                        # Totals row
                        with ui.row().classes('w-full gap-6 mt-1'):
                            ui.label(f'Bank: {format_euro(bank)}').classes('text-sm')
                            ui.label(f'Sales: {format_euro(sales)}').classes('text-sm')
                            ui.label(f'Delta: {format_euro(delta)}').classes(f'text-sm font-semibold {delta_color}')

                        # Adjustments
                        if adjustments:
                            ui.label(f'Adjustments ({len(adjustments)}):').classes('text-sm font-medium mt-2')
                            for adj in adjustments:
                                amt = adj.get('amount', 0)
                                sign = '+' if amt >= 0 else ''
                                date_str = adj.get('entry_date', '') or ''
                                date_display = f' ({date_str})' if date_str else ''
                                color = 'text-green-600' if amt >= 0 else 'text-red-600'
                                ui.label(
                                    f'  {adj.get("label", "")}: {sign}{format_euro(amt)}{date_display}'
                                ).classes(f'text-sm ml-4 {color}')
                            ui.label(
                                f'  Adj. Total: {format_euro(adj_total)}'
                            ).classes('text-sm ml-4 font-medium text-purple-600')
                        else:
                            ui.label('Adjustments: (none)').classes('text-sm text-gray-400 mt-2')

                        # Justification text
                        ui.textarea(
                            value=justif_text or '',
                            label=f'{pt} Justification',
                        ).classes('w-full mt-2').props(
                            'readonly rows=3' + (' filled' if justif_text else ' placeholder="Not yet justified"')
                        )

        # Update month summary textarea
        if refs['month_summary_textarea']:
            refs['month_summary_textarea'].value = existing_summary or ''
            refs['month_summary_textarea'].set_enabled(state['month_status'] != 'CLOSED')

        if refs['month_summary_saved_label']:
            refs['month_summary_saved_label'].set_text('')

        if refs['month_summary_container']:
            refs['month_summary_container'].set_visibility(True)

    def on_save_month_summary():
        text = refs['month_summary_textarea'].value if refs['month_summary_textarea'] else ''
        if not text.strip():
            ui.notify('Summary text cannot be empty', type='warning')
            return

        result = ReconciliationService.save_month_summary(
            state['month'], state['year'], text
        )
        if result['success']:
            ui.notify('Monthly summary saved', type='positive')
            if refs['month_summary_saved_label']:
                refs['month_summary_saved_label'].set_text('Saved successfully')
        else:
            ui.notify(result['message'], type='negative')

    def on_generate_month_summary(provider: str):
        ui.notify(f'Generating monthly summary with {provider}...', type='info')
        try:
            text = ReconciliationService.generate_ai_month_summary(
                state['month'], state['year'], provider
            )
            if refs['month_summary_textarea']:
                refs['month_summary_textarea'].value = text
            ui.notify('Monthly summary draft generated', type='positive')
        except RuntimeError as e:
            ui.notify(str(e), type='negative')

    # ==================== UI LAYOUT ====================

    # Add Adjustment dialog
    adj_fields = {}
    with ui.dialog() as adj_dialog, ui.card().classes('p-4 min-w-[400px]'):
        ui.label('Add Manual Adjustment').classes('text-lg font-semibold mb-4')
        with ui.column().classes('w-full gap-2'):
            adj_fields['label'] = ui.input(label='Description').classes('w-full')
            with ui.row().classes('w-full gap-4'):
                adj_fields['amount'] = ui.number(label='Amount', value=0, step=0.01).classes('flex-1')
                adj_fields['date'] = ui.input(label='Date (YYYY-MM-DD)').classes('flex-1')
        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            ui.button('Cancel', on_click=adj_dialog.close).props('flat')
            ui.button('Add', on_click=on_confirm_add_adjustment).props('color=primary')

    with layout('Reconciliation'):
        # Header
        with ui.card().classes('w-full mb-4'):
            with ui.row().classes('w-full items-center gap-4'):
                ui.select(
                    label='Month', options=month_options,
                    value=default_month, on_change=lambda e: state.update(month=e.value)
                ).classes('w-40')
                ui.select(
                    label='Year', options=year_options,
                    value=default_year, on_change=lambda e: state.update(year=e.value)
                ).classes('w-32')
                ui.button('Load', icon='search', on_click=load_data).props('color=primary')

                ui.space()

                refs['status_badge'] = ui.badge('OPEN', color='orange').classes('text-sm px-3 py-1')
                refs['close_btn'] = ui.button('Close Month', icon='lock', on_click=on_close_month).props('flat color=green')
                refs['reopen_btn'] = ui.button('Reopen', icon='lock_open', on_click=on_reopen_month).props('flat color=orange')
                refs['reopen_btn'].set_visibility(False)

                refs['status_label'] = ui.label('Select month/year and click Load').classes('text-sm text-gray-500')

        # Summary table
        with ui.card().classes('w-full mb-4'):
            ui.label('Payment Type Summary').classes('text-lg font-semibold mb-2')
            ui.label('Click a row to drill down, click TOTAL for monthly summary').classes('text-xs text-gray-500 mb-2')

            summary_columns = [
                {'name': 'payment_type', 'label': 'Payment Type', 'field': 'payment_type', 'align': 'left', 'sortable': True},
                {'name': 'bank_total', 'label': 'Bank', 'field': 'bank_total', 'align': 'right', 'sortable': True},
                {'name': 'sales_total', 'label': 'Sales', 'field': 'sales_total', 'align': 'right', 'sortable': True},
                {'name': 'adjustments_total', 'label': 'Adjustments', 'field': 'adjustments_total', 'align': 'right', 'sortable': True},
                {'name': 'delta', 'label': 'Delta', 'field': 'delta', 'align': 'right', 'sortable': True},
                {'name': 'justified_at', 'label': 'Justified', 'field': 'justified_at', 'align': 'center'},
            ]

            refs['summary_table'] = ui.table(
                columns=summary_columns,
                rows=[],
                row_key='payment_type',
            ).classes('w-full cursor-pointer')

            refs['summary_table'].on('rowClick', on_summary_click)

            # Custom body slot for styling
            refs['summary_table'].add_slot('body', '''
                <q-tr :props="props"
                      @click="$parent.$emit('rowClick', {row: props.row})"
                      :class="{
                          'bg-gray-200 dark:bg-gray-700 font-bold cursor-pointer hover:bg-gray-300 dark:hover:bg-gray-600': props.row.payment_type === 'TOTAL',
                          'cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800': props.row.payment_type !== 'TOTAL'
                      }">
                    <q-td key="payment_type" :props="props">
                        <span :class="props.row.payment_type === 'TOTAL' ? 'font-bold' : 'text-blue-600'">
                            {{ props.row.payment_type }}
                        </span>
                    </q-td>
                    <q-td key="bank_total" :props="props" class="text-right">
                        {{ props.row.bank_total != null ? props.row.bank_total.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '0.00' }}
                    </q-td>
                    <q-td key="sales_total" :props="props" class="text-right">
                        {{ props.row.sales_total != null ? props.row.sales_total.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '0.00' }}
                    </q-td>
                    <q-td key="adjustments_total" :props="props" class="text-right">
                        <span :class="props.row.adjustments_total !== 0 ? 'text-purple-600 font-medium' : ''">
                            {{ props.row.adjustments_total != null ? props.row.adjustments_total.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '0.00' }}
                        </span>
                    </q-td>
                    <q-td key="delta" :props="props" class="text-right">
                        <q-badge v-if="Math.abs(props.row.delta) < 0.01" color="green" outline>0.00</q-badge>
                        <q-badge v-else-if="props.row.justified_at" color="amber" outline>
                            {{ props.row.delta.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) }}
                        </q-badge>
                        <q-badge v-else color="red" outline>
                            {{ props.row.delta.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) }}
                        </q-badge>
                    </q-td>
                    <q-td key="justified_at" :props="props" class="text-center">
                        <q-icon v-if="props.row.justified_at" name="check_circle" color="green" size="sm" />
                        <span v-else-if="props.row.payment_type !== 'TOTAL'" class="text-grey-4">-</span>
                    </q-td>
                </q-tr>
            ''')

        # Drilldown panel (hidden until a payment type is selected)
        with ui.card().classes('w-full') as drilldown_container:
            refs['drilldown_container'] = drilldown_container
            drilldown_container.set_visibility(False)

            refs['drilldown_title'] = ui.label('Daily Breakdown').classes('text-lg font-semibold mb-2')

            # Side-by-side daily tables
            with ui.row().classes('w-full gap-4 mb-4'):
                # Bank daily
                with ui.card().classes('flex-1'):
                    ui.label('Bank Daily').classes('font-semibold text-green-700 mb-1')
                    daily_columns = [
                        {'name': 'date', 'label': 'Date Operation', 'field': 'date', 'align': 'left', 'sortable': True},
                        {'name': 'amount', 'label': 'Amount', 'field': 'amount', 'align': 'right', 'sortable': True},
                    ]
                    refs['bank_daily_table'] = ui.table(
                        columns=daily_columns, rows=[], row_key='date',
                    ).classes('w-full')

                    refs['bank_daily_table'].add_slot('body-cell-amount', '''
                        <q-td :props="props" class="text-right">
                            <span :class="props.row.date === 'TOTAL' ? 'font-bold text-green-700' : ''">
                                {{ props.row.amount != null ? props.row.amount.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '0.00' }}
                            </span>
                        </q-td>
                    ''')
                    refs['bank_daily_table'].add_slot('body-cell-date', '''
                        <q-td :props="props">
                            <span :class="props.row.date === 'TOTAL' ? 'font-bold' : ''">
                                {{ props.row.date }}
                            </span>
                        </q-td>
                    ''')

                # Sales daily
                with ui.card().classes('flex-1'):
                    ui.label('Sales Daily').classes('font-semibold text-blue-700 mb-1')
                    refs['sales_daily_table'] = ui.table(
                        columns=daily_columns, rows=[], row_key='date',
                    ).classes('w-full')

                    refs['sales_daily_table'].add_slot('body-cell-amount', '''
                        <q-td :props="props" class="text-right">
                            <span :class="props.row.date === 'TOTAL' ? 'font-bold text-blue-700' : ''">
                                {{ props.row.amount != null ? props.row.amount.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '0.00' }}
                            </span>
                        </q-td>
                    ''')
                    refs['sales_daily_table'].add_slot('body-cell-date', '''
                        <q-td :props="props">
                            <span :class="props.row.date === 'TOTAL' ? 'font-bold' : ''">
                                {{ props.row.date }}
                            </span>
                        </q-td>
                    ''')

            # Manual Adjustments
            with ui.card().classes('w-full mb-4'):
                with ui.row().classes('w-full items-center justify-between mb-2'):
                    ui.label('Manual Adjustments').classes('font-semibold')
                    ui.button('Add Adjustment', icon='add', on_click=on_add_adjustment).props('flat color=purple dense')

                adj_columns = [
                    {'name': 'label', 'label': 'Description', 'field': 'label', 'align': 'left'},
                    {'name': 'entry_date', 'label': 'Date', 'field': 'entry_date', 'align': 'center'},
                    {'name': 'amount', 'label': 'Amount', 'field': 'amount', 'align': 'right'},
                    {'name': 'actions', 'label': '', 'field': 'id', 'align': 'center'},
                ]
                refs['adj_table'] = ui.table(
                    columns=adj_columns, rows=[], row_key='id',
                ).classes('w-full')

                refs['adj_table'].add_slot('body-cell-amount', '''
                    <q-td :props="props" class="text-right">
                        <span :class="props.row.amount >= 0 ? 'text-green-600' : 'text-red-600'" class="font-medium">
                            {{ props.row.amount != null ? props.row.amount.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '0.00' }}
                        </span>
                    </q-td>
                ''')

                refs['adj_table'].add_slot('body-cell-actions', '''
                    <q-td :props="props" class="text-center">
                        <q-btn flat round dense icon="delete" color="negative" size="sm"
                               @click.stop="$parent.$emit('delete-adj', props.row.id)" />
                    </q-td>
                ''')
                refs['adj_table'].on('delete-adj', lambda e: on_delete_adjustment(e.args))

            # Justification
            with ui.card().classes('w-full'):
                ui.label('Justification').classes('font-semibold mb-2')
                with ui.row().classes('gap-2 mb-2'):
                    ui.button('Generate with Qwen', icon='smart_toy',
                              on_click=lambda: on_generate_ai('ollama')).props('flat color=teal dense')
                    ui.button('Generate with Sonnet', icon='cloud',
                              on_click=lambda: on_generate_ai('bedrock')).props('flat color=deep-purple dense')

                refs['justification_textarea'] = ui.textarea(
                    label='Justification text',
                ).classes('w-full').props('rows=4')

                with ui.row().classes('w-full items-center justify-between mt-2'):
                    ui.button('Save Justification', icon='save',
                              on_click=on_save_justification).props('color=primary')
                    refs['justified_at_label'] = ui.label('').classes('text-sm text-gray-500')

        # Monthly Summary panel (hidden until TOTAL row is clicked)
        with ui.card().classes('w-full') as month_summary_container:
            refs['month_summary_container'] = month_summary_container
            month_summary_container.set_visibility(False)

            with ui.row().classes('w-full items-center justify-between mb-2'):
                ui.label('Monthly Reconciliation Summary').classes('text-lg font-semibold')
                refs['month_progress_label'] = ui.label('0/5 justified').classes(
                    'text-sm font-medium text-gray-600'
                )

            # Dynamic content area — cleared and rebuilt each time
            refs['month_summary_content'] = ui.column().classes('w-full gap-0')

            # Consolidated Monthly Summary section
            with ui.card().classes('w-full mt-4'):
                ui.label('Consolidated Monthly Summary').classes('font-semibold mb-2')
                with ui.row().classes('gap-2 mb-2'):
                    ui.button('Generate with Qwen', icon='smart_toy',
                              on_click=lambda: on_generate_month_summary('ollama')).props('flat color=teal dense')
                    ui.button('Generate with Sonnet', icon='cloud',
                              on_click=lambda: on_generate_month_summary('bedrock')).props('flat color=deep-purple dense')

                refs['month_summary_textarea'] = ui.textarea(
                    label='Monthly summary text',
                ).classes('w-full').props('rows=5')

                with ui.row().classes('w-full items-center justify-between mt-2'):
                    ui.button('Save Summary', icon='save',
                              on_click=on_save_month_summary).props('color=primary')
                    refs['month_summary_saved_label'] = ui.label('').classes('text-sm text-gray-500')
