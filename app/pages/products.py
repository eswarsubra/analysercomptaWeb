from nicegui import ui
from app.components.layout import layout
from app.services import ProductService, SupplierService


@ui.page('/products')
def products_page():
    """Products management page."""

    # State
    products_data = []
    selected_product = {'id': None, 'data': None}
    table_ref = {'table': None}
    filters = {'supplier': None, 'category': None}

    # Get supplier filter from URL if present
    query_string = ui.context.client.request.query_params
    if 'supplier' in query_string:
        try:
            filters['supplier'] = int(query_string['supplier'])
        except (ValueError, TypeError):
            pass

    def load_products():
        nonlocal products_data
        products_data = ProductService.get_all(
            supplier_id=filters['supplier'],
            category=filters['category']
        )
        if table_ref['table']:
            table_ref['table'].update_rows(products_data)

    def create_product(values):
        try:
            ProductService.create(
                code=values['code'],
                designation=values['designation'],
                unitprice=float(values['unitprice']) if values['unitprice'] else 0,
                tva=values.get('tva'),
                category=values.get('category'),
                idsupplier=int(values['idsupplier']) if values.get('idsupplier') else None
            )
            ui.notify('Product created', type='positive')
            load_products()
        except Exception as e:
            ui.notify(f'Error: {e}', type='negative')

    def update_product(values):
        if selected_product['id']:
            try:
                ProductService.update(
                    selected_product['id'],
                    code=values['code'],
                    designation=values['designation'],
                    unitprice=float(values['unitprice']) if values['unitprice'] else 0,
                    tva=values.get('tva'),
                    category=values.get('category'),
                    idsupplier=int(values['idsupplier']) if values.get('idsupplier') else None
                )
                ui.notify('Product updated', type='positive')
                load_products()
            except Exception as e:
                ui.notify(f'Error: {e}', type='negative')

    def delete_product():
        if selected_product['id']:
            try:
                ProductService.delete(selected_product['id'])
                ui.notify('Product deleted', type='positive')
                selected_product['id'] = None
                selected_product['data'] = None
                load_products()
            except Exception as e:
                ui.notify(f'Cannot delete: {e}', type='negative')

    def on_row_select(e):
        if e.selection:
            selected_product['id'] = e.selection[0]['idsupplierproduct']
            selected_product['data'] = e.selection[0]
        else:
            selected_product['id'] = None
            selected_product['data'] = None

    def on_supplier_filter(value):
        filters['supplier'] = value
        load_products()

    def on_category_filter(value):
        filters['category'] = value
        load_products()

    with layout('Products'):
        # Load suppliers for dropdown
        suppliers = SupplierService.get_all()
        supplier_options = {s['idsupplier']: s['name'] for s in suppliers}
        categories = ProductService.get_categories()

        # Toolbar
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('gap-4'):
                ui.input(placeholder='Search code or designation...').classes('w-64').on(
                    'keyup.enter',
                    lambda e: _search_products(e.sender.value, table_ref)
                )
                ui.select(
                    label='Supplier',
                    options={None: 'All', **supplier_options},
                    value=filters['supplier'],
                    on_change=lambda e: on_supplier_filter(e.value)
                ).classes('w-48')
                ui.select(
                    label='Category',
                    options=[None] + categories,
                    value=None,
                    on_change=lambda e: on_category_filter(e.value)
                ).classes('w-40').props('clearable')

            with ui.row().classes('gap-2'):
                ui.button('Add Product', icon='add', on_click=lambda: _open_create_dialog(create_dialog, create_fields)).props('color=primary')
                ui.button('Edit', icon='edit', on_click=lambda: _open_edit_dialog(selected_product, edit_dialog, edit_fields)).props('flat')
                ui.button('Delete', icon='delete', on_click=lambda: delete_dialog.open()).props('flat color=negative')

        # Table
        columns = [
            {'name': 'code', 'label': 'Code', 'field': 'code', 'align': 'left', 'sortable': True},
            {'name': 'designation', 'label': 'Designation', 'field': 'designation', 'align': 'left', 'sortable': True},
            {'name': 'unitprice', 'label': 'Unit Price', 'field': 'unitprice', 'align': 'right', 'sortable': True},
            {'name': 'tva', 'label': 'TVA', 'field': 'tva', 'align': 'center'},
            {'name': 'category', 'label': 'Category', 'field': 'category', 'align': 'left'},
            {'name': 'supplier_name', 'label': 'Supplier', 'field': 'supplier_name', 'align': 'left'},
        ]

        table_ref['table'] = ui.table(
            columns=columns,
            rows=[],
            row_key='idsupplierproduct',
            selection='single',
            on_select=on_row_select,
            pagination=20
        ).classes('w-full')

        # Clickable supplier name - navigates to supplier page
        table_ref['table'].add_slot('body-cell-supplier_name', '''
            <q-td :props="props" class="cursor-pointer">
                <a v-if="props.row.supplier_name" class="text-primary hover:underline"
                   @click.stop="$parent.$emit('goto-supplier', props.row.idsupplier)">
                    {{ props.row.supplier_name }}
                </a>
                <span v-else class="text-grey-5">-</span>
            </q-td>
        ''')

        table_ref['table'].on('goto-supplier', lambda e: ui.navigate.to(f'/suppliers?highlight={e.args}') if e.args else None)

        # Create dialog
        create_fields = {}
        with ui.dialog() as create_dialog, ui.card().classes('p-4 min-w-[500px]'):
            ui.label('Create Product').classes('text-lg font-semibold mb-4')
            with ui.column().classes('w-full gap-2'):
                create_fields['code'] = ui.input(label='Code').classes('w-full')
                create_fields['designation'] = ui.input(label='Designation').classes('w-full')
                with ui.row().classes('w-full gap-4'):
                    create_fields['unitprice'] = ui.number(label='Unit Price', value=0).classes('flex-1')
                    create_fields['tva'] = ui.select(label='TVA', options=['5.5', '20']).classes('flex-1')
                with ui.row().classes('w-full gap-4'):
                    create_fields['category'] = ui.input(label='Category').classes('flex-1')
                    create_fields['idsupplier'] = ui.select(label='Supplier', options=supplier_options).classes('flex-1')
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=create_dialog.close).props('flat')
                ui.button('Create', on_click=lambda: _handle_create(create_dialog, create_fields, create_product)).props('color=primary')

        # Edit dialog
        edit_fields = {}
        with ui.dialog() as edit_dialog, ui.card().classes('p-4 min-w-[500px]'):
            ui.label('Edit Product').classes('text-lg font-semibold mb-4')
            with ui.column().classes('w-full gap-2'):
                edit_fields['code'] = ui.input(label='Code').classes('w-full')
                edit_fields['designation'] = ui.input(label='Designation').classes('w-full')
                with ui.row().classes('w-full gap-4'):
                    edit_fields['unitprice'] = ui.number(label='Unit Price', value=0).classes('flex-1')
                    edit_fields['tva'] = ui.select(label='TVA', options=['5.5', '20']).classes('flex-1')
                with ui.row().classes('w-full gap-4'):
                    edit_fields['category'] = ui.input(label='Category').classes('flex-1')
                    edit_fields['idsupplier'] = ui.select(label='Supplier', options=supplier_options).classes('flex-1')
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=edit_dialog.close).props('flat')
                ui.button('Save', on_click=lambda: _handle_update(edit_dialog, edit_fields, update_product)).props('color=primary')

        # Delete dialog
        with ui.dialog() as delete_dialog, ui.card().classes('p-4'):
            ui.label('Delete Product?').classes('text-lg font-semibold')
            ui.label('This will remove the product from the catalog.').classes('text-gray-600 my-4')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=delete_dialog.close).props('flat')
                ui.button('Delete', on_click=lambda: _handle_delete(delete_dialog, delete_product)).props('color=negative')

        # Load initial data
        load_products()


def _handle_create(dialog, fields, callback):
    values = {k: v.value for k, v in fields.items()}
    dialog.close()
    callback(values)
    for f in fields.values():
        if hasattr(f, 'set_value'):
            f.set_value('' if isinstance(f.value, str) else 0)


def _handle_update(dialog, fields, callback):
    values = {k: v.value for k, v in fields.items()}
    dialog.close()
    callback(values)


def _handle_delete(dialog, callback):
    dialog.close()
    callback()


def _open_create_dialog(dialog, fields):
    for f in fields.values():
        if hasattr(f, 'set_value'):
            f.set_value('' if isinstance(f.value, str) else 0)
    dialog.open()


def _open_edit_dialog(selected, dialog, fields):
    if selected['data']:
        data = selected['data']
        fields['code'].value = data.get('code', '')
        fields['designation'].value = data.get('designation', '')
        fields['unitprice'].value = data.get('unitprice', 0)
        fields['tva'].value = data.get('tva')
        fields['category'].value = data.get('category', '')
        fields['idsupplier'].value = data.get('idsupplier')
        dialog.open()


def _search_products(query, table_ref):
    if query:
        results = ProductService.search(query)
    else:
        results = ProductService.get_all()
    if table_ref['table']:
        table_ref['table'].update_rows(results)
