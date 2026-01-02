from nicegui import ui
from app.components.layout import layout
from app.services import NewProductsService, SupplierService, ProductService
from app.models.supplier_newproducts import NEWPRODUCT_STATUS_CHOICES
from app.logging_config import get_logger

logger = get_logger(__name__)


# Status colors for visual distinction
STATUS_COLORS = {
    'CLOSED': 'positive',
    'CREATE PRODUCT': 'primary',
    'IGNORE PRODUCT': 'warning',
    'FULL IGNORE': 'negative',
    'OBSOLETE': 'grey',
    'INCOMPLETE': 'pink'
}


@ui.page('/review')
def review_page():
    """New Products Review page - core screen for managing staging table with inline editing."""

    # State
    products_data = []
    selected_rows = []
    modified_rows = {}  # Track modified rows: {row_id: {field: value}}
    pending_duplicates = []  # Track new duplicated rows not yet saved
    temp_id_counter = {'value': -1}  # Negative IDs for unsaved duplicates
    table_ref = {'table': None}
    filters = {'status': None, 'supplier': None, 'facture': None, 'exclude_closed': True}
    products_cache = {}  # Cache products by supplier for product selector
    save_btn_ref = {'btn': None}
    changes_label_ref = {'label': None}
    save_bar_ref = {'bar': None}
    inconsistent_rows = set()  # Track rows flagged as inconsistent

    def load_products():
        nonlocal products_data
        products_data = NewProductsService.get_all(
            status=filters['status'],
            supplier_id=filters['supplier'],
            facture_id=filters['facture'],
            exclude_closed=filters['exclude_closed']
        )
        # Check for product consistency and auto-flag inconsistent rows
        check_and_flag_inconsistent()
        if table_ref['table']:
            table_ref['table'].update_rows(products_data)
        update_stats()

    def check_and_flag_inconsistent():
        """Check for product consistency issues and auto-flag rows."""
        nonlocal products_data
        inconsistent_rows.clear()

        # Get inconsistent records from service
        inconsistent = NewProductsService.check_product_consistency(
            facture_id=filters['facture'],
            supplier_id=filters['supplier'],
            exclude_closed=filters['exclude_closed']
        )

        if not inconsistent:
            return

        # Build lookup for quick access
        inconsistent_lookup = {item['idsuppliernewproducts']: item['existing_product_id']
                               for item in inconsistent}

        flagged_count = 0
        for row in products_data:
            row_id = row['idsuppliernewproducts']
            if row_id in inconsistent_lookup:
                existing_product_id = inconsistent_lookup[row_id]

                # Mark row as inconsistent for visual highlighting
                row['_inconsistent'] = True
                inconsistent_rows.add(row_id)

                # Auto-update status and misc (track as pending changes)
                new_status = 'IGNORE PRODUCT'
                new_misc = f"Product Reference ID:{existing_product_id}-"

                # Update row data for display
                row['Status'] = new_status
                row['misc'] = new_misc

                # Track changes for save
                if row_id not in modified_rows:
                    modified_rows[row_id] = {}
                modified_rows[row_id]['Status'] = new_status
                modified_rows[row_id]['misc'] = new_misc

                flagged_count += 1

        if flagged_count > 0:
            ui.notify(f"Auto-flagged {flagged_count} row(s) with existing products - review and save changes",
                      type='warning', timeout=5000)
            update_save_button()

    def refresh_table_with_pending():
        """Refresh table including pending (unsaved) duplicates."""
        nonlocal products_data
        products_data = NewProductsService.get_all(
            status=filters['status'],
            supplier_id=filters['supplier'],
            facture_id=filters['facture'],
            exclude_closed=filters['exclude_closed']
        )
        # Add pending duplicates to the display (at the top)
        for dup in pending_duplicates:
            dup['_duplicated'] = True  # Mark as new/unsaved
        all_rows = pending_duplicates + products_data
        if table_ref['table']:
            table_ref['table'].update_rows(all_rows)
        update_stats()

    def update_stats():
        counts = NewProductsService.get_status_counts()
        pending = NewProductsService.get_pending_count()
        stats_label.set_text(f"Pending: {pending} | " + " | ".join([f"{k}: {v}" for k, v in counts.items() if k not in ['CLOSED', 'OBSOLETE']]))

    def on_selection_change(e):
        nonlocal selected_rows
        selected_rows = e.selection if e.selection else []
        selection_label.set_text(f"Selected: {len(selected_rows)}")

    def create_pending_duplicate(source_row):
        """Create an in-memory duplicate that will be saved later."""
        temp_id_counter['value'] -= 1
        temp_id = temp_id_counter['value']

        duplicate = {
            'idsuppliernewproducts': temp_id,  # Temporary negative ID
            'code': source_row.get('code'),
            'designation': source_row.get('designation'),
            'unitprice': source_row.get('unitprice'),
            'tva': source_row.get('tva'),
            'category': source_row.get('category'),
            'misc': source_row.get('misc'),
            'quantity': source_row.get('quantity'),
            'ItemPrice': source_row.get('ItemPrice'),
            'Status': 'CREATE PRODUCT',  # Default status for duplicates
            'idFacture': source_row.get('idFacture'),
            'idsupplier': source_row.get('idsupplier'),
            'supplier_name': source_row.get('supplier_name', 'Unknown'),
            '_duplicated': True,
            '_is_new': True,  # Flag to identify unsaved rows
        }
        return duplicate

    def duplicate_selected():
        if selected_rows:
            for row in selected_rows:
                duplicate = create_pending_duplicate(row)
                pending_duplicates.append(duplicate)
            ui.notify(f"Duplicated {len(selected_rows)} row(s) - click 'Save All Changes' to persist", type='info')
            refresh_table_with_pending()
            update_save_button()

    def bulk_change_status(status):
        if selected_rows:
            ids = [r['idsuppliernewproducts'] for r in selected_rows]
            NewProductsService.bulk_update_status(ids, status)
            ui.notify(f"Updated {len(ids)} row(s) to {status}", type='positive')
            load_products()

    def resolve_pending():
        try:
            facture_id = filters['facture'] if filters['facture'] else None
            stats = NewProductsService.resolve_anomalies(facture_id)
            dups = stats.get('duplicates_converted', 0)
            full_ign = stats.get('full_ignored', 0)
            parts = []
            if stats['created'] > 0:
                parts.append(f"{stats['created']} New Product&FactItem Created")
            if stats['ignored'] > 0:
                parts.append(f"{stats['ignored']} Product exists-FactItem created")
            if full_ign > 0:
                parts.append(f"{full_ign} Product&FactItems created during Ingestion, Nothing to do")
            if dups > 0:
                parts.append(f"{dups} duplicates auto-linked")
            if stats['errors'] > 0:
                parts.append(f"{stats['errors']} errors")
            msg = "Resolved: " + ", ".join(parts) if parts else "Nothing to resolve"
            ui.notify(msg, type='positive')
            load_products()
        except Exception as e:
            ui.notify(f"Error: {e}", type='negative')

    def undo_facture():
        if filters['facture']:
            try:
                NewProductsService.undo_facture(filters['facture'])
                ui.notify(f"Facture {filters['facture']} undone", type='positive')
                load_products()
            except Exception as e:
                ui.notify(f"Error: {e}", type='negative')
        else:
            ui.notify("Select a facture first", type='warning')

    def purge_closed():
        try:
            count = NewProductsService.purge_closed()
            ui.notify(f"Purged {count} CLOSED record(s)", type='positive')
            load_products()
        except Exception as e:
            ui.notify(f"Error: {e}", type='negative')

    def track_change(row_id, field, value):
        """Track a field change for later bulk save."""
        # Check if this is a pending duplicate (negative ID)
        if row_id < 0:
            # Update the pending duplicate directly
            for dup in pending_duplicates:
                if dup['idsuppliernewproducts'] == row_id:
                    dup[field] = value
                    break
        else:
            # Track change for existing row
            if row_id not in modified_rows:
                modified_rows[row_id] = {}
            modified_rows[row_id][field] = value
        update_save_button()

    def update_save_button():
        """Update the save button visibility and label."""
        modified_count = len(modified_rows)
        new_count = len(pending_duplicates)
        inconsistent_count = len(inconsistent_rows)
        total = modified_count + new_count

        if save_btn_ref['btn'] and save_bar_ref['bar']:
            if total > 0:
                parts = []
                if inconsistent_count > 0:
                    parts.append(f"{inconsistent_count} auto-synced")
                if modified_count - inconsistent_count > 0:
                    parts.append(f"{modified_count - inconsistent_count} modified")
                if new_count > 0:
                    parts.append(f"{new_count} new")
                changes_label_ref['label'].set_text(f"{' + '.join(parts)} row(s)")
                save_bar_ref['bar'].set_visibility(True)
                save_btn_ref['btn'].set_visibility(True)
                changes_label_ref['label'].set_visibility(True)
            else:
                save_bar_ref['bar'].set_visibility(False)
                save_btn_ref['btn'].set_visibility(False)
                changes_label_ref['label'].set_visibility(False)

    def save_all_changes():
        """Save all modified rows and new duplicates to the database."""
        if not modified_rows and not pending_duplicates:
            ui.notify('No changes to save', type='info')
            return

        errors = 0
        saved = 0
        created = 0

        # Save modified rows
        for row_id, changes in modified_rows.items():
            try:
                NewProductsService.update(row_id, **changes)
                saved += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error saving row {row_id}: {e}")

        # Create new duplicates
        for dup in pending_duplicates:
            try:
                # Remove internal tracking fields before saving
                save_data = {k: v for k, v in dup.items()
                            if not k.startswith('_') and k not in ['idsuppliernewproducts', 'supplier_name']}
                NewProductsService.create(**save_data)
                created += 1
            except Exception as e:
                errors += 1
                logger.error(f"Error creating duplicate: {e}")

        modified_rows.clear()
        pending_duplicates.clear()
        inconsistent_rows.clear()
        update_save_button()

        results = []
        if saved > 0:
            results.append(f"{saved} updated")
        if created > 0:
            results.append(f"{created} created")
        if errors > 0:
            results.append(f"{errors} errors")

        if errors > 0:
            ui.notify(f"Saved: {', '.join(results)}", type='warning')
        else:
            ui.notify(f"Saved: {', '.join(results)}", type='positive')
        load_products()

    def discard_changes():
        """Discard all pending changes including unsaved duplicates."""
        modified_rows.clear()
        pending_duplicates.clear()
        inconsistent_rows.clear()
        update_save_button()
        load_products()
        ui.notify('Changes discarded', type='info')

    def get_products_for_supplier(supplier_id):
        """Get products for a supplier (with caching)."""
        if not supplier_id:
            return {}
        if supplier_id not in products_cache:
            products = ProductService.get_all(supplier_id=int(supplier_id))
            products_cache[supplier_id] = {
                str(p['idsupplierproduct']): f"{p['code']} - {p['designation'][:40]}"
                for p in products
            }
        return products_cache[supplier_id]

    with layout('Review Pending Products'):
        # Get filter options
        suppliers = SupplierService.get_all()
        supplier_options = {None: 'All Suppliers'}
        supplier_options.update({s['idsupplier']: s['name'] for s in suppliers})

        facture_ids = NewProductsService.get_facture_ids()
        facture_options = {None: 'All Factures'}
        facture_options.update({f: f"Facture #{f}" for f in facture_ids})

        status_options = {None: 'All Status'}
        status_options.update({s: s for s in NEWPRODUCT_STATUS_CHOICES})

        # Filter bar
        with ui.card().classes('w-full mb-4'):
            with ui.row().classes('w-full items-end gap-4 flex-wrap'):
                # Status filter chips
                with ui.row().classes('gap-2 items-center'):
                    ui.label('Status:').classes('text-sm font-medium')
                    for status in NEWPRODUCT_STATUS_CHOICES:
                        color = STATUS_COLORS.get(status, 'grey')
                        ui.chip(
                            status,
                            color=color,
                            selectable=True,
                            on_click=lambda s=status: _toggle_status_filter(s, filters, load_products)
                        )

                ui.select(
                    label='Supplier',
                    options=supplier_options,
                    value=None,
                    on_change=lambda e: _set_filter('supplier', e.value, filters, load_products)
                ).classes('w-40')

                ui.select(
                    label='Facture',
                    options=facture_options,
                    value=None,
                    on_change=lambda e: _set_filter('facture', e.value, filters, load_products)
                ).classes('w-40')

                ui.checkbox(
                    'Hide Closed/Obsolete',
                    value=True,
                    on_change=lambda e: _set_filter('exclude_closed', e.value, filters, load_products)
                )

        # Action toolbar
        with ui.row().classes('w-full justify-between items-center mb-4'):
            with ui.row().classes('gap-2 items-center'):
                selection_label = ui.label('Selected: 0').classes('text-sm text-gray-600')
                ui.button('Duplicate', icon='content_copy', on_click=duplicate_selected).props('flat dense')
                ui.button('Change Status', icon='swap_horiz').props('flat dense')
                with ui.menu():
                    for status in NEWPRODUCT_STATUS_CHOICES:
                        ui.menu_item(status, on_click=lambda s=status: bulk_change_status(s))

            with ui.row().classes('gap-2'):
                ui.button('Resolve Pending', icon='check_circle', on_click=lambda: resolve_dialog.open()).props('color=primary')
                ui.button('Undo Facture', icon='undo', on_click=lambda: undo_dialog.open()).props('color=negative outlined')
                ui.button('Purge Closed', icon='delete_sweep', on_click=lambda: purge_dialog.open()).props('color=grey outlined')

        # Save changes bar (visible when there are pending changes)
        with ui.card().classes('w-full mb-4 bg-amber-50 dark:bg-amber-900') as save_bar:
            with ui.row().classes('w-full items-center justify-between'):
                with ui.row().classes('gap-2 items-center'):
                    ui.icon('edit_note', color='amber').classes('text-2xl')
                    changes_label_ref['label'] = ui.label('0 row(s) modified').classes('text-amber-800 dark:text-amber-200 font-medium')
                with ui.row().classes('gap-2'):
                    ui.button('Discard', icon='close', on_click=discard_changes).props('flat color=grey')
                    save_btn_ref['btn'] = ui.button('Save All Changes', icon='save', on_click=save_all_changes).props('color=primary')
            save_bar_ref['bar'] = save_bar
            save_bar.set_visibility(False)
            save_btn_ref['btn'].set_visibility(False)
            changes_label_ref['label'].set_visibility(False)

        # Stats bar
        stats_label = ui.label('Loading...').classes('text-sm text-gray-500 mb-2')

        ui.label('Click on any cell to edit inline. Changes are tracked and saved with "Save All Changes" button.').classes('text-xs text-gray-400 mb-2 italic')

        # Data table with inline editing via popup-edit
        columns = [
            {'name': 'idsuppliernewproducts', 'label': 'ID', 'field': 'idsuppliernewproducts', 'align': 'left', 'sortable': True},
            {'name': 'supplier_name', 'label': 'Supplier', 'field': 'supplier_name', 'align': 'left', 'sortable': True},
            {'name': 'code', 'label': 'Code', 'field': 'code', 'align': 'left', 'sortable': True},
            {'name': 'designation', 'label': 'Designation', 'field': 'designation', 'align': 'left'},
            {'name': 'unitprice', 'label': 'Unit Price', 'field': 'unitprice', 'align': 'right'},
            {'name': 'quantity', 'label': 'Qty', 'field': 'quantity', 'align': 'right'},
            {'name': 'ItemPrice', 'label': 'Item Price', 'field': 'ItemPrice', 'align': 'right'},
            {'name': 'tva', 'label': 'TVA', 'field': 'tva', 'align': 'center'},
            {'name': 'category', 'label': 'Category', 'field': 'category', 'align': 'left'},
            {'name': 'misc', 'label': 'Misc', 'field': 'misc', 'align': 'left'},
            {'name': 'Status', 'label': 'Status', 'field': 'Status', 'align': 'center'},
            {'name': 'idFacture', 'label': 'Facture', 'field': 'idFacture', 'align': 'center'},
            {'name': 'actions', 'label': 'Actions', 'field': 'actions', 'align': 'center'},
        ]

        table_ref['table'] = ui.table(
            columns=columns,
            rows=[],
            row_key='idsuppliernewproducts',
            selection='multiple',
            on_select=on_selection_change,
            pagination=25
        ).classes('w-full')

        # ID column with duplicate/inconsistent highlight badge
        table_ref['table'].add_slot('body-cell-idsuppliernewproducts', '''
            <q-td :props="props" :class="props.row._inconsistent ? 'bg-orange-100 dark:bg-orange-900' : (props.row._duplicated ? 'bg-yellow-100 dark:bg-yellow-900' : '')">
                <span :class="props.row._inconsistent ? 'font-bold text-orange-700 dark:text-orange-300' : (props.row._duplicated ? 'font-bold text-yellow-700 dark:text-yellow-300' : '')">
                    {{ props.row.idsuppliernewproducts }}
                </span>
                <q-badge v-if="props.row._inconsistent" color="orange" text-color="white" class="q-ml-xs">
                    <q-icon name="warning" size="xs" class="q-mr-xs" />SYNC
                </q-badge>
                <q-badge v-else-if="props.row._duplicated" color="yellow" text-color="black" class="q-ml-xs">NEW</q-badge>
            </q-td>
        ''')

        # Clickable supplier name - navigates to supplier page
        table_ref['table'].add_slot('body-cell-supplier_name', '''
            <q-td :props="props" class="cursor-pointer">
                <a class="text-primary hover:underline" @click.stop="$parent.$emit('goto-supplier', props.row.idsupplier)">
                    {{ props.row.supplier_name || 'Unknown' }}
                </a>
            </q-td>
        ''')

        # Clickable facture ID - navigates to facture page
        table_ref['table'].add_slot('body-cell-idFacture', '''
            <q-td :props="props" class="cursor-pointer">
                <a v-if="props.row.idFacture" class="text-primary hover:underline"
                   @click.stop="$parent.$emit('goto-facture', props.row.idFacture)">
                    #{{ props.row.idFacture }}
                </a>
                <span v-else class="text-grey-5">-</span>
            </q-td>
        ''')

        # Inline editable cell for code
        table_ref['table'].add_slot('body-cell-code', '''
            <q-td :props="props" class="cursor-pointer">
                {{ props.row.code }}
                <q-popup-edit v-model="props.row.code" buttons v-slot="scope"
                    @save="(val) => $parent.$emit('update', {id: props.row.idsuppliernewproducts, field: 'code', value: val})">
                    <q-input v-model="scope.value" dense autofocus />
                </q-popup-edit>
            </q-td>
        ''')

        # Inline editable cell for designation
        table_ref['table'].add_slot('body-cell-designation', '''
            <q-td :props="props" class="cursor-pointer">
                {{ props.row.designation }}
                <q-popup-edit v-model="props.row.designation" buttons v-slot="scope"
                    @save="(val) => $parent.$emit('update', {id: props.row.idsuppliernewproducts, field: 'designation', value: val})">
                    <q-input v-model="scope.value" dense autofocus style="min-width: 300px" />
                </q-popup-edit>
            </q-td>
        ''')

        # Inline editable cell for unitprice
        table_ref['table'].add_slot('body-cell-unitprice', '''
            <q-td :props="props" class="cursor-pointer">
                {{ props.row.unitprice }}
                <q-popup-edit v-model="props.row.unitprice" buttons v-slot="scope"
                    @save="(val) => $parent.$emit('update', {id: props.row.idsuppliernewproducts, field: 'unitprice', value: val})">
                    <q-input v-model="scope.value" type="number" dense autofocus />
                </q-popup-edit>
            </q-td>
        ''')

        # Inline editable cell for quantity
        table_ref['table'].add_slot('body-cell-quantity', '''
            <q-td :props="props" class="cursor-pointer">
                {{ props.row.quantity }}
                <q-popup-edit v-model="props.row.quantity" buttons v-slot="scope"
                    @save="(val) => $parent.$emit('update', {id: props.row.idsuppliernewproducts, field: 'quantity', value: val})">
                    <q-input v-model="scope.value" type="number" dense autofocus />
                </q-popup-edit>
            </q-td>
        ''')

        # Inline editable cell for ItemPrice
        table_ref['table'].add_slot('body-cell-ItemPrice', '''
            <q-td :props="props" class="cursor-pointer">
                {{ props.row.ItemPrice }}
                <q-popup-edit v-model="props.row.ItemPrice" buttons v-slot="scope"
                    @save="(val) => $parent.$emit('update', {id: props.row.idsuppliernewproducts, field: 'ItemPrice', value: val})">
                    <q-input v-model="scope.value" type="number" dense autofocus />
                </q-popup-edit>
            </q-td>
        ''')

        # Inline editable cell for TVA with select
        table_ref['table'].add_slot('body-cell-tva', '''
            <q-td :props="props" class="cursor-pointer">
                {{ props.row.tva || '-' }}
                <q-popup-edit v-model="props.row.tva" buttons v-slot="scope"
                    @save="(val) => $parent.$emit('update', {id: props.row.idsuppliernewproducts, field: 'tva', value: val})">
                    <q-select v-model="scope.value" :options="['5.5', '20', '']" dense autofocus emit-value map-options />
                </q-popup-edit>
            </q-td>
        ''')

        # Inline editable cell for category
        table_ref['table'].add_slot('body-cell-category', '''
            <q-td :props="props" class="cursor-pointer">
                {{ props.row.category || '-' }}
                <q-popup-edit v-model="props.row.category" buttons v-slot="scope"
                    @save="(val) => $parent.$emit('update', {id: props.row.idsuppliernewproducts, field: 'category', value: val})">
                    <q-input v-model="scope.value" dense autofocus />
                </q-popup-edit>
            </q-td>
        ''')

        # Inline editable cell for misc with product selector hint
        table_ref['table'].add_slot('body-cell-misc', '''
            <q-td :props="props" class="cursor-pointer">
                <template v-if="props.row.misc">
                    <q-badge v-if="props.row.misc.includes('Already inserted')" color="green" outline>
                        <q-icon name="check_circle" size="xs" class="q-mr-xs" />
                        Already inserted
                    </q-badge>
                    <q-badge v-else-if="props.row.misc.includes('Product Reference ID')" color="blue" outline>
                        <q-icon name="link" size="xs" class="q-mr-xs" />
                        {{ props.row.misc }}
                    </q-badge>
                    <span v-else class="text-grey-7">{{ props.row.misc }}</span>
                </template>
                <span v-else class="text-grey-5">-</span>
                <q-popup-edit v-model="props.row.misc" buttons v-slot="scope"
                    @save="(val) => $parent.$emit('update', {id: props.row.idsuppliernewproducts, field: 'misc', value: val})">
                    <q-input v-model="scope.value" dense autofocus style="min-width: 250px"
                        hint="For product ref, use: Product Reference ID:{id}-" />
                    <q-btn flat dense color="primary" label="Select Product" class="q-mt-sm"
                        @click="$parent.$emit('select-product', {id: props.row.idsuppliernewproducts, supplier: props.row.idsupplier})" />
                </q-popup-edit>
            </q-td>
        ''')

        # Inline editable cell for Status with select dropdown
        table_ref['table'].add_slot('body-cell-Status', '''
            <q-td :props="props" class="cursor-pointer">
                <q-badge :color="props.row.Status === 'CLOSED' ? 'positive' :
                                 props.row.Status === 'CREATE PRODUCT' ? 'primary' :
                                 props.row.Status === 'IGNORE PRODUCT' ? 'warning' :
                                 props.row.Status === 'FULL IGNORE' ? 'negative' :
                                 props.row.Status === 'OBSOLETE' ? 'grey' : 'pink'">
                    {{ props.row.Status }}
                </q-badge>
                <q-popup-edit v-model="props.row.Status" buttons v-slot="scope"
                    @save="(val) => $parent.$emit('update', {id: props.row.idsuppliernewproducts, field: 'Status', value: val})">
                    <q-select v-model="scope.value"
                        :options="['CLOSED', 'CREATE PRODUCT', 'IGNORE PRODUCT', 'FULL IGNORE', 'OBSOLETE']"
                        dense autofocus emit-value map-options style="min-width: 180px" />
                </q-popup-edit>
            </q-td>
        ''')

        # Add slot for actions column
        table_ref['table'].add_slot('body-cell-actions', '''
            <q-td :props="props">
                <q-btn flat dense icon="content_copy" @click="$parent.$emit('duplicate', props.row)"
                    title="Duplicate row">
                    <q-tooltip>Duplicate row</q-tooltip>
                </q-btn>
            </q-td>
        ''')

        # Handle update events from inline edits
        def on_cell_update(e):
            data = e.args
            track_change(data['id'], data['field'], data['value'])

        table_ref['table'].on('update', on_cell_update)

        def handle_duplicate(e):
            row = e.args
            duplicate = create_pending_duplicate(row)
            pending_duplicates.append(duplicate)
            ui.notify("Row duplicated - click 'Save All Changes' to persist", type='info')
            refresh_table_with_pending()
            update_save_button()

        table_ref['table'].on('duplicate', handle_duplicate)

        # Navigation handlers
        def goto_supplier(e):
            supplier_id = e.args
            if supplier_id:
                ui.navigate.to(f'/suppliers?highlight={supplier_id}')

        def goto_facture(e):
            facture_id = e.args
            if facture_id:
                ui.navigate.to(f'/factures?highlight={facture_id}')

        table_ref['table'].on('goto-supplier', goto_supplier)
        table_ref['table'].on('goto-facture', goto_facture)

        # Product selector dialog
        product_select_data = {'row_id': None, 'supplier_id': None}
        with ui.dialog() as product_dialog, ui.card().classes('p-4 min-w-[500px]'):
            ui.label('Select Product Reference').classes('text-lg font-semibold mb-4')
            product_select_options = {}
            product_select = ui.select(
                label='Product',
                options=product_select_options,
                with_input=True
            ).classes('w-full')

            def on_product_confirm():
                if product_select.value:
                    row_id = product_select_data['row_id']
                    # Find current misc value to preserve content after the separator
                    current_misc = ''
                    for row in products_data:
                        if row['idsuppliernewproducts'] == row_id:
                            current_misc = row.get('misc', '') or ''
                            break
                    # Also check pending duplicates
                    for dup in pending_duplicates:
                        if dup['idsuppliernewproducts'] == row_id:
                            current_misc = dup.get('misc', '') or ''
                            break

                    # Build new misc: "Product Reference ID:{id}-" + preserved content
                    new_ref = f"Product Reference ID:{product_select.value}-"
                    # If there was existing content after "-", preserve it
                    if 'Product Reference ID:' in current_misc and '-' in current_misc:
                        existing_suffix = current_misc.split('-', 1)[1]
                        new_misc = new_ref + existing_suffix
                    else:
                        new_misc = new_ref

                    # Track the change
                    track_change(row_id, 'misc', new_misc)

                    # Also update the table row visually
                    for row in products_data:
                        if row['idsuppliernewproducts'] == row_id:
                            row['misc'] = new_misc
                            break
                    for dup in pending_duplicates:
                        if dup['idsuppliernewproducts'] == row_id:
                            dup['misc'] = new_misc
                            break
                    table_ref['table'].update_rows(pending_duplicates + products_data)
                    product_dialog.close()
                    ui.notify('Product reference set', type='positive')

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=product_dialog.close).props('flat')
                ui.button('Set Reference', on_click=on_product_confirm).props('color=primary')

        # Handle product selection request
        def on_select_product(e):
            data = e.args
            product_select_data['row_id'] = data['id']
            product_select_data['supplier_id'] = data['supplier']
            # Load products for this supplier
            products = get_products_for_supplier(data['supplier'])
            product_select.options = products
            product_select.value = None
            product_select.update()
            product_dialog.open()

        table_ref['table'].on('select-product', on_select_product)

        # Resolve confirmation dialog
        with ui.dialog() as resolve_dialog, ui.card().classes('p-4'):
            ui.label('Resolve Pending Items?').classes('text-lg font-semibold')
            ui.label('This will create products and facture items based on status.').classes('text-gray-600 my-4')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=resolve_dialog.close).props('flat')
                ui.button('Resolve', on_click=lambda: (resolve_dialog.close(), resolve_pending())).props('color=primary')

        # Undo facture dialog
        with ui.dialog() as undo_dialog, ui.card().classes('p-4'):
            ui.label('Undo Facture?').classes('text-lg font-semibold')
            ui.label('This will mark staging items as OBSOLETE and delete facture items. This cannot be undone!').classes('text-red-600 my-4')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=undo_dialog.close).props('flat')
                ui.button('Undo', on_click=lambda: (undo_dialog.close(), undo_facture())).props('color=negative')

        # Purge closed dialog
        with ui.dialog() as purge_dialog, ui.card().classes('p-4'):
            ui.label('Purge Closed Records?').classes('text-lg font-semibold')
            ui.label('This will permanently delete all records with STATUS = CLOSED. This cannot be undone!').classes('text-red-600 my-4')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=purge_dialog.close).props('flat')
                ui.button('Purge', icon='delete_sweep', on_click=lambda: (purge_dialog.close(), purge_closed())).props('color=negative')

        # Load initial data
        load_products()


def _toggle_status_filter(status, filters, reload_callback):
    """Toggle status filter."""
    if filters['status'] == status:
        filters['status'] = None
    else:
        filters['status'] = status
    reload_callback()


def _set_filter(key, value, filters, reload_callback):
    """Set a filter value and reload."""
    filters[key] = value
    reload_callback()


