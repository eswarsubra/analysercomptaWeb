"""Mobile Scan & Match page - scan receipts from phone and match to outbound transactions."""
import io
import os
import base64
import socket
import logging
from datetime import date
from dateutil.relativedelta import relativedelta

from nicegui import ui

from app.components.layout import layout
from app.services import OutboundMatchService, BankInstructionService, SupplierService
from app.services.mobile_scan_service import MobileScanService

logger = logging.getLogger(__name__)


def _get_server_url() -> str:
    """Build the base URL that a phone on the same LAN can reach."""
    host_ip = os.environ.get('SCAN_HOST_IP')
    if not host_ip:
        try:
            hostname = socket.gethostname()
            host_ip = socket.gethostbyname(hostname)
        except Exception:
            host_ip = '127.0.0.1'
    port = 8099 if os.environ.get('APP_ENV') == 'production' else 9090
    return f'http://{host_ip}:{port}'


def _generate_qr_base64(url: str) -> str:
    """Generate a QR code PNG as a base64 data URI."""
    import qrcode
    qr = qrcode.QRCode(version=1, box_size=8, border=3)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f'data:image/png;base64,{b64}'


@ui.page('/analytics/outbound/scan')
def mobile_scan_match_page():
    """Page for scanning receipts from phone and matching to transactions."""

    # Default to previous month
    today = date.today()
    last_month = today.replace(day=1) - relativedelta(months=1)
    default_month = last_month.month
    default_year = last_month.year

    state = {
        'month': default_month,
        'year': default_year,
        'session_token': None,
        'receipts': [],          # from MobileScanService polling
        'transactions': [],      # unmatched outbound transactions for matching scope
        'suppliers': [],         # all suppliers for dropdowns
        'pairings': [],          # [{receipt, transaction, confirmed}]
        'poll_active': False,
    }

    refs = {
        'qr_dialog': None,
        'qr_counter_label': None,
        'qr_receipts_container': None,
        'poll_timer': None,
        'match_dialog': None,
        'match_dialog_card': None,
        'pairings_container': None,
    }

    # Pre-create the matching dialog at page level so it is NOT a child of
    # the QR dialog (which would hide it when closed).
    match_dialog = ui.dialog().props('persistent maximized=false')
    refs['match_dialog'] = match_dialog

    # ==================== DATA LOADING ====================

    def load_unmatched_transactions():
        """Load unmatched outbound transactions for the selected month(s)."""
        all_tx = OutboundMatchService.get_transactions_for_month(
            state['month'], state['year'],
        )
        state['transactions'] = [
            t for t in all_tx if t.get('match_status') == 'UNMATCHED'
        ]
        if not state['suppliers']:
            state['suppliers'] = SupplierService.get_all()

    # ==================== QR SCAN SESSION ====================

    def on_start_scan():
        """Create session, show QR code dialog."""
        # Load unmatched transactions for the selected month scope
        load_unmatched_transactions()
        if not state['transactions']:
            ui.notify(
                f"No unmatched transactions for {state['month']}/{state['year']}.",
                type='warning',
            )
            return

        token = MobileScanService.create_session()
        state['session_token'] = token
        state['receipts'] = []

        scan_url = f'{_get_server_url()}/mobile/scan/{token}'
        qr_data_uri = _generate_qr_base64(scan_url)

        show_qr_dialog(qr_data_uri, scan_url)

    def show_qr_dialog(qr_data_uri: str, scan_url: str):
        """Display the QR code dialog and start polling."""
        with ui.dialog() as qr_dialog, ui.card().classes('p-6 min-w-[500px]'):
            refs['qr_dialog'] = qr_dialog

            ui.label('Scan Receipts from Phone').classes('text-xl font-semibold mb-2')
            ui.label(
                'Scan the QR code with your phone camera. '
                'Take photos of receipts one by one. '
                'Click "Done Scanning" when finished.'
            ).classes('text-sm text-gray-500 mb-4')

            with ui.row().classes('w-full justify-center'):
                ui.image(qr_data_uri).classes('w-56 h-56')

            ui.label(scan_url).classes(
                'text-xs text-gray-400 text-center w-full mt-1 break-all'
            )

            ui.separator().classes('my-4')

            refs['qr_counter_label'] = ui.label('0 receipts scanned').classes(
                'text-lg font-semibold text-center w-full'
            )

            refs['qr_receipts_container'] = ui.column().classes('w-full gap-1 mt-2')

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=on_cancel_scan).props('flat')
                ui.button(
                    'Done Scanning', icon='check',
                    on_click=on_done_scanning,
                ).props('color=primary')

        qr_dialog.open()
        start_polling()

    def start_polling():
        """Start polling for new receipts from the mobile session."""
        state['poll_active'] = True

        async def poll():
            if not state['poll_active'] or not state['session_token']:
                return
            token = state['session_token']
            receipts = MobileScanService.get_receipts(token)

            # Detect any change: new receipts OR status updates (processing -> ready/error)
            changed = len(receipts) != len(state['receipts'])
            if not changed:
                for new, old in zip(receipts, state['receipts']):
                    if new.get('status') != old.get('status'):
                        changed = True
                        break

            if changed:
                state['receipts'] = receipts
                update_qr_dialog_receipts()

        refs['poll_timer'] = ui.timer(2.0, poll)

    def stop_polling():
        if refs['poll_timer']:
            refs['poll_timer'].cancel()
            refs['poll_timer'] = None
        state['poll_active'] = False

    def update_qr_dialog_receipts():
        """Update the receipt list in the QR dialog."""
        count = len(state['receipts'])
        if refs['qr_counter_label']:
            refs['qr_counter_label'].set_text(
                f'{count} receipt{"s" if count != 1 else ""} scanned'
            )
        container = refs['qr_receipts_container']
        if not container:
            return
        container.clear()
        with container:
            for r in reversed(state['receipts']):
                ocr = r.get('ocr_result') or {}
                status = r.get('status', 'processing')
                with ui.card().classes('w-full p-2'):
                    with ui.row().classes('items-center gap-2'):
                        if status == 'ready':
                            ui.icon('check_circle', color='green').classes('text-lg')
                        elif status == 'error':
                            ui.icon('error', color='red').classes('text-lg')
                        else:
                            ui.spinner(size='sm')
                        supplier = ocr.get('supplier_name', 'Processing...')
                        amount = ocr.get('amount_ttc')
                        label = supplier
                        if amount is not None:
                            label += f' - {amount:,.2f}'
                        ui.label(label).classes('text-sm')

    def on_cancel_scan():
        stop_polling()
        if state['session_token']:
            MobileScanService.invalidate(state['session_token'])
            state['session_token'] = None
        if refs['qr_dialog']:
            refs['qr_dialog'].close()

    def on_done_scanning():
        stop_polling()
        if refs['qr_dialog']:
            refs['qr_dialog'].close()

        # Refresh receipts one last time
        if state['session_token']:
            state['receipts'] = MobileScanService.get_receipts(state['session_token'])

        logger.info(
            f"Done scanning: {len(state['receipts'])} receipts, "
            f"statuses: {[r.get('status') for r in state['receipts']]}"
        )

        # Include both 'ready' (OCR success) and 'error' (OCR failed but image archived)
        usable_receipts = [
            r for r in state['receipts']
            if r.get('status') in ('ready', 'error')
        ]

        # Also include 'processing' receipts that may still be running OCR
        still_processing = [
            r for r in state['receipts']
            if r.get('status') == 'processing'
        ]
        if still_processing:
            logger.warning(
                f"{len(still_processing)} receipt(s) still processing at done time"
            )
            ui.notify(
                f'{len(still_processing)} receipt(s) still processing. '
                'They will be included with whatever data is available.',
                type='info',
            )
            usable_receipts.extend(still_processing)

        if not usable_receipts:
            ui.notify('No receipts were scanned.', type='warning')
            return

        # Reload unmatched transactions (in case some were matched meanwhile)
        try:
            load_unmatched_transactions()
        except Exception as e:
            logger.error(f"Failed to load unmatched transactions: {e}", exc_info=True)
            ui.notify(f'Error loading transactions: {e}', type='negative')
            return

        try:
            build_pairings(usable_receipts)
            show_matching_panel()
        except Exception as e:
            logger.error(f"Failed to build matching panel: {e}", exc_info=True)
            ui.notify(f'Error building matching panel: {e}', type='negative')

    # ==================== AUTO-MATCH & PAIRING ====================

    def build_pairings(receipts: list[dict]):
        """Auto-match scanned receipts to unmatched transactions by amount."""
        used_tx_ids = set()
        pairings = []

        for receipt in receipts:
            ocr = receipt.get('ocr_result') or {}
            receipt_amount = ocr.get('amount_ttc')
            best_tx = None
            best_diff = float('inf')

            if receipt_amount is not None:
                for tx in state['transactions']:
                    tx_id = tx['TransactionID']
                    if tx_id in used_tx_ids:
                        continue
                    # Compare absolute amounts (outbound are negative, receipt amounts positive)
                    tx_amount = abs(tx.get('Montant', 0))
                    diff = abs(tx_amount - abs(receipt_amount))
                    if diff < best_diff:
                        best_diff = diff
                        best_tx = tx

            if best_tx is not None:
                used_tx_ids.add(best_tx['TransactionID'])

            pairings.append({
                'receipt': receipt,
                'transaction': best_tx,
                'amount_diff': best_diff if best_tx else None,
                'confirmed': False,
            })

        state['pairings'] = pairings

    def show_matching_panel():
        """Populate and open the pre-created matching dialog."""
        unmatched_tx_options = {
            tx['TransactionID']: f"{tx.get('Date_operation', '')} | {tx.get('Libelle', '')[:40]} | {abs(tx.get('Montant', 0)):,.2f}"
            for tx in state['transactions']
        }

        match_dialog = refs['match_dialog']
        match_dialog.clear()

        with match_dialog, ui.card().classes('p-4 min-w-[900px] max-h-[80vh]'):
            ui.label('Match Scanned Receipts to Transactions').classes(
                'text-xl font-semibold mb-2'
            )
            ui.label(
                'Review the auto-suggested pairings below. '
                'Adjust if needed, then click Confirm All.'
            ).classes('text-sm text-gray-500 mb-4')

            refs['pairings_container'] = ui.column().classes('w-full gap-3')
            render_pairings(unmatched_tx_options)

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=match_dialog.close).props('flat')
                ui.button(
                    'Confirm All', icon='done_all',
                    on_click=on_confirm_all,
                ).props('color=primary')

        logger.info(f"Opening matching panel with {len(state['pairings'])} pairings")
        match_dialog.open()

    def render_pairings(tx_options: dict):
        """Render pairing cards in the matching panel."""
        container = refs['pairings_container']
        if not container:
            return
        container.clear()

        with container:
            for idx, pairing in enumerate(state['pairings']):
                receipt = pairing['receipt']
                ocr = receipt.get('ocr_result') or {}
                tx = pairing.get('transaction')
                diff = pairing.get('amount_diff')
                ocr_failed = receipt.get('status') == 'error'

                card_classes = 'w-full p-3'
                if ocr_failed:
                    card_classes += ' border-l-4 border-orange-400'

                with ui.card().classes(card_classes):
                    with ui.row().classes('w-full items-center gap-4'):
                        # Left: Receipt info
                        with ui.column().classes('flex-1'):
                            if ocr_failed:
                                ui.label('Scanned Receipt (OCR failed)').classes(
                                    'text-xs text-orange-600 font-medium'
                                )
                                archived = ocr.get('archived_filename', 'unknown')
                                ui.label(f'Image archived: {archived}').classes(
                                    'text-sm text-gray-500'
                                )
                                ui.label(
                                    'Will be linked as file justification'
                                ).classes('text-xs text-gray-400 italic')
                            else:
                                ui.label('Scanned Receipt').classes('text-xs text-gray-400')
                                supplier = ocr.get('supplier_name', 'Unknown')
                                amount_ttc = ocr.get('amount_ttc')
                                facture_num = ocr.get('facture_num', '')
                                facture_date = ocr.get('facture_date', '')
                                supplier_exists = _find_supplier_id(
                                    supplier, state['suppliers'],
                                ) is not None

                                with ui.row().classes('items-center gap-2'):
                                    ui.label(supplier).classes('font-semibold')
                                    if amount_ttc is not None:
                                        ui.badge(
                                            f'{amount_ttc:,.2f}', color='blue',
                                        ).classes('text-sm')
                                    if supplier and not supplier_exists:
                                        ui.badge(
                                            'New supplier', color='teal',
                                        ).classes('text-xs')
                                if facture_num:
                                    ui.label(f'#{facture_num} - {facture_date}').classes(
                                        'text-xs text-gray-500'
                                    )

                        # Middle: Match indicator
                        with ui.column().classes('items-center'):
                            if ocr_failed:
                                ui.icon('attach_file', color='orange').classes('text-2xl')
                                ui.label('File only').classes('text-xs text-orange-600')
                            elif tx and diff is not None and diff < 0.01:
                                ui.icon('link', color='green').classes('text-2xl')
                                ui.label('Exact').classes('text-xs text-green-600')
                            elif tx and diff is not None and diff < 5.0:
                                ui.icon('link', color='orange').classes('text-2xl')
                                ui.label(f'~{diff:.2f}').classes('text-xs text-orange-600')
                            else:
                                ui.icon('help_outline', color='grey').classes('text-2xl')
                                ui.label('Manual').classes('text-xs text-gray-400')

                        # Right: Transaction selector
                        with ui.column().classes('flex-1'):
                            ui.label('Transaction').classes('text-xs text-gray-400')
                            current_tx_id = tx['TransactionID'] if tx else None
                            select = ui.select(
                                label='Select transaction',
                                options=tx_options,
                                value=current_tx_id,
                                with_input=True,
                            ).classes('w-full')
                            # Store the select ref for reading on confirm
                            pairing['_tx_select'] = select

                    # Expandable detail section (only for successful OCR)
                    if not ocr_failed:
                        with ui.expansion('OCR Details', icon='visibility').classes(
                            'w-full text-xs'
                        ):
                            with ui.grid(columns=3).classes('gap-2 w-full'):
                                ui.label(f"HT: {ocr.get('amount_ht', '-')}")
                                ui.label(f"TVA: {ocr.get('amount_tva', '-')}")
                                ui.label(f"TTC: {ocr.get('amount_ttc', '-')}")
                            if ocr.get('line_items'):
                                ui.label('Line items:').classes('font-medium mt-2')
                                for li in ocr['line_items']:
                                    ui.label(
                                        f"  {li.get('description', '?')} x{li.get('quantity', 1)} "
                                        f"@ {li.get('unit_price', '?')} = {li.get('total_price', '?')}"
                                    ).classes('text-xs text-gray-500')
                            if ocr.get('archived_filename'):
                                ui.label(
                                    f"Archived: {ocr['archived_filename']}"
                                ).classes('text-xs text-gray-400 mt-1')

    # ==================== CONFIRM ALL ====================

    async def on_confirm_all():
        """Create facture + match for every pairing."""
        # Read current selections from dropdowns
        results = {'created': 0, 'errors': 0, 'skipped': 0, 'suppliers_created': 0}

        for pairing in state['pairings']:
            if pairing.get('confirmed'):
                results['skipped'] += 1
                continue

            tx_select = pairing.get('_tx_select')
            tx_id = tx_select.value if tx_select else None
            if not tx_id:
                results['skipped'] += 1
                continue

            ocr = pairing['receipt'].get('ocr_result') or {}
            ocr_failed = pairing['receipt'].get('status') == 'error'

            # OCR failed -> create file justification with the archived image
            if ocr_failed or not ocr.get('success', False):
                archived = ocr.get('archived_filename')
                if archived:
                    try:
                        OutboundMatchService.create_file_match(
                            transaction_id=tx_id,
                            filename=archived,
                        )
                        results['created'] += 1
                        pairing['confirmed'] = True
                    except Exception as e:
                        logger.error(f"Error creating file match: {e}")
                        results['errors'] += 1
                else:
                    results['skipped'] += 1
                continue

            try:
                # Find or create supplier
                supplier_name = ocr.get('supplier_name', '')
                supplier_id = _find_supplier_id(supplier_name, state['suppliers'])
                if not supplier_id and supplier_name:
                    # Create new supplier
                    new_supplier = SupplierService.create(supplier_name)
                    supplier_id = new_supplier.get('idsupplier')
                    # Add to local cache so subsequent receipts can match
                    state['suppliers'].append(new_supplier)
                    results['suppliers_created'] += 1
                    logger.info(f"Created new supplier: {supplier_name} (id={supplier_id})")

                if not supplier_id:
                    # No name from OCR at all -> file justification fallback
                    if ocr.get('archived_filename'):
                        OutboundMatchService.create_file_match(
                            transaction_id=tx_id,
                            filename=ocr['archived_filename'],
                        )
                        results['created'] += 1
                        pairing['confirmed'] = True
                    else:
                        results['skipped'] += 1
                    continue

                # Build line items for create_facture_and_match
                line_items = []
                for li in ocr.get('line_items', []):
                    line_items.append({
                        'product_id': None,  # will create new products
                        'code': _slugify(li.get('description', 'ITEM')),
                        'designation': li.get('description', 'Item'),
                        'unitprice': li.get('unit_price', 0),
                        'tva': None,
                        'category': None,
                        'quantity': li.get('quantity', 1),
                        'item_price': li.get('total_price', 0),
                        'unit_price_snap': li.get('unit_price', 0),
                    })

                OutboundMatchService.create_facture_and_match(
                    transaction_id=tx_id,
                    supplier_id=supplier_id,
                    facture_num=ocr.get('facture_num', 'SCAN-UNKNOWN'),
                    facture_date=ocr.get('facture_date') or str(date.today()),
                    ttc=ocr.get('amount_ttc', 0) or 0,
                    ht=ocr.get('amount_ht', 0) or 0,
                    tva=ocr.get('amount_tva', 0) or 0,
                    line_items=line_items,
                    filename=ocr.get('archived_filename', 'MOBILE_SCAN'),
                    match_type='VISION_OCR',
                )
                results['created'] += 1
                pairing['confirmed'] = True

            except Exception as e:
                logger.error(f"Error creating facture for pairing: {e}")
                results['errors'] += 1

        # Cleanup session
        if state['session_token']:
            MobileScanService.invalidate(state['session_token'])
            state['session_token'] = None

        parts = [f"Matched: {results['created']}"]
        if results['suppliers_created']:
            parts.append(f"New suppliers: {results['suppliers_created']}")
        if results['skipped']:
            parts.append(f"Skipped: {results['skipped']}")
        if results['errors']:
            parts.append(f"Errors: {results['errors']}")
        msg = 'Done! ' + ', '.join(parts)
        ui.notify(msg, type='positive' if results['errors'] == 0 else 'warning', timeout=6000)

        if refs['match_dialog']:
            refs['match_dialog'].close()

        # Navigate back to outbound page to see updated data
        ui.navigate.to('/analytics/outbound')

    # ==================== HELPERS ====================

    def _find_supplier_id(name: str, suppliers: list[dict]) -> int | None:
        """Find supplier ID by name (case-insensitive partial match)."""
        if not name:
            return None
        name_lower = name.lower().strip()
        # Exact match first
        for s in suppliers:
            if s.get('name', '').lower().strip() == name_lower:
                return s['idsupplier']
        # Partial match
        for s in suppliers:
            if name_lower in s.get('name', '').lower() or s.get('name', '').lower() in name_lower:
                return s['idsupplier']
        return None

    def _slugify(text: str) -> str:
        """Simple slugify for product codes."""
        import re
        slug = re.sub(r'[^a-zA-Z0-9]', '_', text.strip())
        return slug[:50].upper() or 'ITEM'

    # ==================== PAGE LAYOUT ====================

    month_names = {
        1: 'January', 2: 'February', 3: 'March', 4: 'April',
        5: 'May', 6: 'June', 7: 'July', 8: 'August',
        9: 'September', 10: 'October', 11: 'November', 12: 'December',
    }

    distinct_data = BankInstructionService.get_distinct_months_years()
    available_months = distinct_data.get('months', list(range(1, 13)))
    available_years = distinct_data.get('years', [default_year])
    if default_month not in available_months:
        available_months = sorted(set(available_months + [default_month]))
    if default_year not in available_years:
        available_years = sorted(set(available_years + [default_year]))
    month_options = {m: month_names[m] for m in available_months}
    year_options = {y: str(y) for y in available_years}

    with layout('Scan & Match Receipts'):

        with ui.card().classes('w-full mb-4'):
            ui.label('Mobile Receipt Scanner').classes('text-lg font-semibold mb-1')
            ui.label(
                'Scan receipts from your phone and match them to unmatched outbound transactions.'
            ).classes('text-sm text-gray-500 mb-4')

            with ui.row().classes('w-full items-center gap-4'):
                ui.select(
                    label='Month', options=month_options,
                    value=default_month,
                    on_change=lambda e: state.update(month=e.value),
                ).classes('w-40')
                ui.select(
                    label='Year', options=year_options,
                    value=default_year,
                    on_change=lambda e: state.update(year=e.value),
                ).classes('w-32')

                ui.button(
                    'Start Scanning', icon='qr_code_scanner',
                    on_click=on_start_scan,
                ).props('color=indigo')

                ui.space()

                ui.button(
                    'Back to Outbound', icon='arrow_back',
                    on_click=lambda: ui.navigate.to('/analytics/outbound'),
                ).props('flat')

        # Instructions card
        with ui.card().classes('w-full'):
            ui.label('How it works').classes('text-md font-semibold mb-2')
            with ui.column().classes('gap-1'):
                ui.label('1. Select the matching scope (month/year) for transactions').classes('text-sm')
                ui.label('2. Click "Start Scanning" to generate a QR code').classes('text-sm')
                ui.label('3. Scan the QR code with your phone camera').classes('text-sm')
                ui.label('4. On your phone, take photos of receipts one by one').classes('text-sm')
                ui.label('5. Each receipt is automatically processed (OCR + archive)').classes('text-sm')
                ui.label('6. Click "Done Scanning" when finished').classes('text-sm')
                ui.label('7. Review the auto-matched pairings and click "Confirm All"').classes('text-sm')
