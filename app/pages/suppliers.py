from nicegui import ui
from app.components.layout import layout
from app.services import SupplierService
from urllib.parse import parse_qs


@ui.page('/suppliers')
def suppliers_page():
    """Suppliers management page."""

    # State
    suppliers_data = []
    selected_supplier = {'id': None}
    table_ref = {'table': None}
    highlight_id = {'value': None}

    # Get highlight parameter from URL
    query_string = ui.context.client.request.query_params
    if 'highlight' in query_string:
        try:
            highlight_id['value'] = int(query_string['highlight'])
        except (ValueError, TypeError):
            pass

    def load_suppliers():
        nonlocal suppliers_data
        suppliers_data = SupplierService.get_all_with_counts()
        # Mark highlighted row
        for row in suppliers_data:
            if row['idsupplier'] == highlight_id['value']:
                row['_highlighted'] = True
        if table_ref['table']:
            table_ref['table'].update_rows(suppliers_data)

    def create_supplier(values):
        if values.get('name'):
            SupplierService.create(values['name'])
            ui.notify(f"Supplier '{values['name']}' created", type='positive')
            load_suppliers()

    def update_supplier(values):
        if selected_supplier['id'] and values.get('name'):
            SupplierService.update(selected_supplier['id'], values['name'])
            ui.notify('Supplier updated', type='positive')
            load_suppliers()

    def delete_supplier():
        if selected_supplier['id']:
            try:
                SupplierService.delete(selected_supplier['id'])
                ui.notify('Supplier deleted', type='positive')
                selected_supplier['id'] = None
                load_suppliers()
            except Exception as e:
                ui.notify(f'Cannot delete: {e}', type='negative')

    def on_row_select(e):
        if e.selection:
            selected_supplier['id'] = e.selection[0]['idsupplier']
            selected_supplier['name'] = e.selection[0]['name']
        else:
            selected_supplier['id'] = None

    with layout('Suppliers'):
        # Toolbar
        with ui.row().classes('w-full justify-between items-center mb-4'):
            ui.input(placeholder='Search suppliers...').classes('w-64').on(
                'keyup.enter',
                lambda e: _search_suppliers(e.sender.value, table_ref)
            )
            with ui.row().classes('gap-2'):
                ui.button('Add Supplier', icon='add', on_click=lambda: create_dialog.open()).props('color=primary')
                ui.button('Edit', icon='edit', on_click=lambda: _open_edit_dialog(selected_supplier, edit_dialog, edit_name_input)).props('flat').bind_enabled_from(selected_supplier, 'id', lambda x: x is not None)
                ui.button('Delete', icon='delete', on_click=lambda: delete_dialog.open()).props('flat color=negative').bind_enabled_from(selected_supplier, 'id', lambda x: x is not None)

        # Table
        columns = [
            {'name': 'idsupplier', 'label': 'ID', 'field': 'idsupplier', 'align': 'left', 'sortable': True},
            {'name': 'name', 'label': 'Name', 'field': 'name', 'align': 'left', 'sortable': True},
            {'name': 'product_count', 'label': 'Products', 'field': 'product_count', 'align': 'center'},
            {'name': 'facture_count', 'label': 'Factures', 'field': 'facture_count', 'align': 'center'},
        ]

        table_ref['table'] = ui.table(
            columns=columns,
            rows=[],
            row_key='idsupplier',
            selection='single',
            on_select=on_row_select
        ).classes('w-full')

        # Highlight row and name column for highlighted supplier
        table_ref['table'].add_slot('body-cell-name', '''
            <q-td :props="props" :class="props.row._highlighted ? 'bg-blue-100 dark:bg-blue-900' : ''">
                <span :class="props.row._highlighted ? 'font-bold text-blue-700 dark:text-blue-300' : ''">
                    {{ props.row.name }}
                </span>
                <q-badge v-if="props.row._highlighted" color="blue" class="q-ml-xs">VIEWING</q-badge>
            </q-td>
        ''')

        # Clickable product count - navigates to products page filtered by supplier
        table_ref['table'].add_slot('body-cell-product_count', '''
            <q-td :props="props" class="cursor-pointer">
                <a v-if="props.row.product_count > 0" class="text-primary hover:underline"
                   @click.stop="$parent.$emit('goto-products', props.row.idsupplier)">
                    {{ props.row.product_count }}
                </a>
                <span v-else class="text-grey-5">0</span>
            </q-td>
        ''')

        # Clickable facture count - navigates to factures page filtered by supplier
        table_ref['table'].add_slot('body-cell-facture_count', '''
            <q-td :props="props" class="cursor-pointer">
                <a v-if="props.row.facture_count > 0" class="text-primary hover:underline"
                   @click.stop="$parent.$emit('goto-factures', props.row.idsupplier)">
                    {{ props.row.facture_count }}
                </a>
                <span v-else class="text-grey-5">0</span>
            </q-td>
        ''')

        table_ref['table'].on('goto-products', lambda e: ui.navigate.to(f'/products?supplier={e.args}') if e.args else None)
        table_ref['table'].on('goto-factures', lambda e: ui.navigate.to(f'/factures?supplier={e.args}') if e.args else None)

        # Create dialog
        with ui.dialog() as create_dialog, ui.card().classes('p-4 min-w-96'):
            ui.label('Create Supplier').classes('text-lg font-semibold mb-4')
            create_name_input = ui.input(label='Supplier Name').classes('w-full')
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=create_dialog.close).props('flat')
                ui.button('Create', on_click=lambda: _handle_create(create_dialog, create_name_input, create_supplier)).props('color=primary')

        # Edit dialog
        with ui.dialog() as edit_dialog, ui.card().classes('p-4 min-w-96'):
            ui.label('Edit Supplier').classes('text-lg font-semibold mb-4')
            edit_name_input = ui.input(label='Supplier Name').classes('w-full')
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=edit_dialog.close).props('flat')
                ui.button('Save', on_click=lambda: _handle_update(edit_dialog, edit_name_input, update_supplier)).props('color=primary')

        # Delete confirmation dialog
        with ui.dialog() as delete_dialog, ui.card().classes('p-4'):
            ui.label('Delete Supplier?').classes('text-lg font-semibold')
            ui.label('This action cannot be undone. Products and factures linked to this supplier may be affected.').classes('text-gray-600 my-4')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=delete_dialog.close).props('flat')
                ui.button('Delete', on_click=lambda: _handle_delete(delete_dialog, delete_supplier)).props('color=negative')

        # Load data on page load
        load_suppliers()


def _handle_create(dialog, name_input, callback):
    dialog.close()
    callback({'name': name_input.value})
    name_input.value = ''


def _handle_update(dialog, name_input, callback):
    dialog.close()
    callback({'name': name_input.value})


def _handle_delete(dialog, callback):
    dialog.close()
    callback()


def _open_edit_dialog(selected, dialog, name_input):
    if selected['id']:
        name_input.value = selected.get('name', '')
        dialog.open()


def _search_suppliers(query, table_ref):
    if query:
        results = SupplierService.search(query)
    else:
        results = SupplierService.get_all_with_counts()
    if table_ref['table']:
        table_ref['table'].update_rows(results)
