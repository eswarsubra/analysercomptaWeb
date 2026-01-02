from nicegui import ui
from datetime import datetime
from app.components.layout import layout
from app.services import FactureService, SupplierService, ProductService
from app.database import get_db
from app.models import SupplierFacture, SupplierFactItem


@ui.page('/factures')
def factures_page():
    """Factures (invoices) management page."""

    # State
    factures_data = []
    table_ref = {'table': None}
    filters = {'supplier': None, 'date_from': None, 'date_to': None}
    current_facture = {'data': None}

    # Get supplier filter from URL if present
    query_string = ui.context.client.request.query_params
    if 'supplier' in query_string:
        try:
            filters['supplier'] = int(query_string['supplier'])
        except (ValueError, TypeError):
            pass

    # For create/edit forms
    form_data = {
        'idsupplier': None,
        'factNum': '',
        'factDate': '',
        'factmontantHT': 0,
        'factmontantTVA': 0,
        'factmontantttc': 0,
        'filename': '',
        'items': []
    }
    form_items = []  # List of line item widgets
    items_container = None
    products_by_supplier = {}

    def load_factures():
        nonlocal factures_data
        factures_data = FactureService.get_all(
            supplier_id=filters['supplier'],
            date_from=filters['date_from'],
            date_to=filters['date_to']
        )
        if table_ref['table']:
            table_ref['table'].update_rows(factures_data)

    def load_products_for_supplier(supplier_id):
        """Load products for the selected supplier."""
        if supplier_id:
            products = ProductService.get_all(supplier_id=supplier_id)
            products_by_supplier[supplier_id] = {p['idsupplierproduct']: f"{p['code']} - {p['designation'][:50]}" for p in products}
            return products_by_supplier[supplier_id]
        return {}

    def show_facture_detail(facture_id):
        facture = FactureService.get_by_id(facture_id)
        if facture:
            current_facture['data'] = facture
            detail_container.clear()
            with detail_container:
                _render_facture_detail(facture, detail_dialog)
            detail_dialog.open()

    def handle_selection(e):
        if e.selection:
            current_facture['data'] = e.selection[0]

    def on_supplier_filter(value):
        filters['supplier'] = value
        load_factures()

    def on_date_from_filter(value):
        filters['date_from'] = datetime.strptime(value, '%Y-%m-%d') if value else None
        load_factures()

    def on_date_to_filter(value):
        filters['date_to'] = datetime.strptime(value, '%Y-%m-%d') if value else None
        load_factures()

    def open_create_dialog():
        # Reset form
        form_data['idsupplier'] = None
        form_data['factNum'] = ''
        form_data['factDate'] = ''
        form_data['factmontantHT'] = 0
        form_data['factmontantTVA'] = 0
        form_data['factmontantttc'] = 0
        form_data['filename'] = ''
        form_data['items'] = []
        form_items.clear()

        create_supplier_select.value = None
        create_factnum_input.value = ''
        create_factdate_input.value = ''
        create_ht_input.value = 0
        create_tva_input.value = 0
        create_ttc_input.value = 0
        create_filename_input.value = ''

        create_items_container.clear()
        create_dialog.open()

    def open_edit_dialog():
        if not current_facture['data']:
            ui.notify('Select a facture first', type='warning')
            return

        # Load full facture with items
        facture = FactureService.get_by_id(current_facture['data']['idFacture'])
        if not facture:
            ui.notify('Facture not found', type='negative')
            return

        form_data['id'] = facture['idFacture']
        form_data['idsupplier'] = facture['idsupplier']
        form_data['items'] = facture.get('items', [])

        # Update dialog title with facture ID
        if edit_title_ref['label']:
            edit_title_ref['label'].set_text(f"Edit Facture (ID: {facture['idFacture']})")

        edit_supplier_select.value = facture['idsupplier']
        edit_factnum_input.value = facture['factNum']
        edit_factdate_input.value = facture['factDate'] or ''
        edit_ht_input.value = facture['factmontantHT']
        edit_tva_input.value = facture['factmontantTVA']
        edit_ttc_input.value = facture['factmontantttc']
        edit_filename_input.value = facture['filename'] or ''

        # Load products for this supplier
        load_products_for_supplier(facture['idsupplier'])

        # Populate items
        edit_items_container.clear()
        with edit_items_container:
            for item in facture.get('items', []):
                _add_item_row_edit(item, facture['idsupplier'])

        edit_dialog.open()

    def on_create_supplier_change(supplier_id):
        form_data['idsupplier'] = supplier_id
        load_products_for_supplier(supplier_id)
        # Clear items when supplier changes
        create_items_container.clear()
        form_items.clear()

    def add_create_item():
        if not form_data['idsupplier']:
            ui.notify('Select a supplier first', type='warning')
            return
        with create_items_container:
            _add_item_row_create(form_data['idsupplier'])

    def _add_item_row_create(supplier_id):
        """Add a new item row in create dialog."""
        products = products_by_supplier.get(supplier_id, {})
        item_data = {'product_id': None, 'quantity': 1, 'unitprice': 0, 'itemprice': 0}

        with ui.row().classes('w-full items-end gap-2 p-2 bg-gray-50 dark:bg-gray-800 rounded') as row:
            product_select = ui.select(
                label='Product',
                options=products,
                on_change=lambda e: _on_product_select_create(e.value, item_data, unitprice_input, supplier_id)
            ).classes('flex-1 min-w-[200px]')

            quantity_input = ui.number(
                label='Qty',
                value=1,
                min=0.01,
                on_change=lambda e: _calc_item_price(e.value, item_data, itemprice_input)
            ).classes('w-20')

            unitprice_input = ui.number(
                label='Unit Price',
                value=0,
                on_change=lambda e: _on_unitprice_change(e.value, item_data, quantity_input.value, itemprice_input)
            ).classes('w-28')

            itemprice_input = ui.number(
                label='Item Total',
                value=0
            ).classes('w-28').props('readonly')

            ui.button(icon='delete', on_click=lambda r=row: _remove_item_row(r)).props('flat color=negative')

            item_data['row'] = row
            item_data['product_select'] = product_select
            item_data['quantity_input'] = quantity_input
            item_data['unitprice_input'] = unitprice_input
            item_data['itemprice_input'] = itemprice_input
            form_items.append(item_data)

    def _add_item_row_edit(item, supplier_id):
        """Add an existing item row in edit dialog."""
        products = products_by_supplier.get(supplier_id, {})
        item_data = {
            'id': item.get('idsupplierfactitem'),
            'product_id': item.get('idsupplierproduct'),
            'quantity': item.get('quantity', 1),
            'unitprice': item.get('unitPriceSnap', 0),
            'itemprice': item.get('itemPrice', 0)
        }

        with ui.row().classes('w-full items-end gap-2 p-2 bg-gray-50 dark:bg-gray-800 rounded') as row:
            product_select = ui.select(
                label='Product',
                options=products,
                value=item.get('idsupplierproduct'),
                on_change=lambda e: _on_product_select_create(e.value, item_data, unitprice_input, supplier_id)
            ).classes('flex-1 min-w-[200px]')

            quantity_input = ui.number(
                label='Qty',
                value=item.get('quantity', 1),
                min=0.01,
                on_change=lambda e: _calc_item_price(e.value, item_data, itemprice_input)
            ).classes('w-20')

            unitprice_input = ui.number(
                label='Unit Price',
                value=item.get('unitPriceSnap', 0),
                on_change=lambda e: _on_unitprice_change(e.value, item_data, quantity_input.value, itemprice_input)
            ).classes('w-28')

            itemprice_input = ui.number(
                label='Item Total',
                value=item.get('itemPrice', 0)
            ).classes('w-28').props('readonly')

            ui.button(icon='delete', on_click=lambda r=row, d=item_data: _remove_item_row_edit(r, d)).props('flat color=negative')

            item_data['row'] = row
            item_data['product_select'] = product_select
            item_data['quantity_input'] = quantity_input
            item_data['unitprice_input'] = unitprice_input
            item_data['itemprice_input'] = itemprice_input
            form_items.append(item_data)

    def _on_product_select_create(product_id, item_data, unitprice_input, supplier_id):
        item_data['product_id'] = product_id
        # Get product unit price
        if product_id:
            product = ProductService.get_by_id(product_id)
            if product:
                item_data['unitprice'] = product['unitprice']
                unitprice_input.value = product['unitprice']

    def _on_unitprice_change(value, item_data, quantity, itemprice_input):
        item_data['unitprice'] = value or 0
        item_data['itemprice'] = (value or 0) * (quantity or 1)
        itemprice_input.value = item_data['itemprice']

    def _calc_item_price(quantity, item_data, itemprice_input):
        item_data['quantity'] = quantity or 1
        item_data['itemprice'] = (item_data.get('unitprice', 0) or 0) * (quantity or 1)
        itemprice_input.value = item_data['itemprice']

    def _remove_item_row(row):
        row.delete()
        form_items[:] = [i for i in form_items if i.get('row') != row]

    def _remove_item_row_edit(row, item_data):
        row.delete()
        form_items[:] = [i for i in form_items if i.get('row') != row]

    def save_create_facture():
        """Save new facture with items."""
        if not create_supplier_select.value:
            ui.notify('Select a supplier', type='warning')
            return
        if not create_factnum_input.value:
            ui.notify('Enter facture number', type='warning')
            return
        if not form_items:
            ui.notify('Add at least one item', type='warning')
            return

        try:
            with get_db() as db:
                # Create facture
                facture = SupplierFacture(
                    idsupplier=create_supplier_select.value,
                    factNum=create_factnum_input.value,
                    factDate=datetime.strptime(create_factdate_input.value, '%Y-%m-%d') if create_factdate_input.value else None,
                    factmontantHT=create_ht_input.value or 0,
                    factmontantTVA=create_tva_input.value or 0,
                    factmontantttc=create_ttc_input.value or 0,
                    filename=create_filename_input.value or None
                )
                db.add(facture)
                db.flush()

                # Create items
                for item in form_items:
                    if item.get('product_id'):
                        fact_item = SupplierFactItem(
                            idsupplier=create_supplier_select.value,
                            idsupplierfacture=facture.idFacture,
                            idsupplierproduct=item['product_id'],
                            quantity=item.get('quantity', 1),
                            itemPrice=item.get('itemprice', 0),
                            unitPriceSnap=item.get('unitprice', 0)
                        )
                        db.add(fact_item)

            ui.notify('Facture created successfully', type='positive')
            create_dialog.close()
            load_factures()
        except Exception as e:
            ui.notify(f'Error: {e}', type='negative')

    def save_edit_facture():
        """Save edited facture with items."""
        if not form_data.get('id'):
            ui.notify('No facture selected', type='warning')
            return

        try:
            with get_db() as db:
                # Update facture
                facture = db.query(SupplierFacture).filter(
                    SupplierFacture.idFacture == form_data['id']
                ).first()

                if facture:
                    facture.factNum = edit_factnum_input.value
                    facture.factDate = datetime.strptime(edit_factdate_input.value, '%Y-%m-%d') if edit_factdate_input.value else None
                    facture.factmontantHT = edit_ht_input.value or 0
                    facture.factmontantTVA = edit_tva_input.value or 0
                    facture.factmontantttc = edit_ttc_input.value or 0
                    facture.filename = edit_filename_input.value or None

                    # Delete existing items
                    db.query(SupplierFactItem).filter(
                        SupplierFactItem.idsupplierfacture == form_data['id']
                    ).delete()

                    # Create new items
                    for item in form_items:
                        if item.get('product_id'):
                            fact_item = SupplierFactItem(
                                idsupplier=facture.idsupplier,
                                idsupplierfacture=facture.idFacture,
                                idsupplierproduct=item['product_id'],
                                quantity=item.get('quantity', 1),
                                itemPrice=item.get('itemprice', 0),
                                unitPriceSnap=item.get('unitprice', 0)
                            )
                            db.add(fact_item)

            ui.notify('Facture updated successfully', type='positive')
            edit_dialog.close()
            load_factures()
        except Exception as e:
            ui.notify(f'Error: {e}', type='negative')

    def calc_totals_create():
        """Calculate totals from items."""
        total_ht = sum(item.get('itemprice', 0) or 0 for item in form_items)
        # Assuming 20% TVA by default
        total_tva = total_ht * 0.20
        total_ttc = total_ht + total_tva
        create_ht_input.value = round(total_ht, 2)
        create_tva_input.value = round(total_tva, 2)
        create_ttc_input.value = round(total_ttc, 2)

    def calc_totals_edit():
        """Calculate totals from items."""
        total_ht = sum(item.get('itemprice', 0) or 0 for item in form_items)
        total_tva = total_ht * 0.20
        total_ttc = total_ht + total_tva
        edit_ht_input.value = round(total_ht, 2)
        edit_tva_input.value = round(total_tva, 2)
        edit_ttc_input.value = round(total_ttc, 2)

    # Load suppliers for dropdowns
    suppliers = SupplierService.get_all()
    supplier_options = {s['idsupplier']: s['name'] for s in suppliers}

    # Detail dialog
    with ui.dialog() as detail_dialog:
        with ui.card().classes('w-[600px] max-h-[90vh] overflow-auto'):
            detail_container = ui.column().classes('w-full')

    # Create dialog
    with ui.dialog() as create_dialog:
        with ui.card().classes('w-[800px] max-h-[90vh] overflow-auto p-4'):
            ui.label('Create Facture').classes('text-xl font-bold mb-4')

            with ui.row().classes('w-full gap-4'):
                create_supplier_select = ui.select(
                    label='Supplier',
                    options=supplier_options,
                    on_change=lambda e: on_create_supplier_change(e.value)
                ).classes('flex-1')
                create_factnum_input = ui.input(label='Facture Number').classes('flex-1')

            with ui.row().classes('w-full gap-4'):
                with ui.input(label='Facture Date') as create_factdate_input:
                    with ui.menu().props('no-parent-event') as menu:
                        with ui.date(on_change=lambda e: create_factdate_input.set_value(e.value)):
                            pass
                    with create_factdate_input.add_slot('append'):
                        ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')
                create_filename_input = ui.input(label='Filename').classes('flex-1')

            ui.separator().classes('my-4')
            ui.label('Line Items').classes('font-semibold')

            with ui.row().classes('w-full gap-2 mb-2'):
                ui.button('Add Item', icon='add', on_click=add_create_item).props('outline')
                ui.button('Calculate Totals', icon='calculate', on_click=calc_totals_create).props('outline')

            create_items_container = ui.column().classes('w-full gap-2')

            ui.separator().classes('my-4')
            ui.label('Totals').classes('font-semibold')

            with ui.row().classes('w-full gap-4'):
                create_ht_input = ui.number(label='Total HT', value=0).classes('flex-1')
                create_tva_input = ui.number(label='Total TVA', value=0).classes('flex-1')
                create_ttc_input = ui.number(label='Total TTC', value=0).classes('flex-1')

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=create_dialog.close).props('flat')
                ui.button('Create', on_click=save_create_facture).props('color=primary')

    # Edit dialog
    edit_title_ref = {'label': None}
    with ui.dialog() as edit_dialog:
        with ui.card().classes('w-[800px] max-h-[90vh] overflow-auto p-4'):
            edit_title_ref['label'] = ui.label('Edit Facture').classes('text-xl font-bold mb-4')

            with ui.row().classes('w-full gap-4'):
                edit_supplier_select = ui.select(
                    label='Supplier',
                    options=supplier_options
                ).classes('flex-1').props('disable')
                edit_factnum_input = ui.input(label='Facture Number').classes('flex-1')

            with ui.row().classes('w-full gap-4'):
                with ui.input(label='Facture Date') as edit_factdate_input:
                    with ui.menu().props('no-parent-event') as menu:
                        with ui.date(on_change=lambda e: edit_factdate_input.set_value(e.value)):
                            pass
                    with edit_factdate_input.add_slot('append'):
                        ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')
                edit_filename_input = ui.input(label='Filename').classes('flex-1')

            ui.separator().classes('my-4')
            ui.label('Line Items').classes('font-semibold')

            with ui.row().classes('w-full gap-2 mb-2'):
                def add_edit_item():
                    if not edit_supplier_select.value:
                        return
                    with edit_items_container:
                        _add_item_row_edit({}, edit_supplier_select.value)
                ui.button('Add Item', icon='add', on_click=add_edit_item).props('outline')
                ui.button('Calculate Totals', icon='calculate', on_click=calc_totals_edit).props('outline')

            edit_items_container = ui.column().classes('w-full gap-2')

            ui.separator().classes('my-4')
            ui.label('Totals').classes('font-semibold')

            with ui.row().classes('w-full gap-4'):
                edit_ht_input = ui.number(label='Total HT', value=0).classes('flex-1')
                edit_tva_input = ui.number(label='Total TVA', value=0).classes('flex-1')
                edit_ttc_input = ui.number(label='Total TTC', value=0).classes('flex-1')

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=edit_dialog.close).props('flat')
                ui.button('Save', on_click=save_edit_facture).props('color=primary')

    with layout('Factures'):
        # Filters toolbar
        with ui.row().classes('w-full items-end gap-4 mb-4'):
            ui.select(
                label='Supplier',
                options={None: 'All Suppliers', **supplier_options},
                value=filters['supplier'],
                on_change=lambda e: on_supplier_filter(e.value)
            ).classes('w-48')

            with ui.input(label='From Date') as date_from:
                with ui.menu().props('no-parent-event') as menu:
                    with ui.date(on_change=lambda e: (date_from.set_value(e.value), on_date_from_filter(e.value))):
                        pass
                with date_from.add_slot('append'):
                    ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')

            with ui.input(label='To Date') as date_to:
                with ui.menu().props('no-parent-event') as menu:
                    with ui.date(on_change=lambda e: (date_to.set_value(e.value), on_date_to_filter(e.value))):
                        pass
                with date_to.add_slot('append'):
                    ui.icon('edit_calendar').on('click', menu.open).classes('cursor-pointer')

            ui.button('Clear Filters', icon='clear', on_click=lambda: _clear_filters(filters, load_factures)).props('flat')

        # Action buttons
        with ui.row().classes('w-full gap-2 mb-4'):
            ui.button('Create Facture', icon='add', on_click=open_create_dialog).props('color=primary')
            ui.button('Edit', icon='edit', on_click=open_edit_dialog).props('flat')
            ui.button('View Details', icon='visibility', on_click=lambda: show_facture_detail(current_facture['data']['idFacture']) if current_facture['data'] else ui.notify('Select a facture', type='warning')).props('flat')

        # Table
        columns = [
            {'name': 'idFacture', 'label': 'ID', 'field': 'idFacture', 'align': 'left', 'sortable': True},
            {'name': 'factNum', 'label': 'Invoice #', 'field': 'factNum', 'align': 'left', 'sortable': True},
            {'name': 'supplier_name', 'label': 'Supplier', 'field': 'supplier_name', 'align': 'left', 'sortable': True},
            {'name': 'factDate', 'label': 'Date', 'field': 'factDate', 'align': 'left', 'sortable': True},
            {'name': 'factmontantHT', 'label': 'HT', 'field': 'factmontantHT', 'align': 'right'},
            {'name': 'factmontantTVA', 'label': 'TVA', 'field': 'factmontantTVA', 'align': 'right'},
            {'name': 'factmontantttc', 'label': 'TTC', 'field': 'factmontantttc', 'align': 'right'},
            {'name': 'filename', 'label': 'File', 'field': 'filename', 'align': 'left'},
        ]

        table_ref['table'] = ui.table(
            columns=columns,
            rows=[],
            row_key='idFacture',
            selection='single',
            pagination=20,
            on_select=handle_selection
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

        # Clickable facture number - opens detail view
        table_ref['table'].add_slot('body-cell-factNum', '''
            <q-td :props="props" class="cursor-pointer">
                <a class="text-primary font-medium hover:underline"
                   @click.stop="$parent.$emit('view-detail', props.row.idFacture)">
                    {{ props.row.factNum }}
                </a>
            </q-td>
        ''')

        table_ref['table'].on('goto-supplier', lambda e: ui.navigate.to(f'/suppliers?highlight={e.args}') if e.args else None)
        table_ref['table'].on('view-detail', lambda e: show_facture_detail(e.args) if e.args else None)

        ui.label('Select a row to edit or view details').classes('text-sm text-gray-500 mt-2')

        # Load initial data
        load_factures()


def _render_facture_detail(facture: dict, dialog):
    """Render facture detail in the dialog."""
    with ui.row().classes('w-full justify-between items-center'):
        ui.label(f"Facture Details (ID: {facture['idFacture']})").classes('text-xl font-bold')
        ui.button(icon='close', on_click=dialog.close).props('flat round')

    ui.separator()

    with ui.card().classes('w-full'):
        with ui.grid(columns=2).classes('gap-4'):
            _detail_field('Facture ID', facture['idFacture'])
            _detail_field('Invoice #', facture['factNum'])
            _detail_field('Date', facture['factDate'])
            _detail_field('Supplier', facture['supplier_name'])
            _detail_field('File', facture['filename'])

    with ui.card().classes('w-full'):
        ui.label('Amounts').classes('font-semibold mb-2')
        with ui.row().classes('gap-8'):
            with ui.column():
                ui.label('HT').classes('text-sm text-gray-500')
                ui.label(f"{facture['factmontantHT']:,.2f} EUR").classes('text-lg font-bold text-blue-600')
            with ui.column():
                ui.label('TVA').classes('text-sm text-gray-500')
                ui.label(f"{facture['factmontantTVA']:,.2f} EUR").classes('text-lg font-bold text-amber-600')
            with ui.column():
                ui.label('TTC').classes('text-sm text-gray-500')
                ui.label(f"{facture['factmontantttc']:,.2f} EUR").classes('text-lg font-bold text-green-600')

    if facture.get('items'):
        with ui.card().classes('w-full'):
            ui.label('Line Items').classes('font-semibold mb-2')
            item_columns = [
                {'name': 'product_code', 'label': 'Code', 'field': 'product_code', 'align': 'left'},
                {'name': 'product_designation', 'label': 'Product', 'field': 'product_designation', 'align': 'left'},
                {'name': 'quantity', 'label': 'Qty', 'field': 'quantity', 'align': 'right'},
                {'name': 'unitPriceSnap', 'label': 'Unit', 'field': 'unitPriceSnap', 'align': 'right'},
                {'name': 'itemPrice', 'label': 'Total', 'field': 'itemPrice', 'align': 'right'},
            ]
            ui.table(
                columns=item_columns,
                rows=facture['items'],
                row_key='idsupplierfactitem'
            ).classes('w-full')


def _detail_field(label: str, value):
    with ui.column().classes('gap-0'):
        ui.label(label).classes('text-xs text-gray-500')
        ui.label(str(value) if value else '-').classes('font-medium')


def _clear_filters(filters, reload_callback):
    filters['supplier'] = None
    filters['date_from'] = None
    filters['date_to'] = None
    reload_callback()
