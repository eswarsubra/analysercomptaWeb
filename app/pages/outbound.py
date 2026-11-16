"""Outbound Justification page - match outbound bank transactions to supplier factures."""
import io
import os
import base64
import socket
import logging
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

from pathlib import Path

from nicegui import app, ui

from app.components.layout import layout
from app.services import (
    OutboundMatchService, BankInstructionService, SupplierService,
    MobileScanService, ScanSessionStore,
)

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


@ui.page('/analytics/outbound')
def outbound_page():
    """Outbound transaction justification page."""

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
        'transactions': [],
        'filter': 'unmatched',  # active filter: 'total', 'matched', 'unmatched'
        'filter_libelle': '',
        'filter_type': '',
        'filter_amount': '',
        'summary': {
            'total': 0, 'matched': 0, 'unmatched': 0,
            'match_rate_pct': 0.0,
        },
        'selected_transaction': None,
        'suppliers': [],
        'candidate_factures': [],
        # Folder used by the File Justification tab ('' = default archive dir), persisted
        'justif_dir': app.storage.general.get('outbound_justif_dir') or '',
    }

    refs = {
        'transactions_table': None,
        'total_badge': None,
        'matched_badge': None,
        'unmatched_badge': None,
        'rate_label': None,
        'status_label': None,
        'tx_date_label': None,
        'tx_libelle_label': None,
        'tx_amount_label': None,
        'supplier_select': None,
        'factures_table': None,
        'selected_facture_id': None,
        'date_from_input': None,
        'date_to_input': None,
        'matched_factures_table': None,
        'matched_diff_label': None,
        'archive_files_table': None,
        'selected_archive_file': None,
        'justif_dir_input': None,
        'folder_browser_dialog': None,
        'implicit_note_input': None,
        # Scanned receipts badge + manage
        'scan_badge': None,
        'manage_dialog': None,
        'manage_container': None,
        # OCR result dialog
        'ocr_result_dialog': None,
        # Import receipts refs
        'import_dialog': None,
        'import_counter_label': None,
        'import_files_container': None,
        'import_poll_timer': None,
    }

    import_state = {
        'session_token': None,
        'imported_files': [],
        'poll_active': False,
    }

    # ==================== SCANNED RECEIPTS BADGE + MANAGE ====================

    def _refresh_scan_badge():
        count = ScanSessionStore.available_count()
        if refs['scan_badge']:
            refs['scan_badge'].set_text(str(count))
            refs['scan_badge'].set_visibility(count > 0)

    def _open_manage_dialog():
        dialog = refs['manage_dialog']
        dialog.clear()
        all_receipts = ScanSessionStore.get_all_receipts()

        with dialog, ui.card().classes('p-4 min-w-[600px] max-h-[70vh]'):
            ui.label('Scanned Receipts').classes('text-lg font-semibold mb-2')

            if not all_receipts:
                ui.label('No scanned receipts stored.').classes(
                    'text-sm text-gray-500'
                )
            else:
                refs['manage_container'] = ui.column().classes('w-full gap-2')
                _render_manage_receipts(all_receipts)

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                if all_receipts:
                    ui.button(
                        'Clear All', icon='delete_sweep',
                        on_click=_on_clear_all_receipts,
                    ).props('flat color=negative')
                ui.button('Close', on_click=dialog.close).props('flat')

        dialog.open()

    def _render_manage_receipts(all_receipts: dict):
        container = refs.get('manage_container')
        if not container:
            return
        container.clear()
        status_colors = {
            'ready': 'green', 'error': 'orange',
            'matched': 'blue', 'imported': 'purple',
        }
        with container:
            for rid, r in all_receipts.items():
                ocr = r.get('ocr_result') or {}
                status = r.get('status', 'ready')
                with ui.card().classes('w-full p-2'):
                    with ui.row().classes('w-full items-center gap-2'):
                        supplier = ocr.get('supplier_name', 'Unknown')
                        amount = ocr.get('amount_ttc')
                        ui.label(supplier).classes('font-semibold text-sm')
                        if amount is not None:
                            ui.label(f'{amount:,.2f}').classes(
                                'text-sm text-blue-600 font-medium'
                            )
                        ui.badge(status, color=status_colors.get(status, 'grey')).classes(
                            'text-xs'
                        )
                        archived = r.get('archived_filename', '')
                        if archived:
                            ui.label(archived).classes('text-xs text-gray-400 truncate')
                        ui.space()
                        if status != 'ready':
                            ui.button(
                                icon='replay',
                                on_click=lambda _rid=rid: _on_reset_receipt(_rid),
                            ).props('flat dense round size=sm color=primary').tooltip('Reset to Ready')
                        ui.button(
                            icon='close', on_click=lambda _rid=rid: _on_remove_receipt(_rid),
                        ).props('flat dense round size=sm color=negative').tooltip('Remove')

    def _on_reset_receipt(receipt_id: str):
        ScanSessionStore.mark_ready(receipt_id)
        _refresh_scan_badge()
        _open_manage_dialog()  # Re-render

    def _on_remove_receipt(receipt_id: str):
        ScanSessionStore.remove_receipt(receipt_id)
        _refresh_scan_badge()
        _open_manage_dialog()  # Re-render

    def _on_clear_all_receipts():
        ScanSessionStore.clear_all()
        _refresh_scan_badge()
        if refs['manage_dialog']:
            refs['manage_dialog'].close()
        ui.notify('All scanned receipts cleared', type='info')

    # ==================== IMPORT RECEIPTS (bulk folder upload) ====================

    def on_start_import():
        """Create session, populate QR dialog for import and open it."""
        token = MobileScanService.create_session()
        import_state['session_token'] = token
        import_state['imported_files'] = []

        import_url = f'{_get_server_url()}/mobile/import/{token}'
        qr_data_uri = _generate_qr_base64(import_url)

        dialog = refs['import_dialog']
        dialog.clear()
        with dialog, ui.card().classes('p-6 min-w-[500px]'):
            ui.label('Import Receipts from Phone').classes('text-xl font-semibold mb-2')
            ui.label(
                'Scan the QR code with your phone. '
                'Select your Pictures folder to upload all images. '
                'Click "Done" when the upload finishes on your phone.'
            ).classes('text-sm text-gray-500 mb-4')

            with ui.row().classes('w-full justify-center'):
                ui.image(qr_data_uri).classes('w-56 h-56')

            ui.label(import_url).classes(
                'text-xs text-gray-400 text-center w-full mt-1 break-all'
            )
            ui.separator().classes('my-4')

            refs['import_counter_label'] = ui.label('0 files imported').classes(
                'text-lg font-semibold text-center w-full'
            )
            refs['import_files_container'] = ui.column().classes(
                'w-full gap-1 mt-2 max-h-48 overflow-y-auto'
            )

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=on_cancel_import).props('flat')
                ui.button(
                    'Done', icon='check',
                    on_click=on_done_import,
                ).props('color=primary')

        dialog.open()
        _start_import_polling()

    def _start_import_polling():
        import_state['poll_active'] = True

        async def poll():
            if not import_state['poll_active'] or not import_state['session_token']:
                return
            receipts = MobileScanService.get_receipts(import_state['session_token'])
            if len(receipts) != len(import_state['imported_files']):
                import_state['imported_files'] = receipts
                try:
                    _update_import_progress()
                except Exception:
                    _stop_import_polling()

        refs['import_poll_timer'] = ui.timer(2.0, poll)

    def _stop_import_polling():
        if refs['import_poll_timer']:
            refs['import_poll_timer'].cancel()
            refs['import_poll_timer'] = None
        import_state['poll_active'] = False

    def _update_import_progress():
        count = len(import_state['imported_files'])
        if refs['import_counter_label']:
            refs['import_counter_label'].set_text(
                f'{count} file{"s" if count != 1 else ""} imported'
            )
        container = refs['import_files_container']
        if not container:
            return
        container.clear()
        with container:
            for r in reversed(import_state['imported_files']):
                ocr = r.get('ocr_result') or {}
                archived = ocr.get('archived_filename', '')
                original = ocr.get('original_name', '')
                with ui.row().classes('items-center gap-2'):
                    ui.icon('check_circle', color='green').classes('text-lg')
                    ui.label(original or archived).classes('text-sm truncate')

    def on_cancel_import():
        _stop_import_polling()
        if import_state['session_token']:
            MobileScanService.invalidate(import_state['session_token'])
            import_state['session_token'] = None
        if refs['import_dialog']:
            refs['import_dialog'].close()

    def on_done_import():
        _stop_import_polling()
        if refs['import_dialog']:
            refs['import_dialog'].close()

        # Final refresh from session
        if import_state['session_token']:
            import_state['imported_files'] = MobileScanService.get_receipts(
                import_state['session_token']
            )

        count = len(import_state['imported_files'])
        logger.info(f"Import done: {count} files imported")

        # Sync imported files to ScanSessionStore so they appear in factures page
        synced = 0
        for r in import_state['imported_files']:
            ocr = r.get('ocr_result') or {}
            archived = ocr.get('archived_filename')
            if archived:
                ScanSessionStore.add_receipt(
                    receipt_id=r['id'],
                    ocr_result=ocr,
                    archived_filename=archived,
                    status='ready',
                )
                synced += 1
        logger.info(f"Import: synced {synced} files to ScanSessionStore")

        # Cleanup mobile session
        if import_state['session_token']:
            MobileScanService.invalidate(import_state['session_token'])
            import_state['session_token'] = None

        _refresh_scan_badge()

        # Show results dialog with file count and names
        if count > 0:
            _show_import_results(import_state['imported_files'])
        else:
            ui.notify('No files were imported.', type='warning')

    def _show_import_results(imported_files: list):
        """Show a dialog listing all imported files."""
        count = len(imported_files)
        with ui.dialog() as results_dialog, ui.card().classes('p-6 min-w-[500px]'):
            ui.label('Import Results').classes('text-xl font-semibold mb-2')
            ui.label(f'{count} file{"s" if count != 1 else ""} imported successfully').classes(
                'text-lg text-green-700 font-medium mb-4'
            )

            with ui.column().classes('w-full gap-1 max-h-64 overflow-y-auto'):
                for r in imported_files:
                    ocr = r.get('ocr_result') or {}
                    archived = ocr.get('archived_filename', '')
                    original = ocr.get('original_name', '')
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('image', color='brown').classes('text-sm')
                        ui.label(original or archived).classes('text-sm')
                        if archived:
                            ui.label(f'-> {archived}').classes('text-xs text-gray-400')

            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Close', on_click=results_dialog.close).props('flat')

        results_dialog.open()

        # Refresh archive files table if it's populated
        if refs.get('archive_files_table'):
            _refresh_archive_files()

    def _refresh_archive_files():
        """Reload the archive files table after import."""
        try:
            files = OutboundMatchService.list_archive_files()
            if refs.get('archive_files_table'):
                refs['archive_files_table'].update_rows(files)
        except Exception as e:
            logger.error(f"Failed to refresh archive files: {e}")

    # ==================== DATA LOADING ====================

    def _apply_filter():
        """Filter the transactions table based on the active filter and search inputs."""
        active = state['filter']
        if active == 'total':
            filtered = state['transactions']
        elif active == 'matched':
            filtered = [t for t in state['transactions'] if t['match_status'] == 'CONFIRMED']
        else:  # 'unmatched' (default) — unmatched + partially matched
            filtered = [
                t for t in state['transactions']
                if t['match_status'] in ('UNMATCHED', 'PARTIALLY_MATCHED')
            ]

        # Apply text/amount filters
        libelle_q = (state.get('filter_libelle') or '').strip().lower()
        type_q = (state.get('filter_type') or '').strip().lower()
        amount_q = (state.get('filter_amount') or '').strip()

        if libelle_q:
            filtered = [t for t in filtered if libelle_q in (t.get('Libelle') or '').lower()]
        if type_q:
            filtered = [t for t in filtered if type_q in (t.get('Qualifier') or '').lower()]
        if amount_q:
            try:
                amt_val = float(amount_q)
                filtered = [
                    t for t in filtered
                    if t.get('Montant') is not None
                    and abs(float(t['Montant']) - amt_val) < 0.01
                ]
            except ValueError:
                # partial string match on the amount as fallback
                filtered = [
                    t for t in filtered
                    if amount_q in str(t.get('Montant', ''))
                ]

        if refs['transactions_table']:
            refs['transactions_table'].update_rows(filtered)

        # Update badge styles to highlight active filter
        filter_badges = {
            'total': refs['total_badge'],
            'matched': refs['matched_badge'],
            'unmatched': refs['unmatched_badge'],
        }
        for key, badge in filter_badges.items():
            if badge:
                if key == active:
                    badge.props('outline=false')
                    badge._classes = [c for c in badge._classes if c != 'opacity-50']
                else:
                    badge.props('outline')
                    if 'opacity-50' not in badge._classes:
                        badge._classes.append('opacity-50')
                badge.update()

    def on_filter_click(filter_name: str):
        """Set active filter and refresh the table."""
        state['filter'] = filter_name
        _apply_filter()

    def load_data():
        month = state['month']
        year = state['year']

        state['transactions'] = OutboundMatchService.get_transactions_for_month(month, year)
        state['summary'] = OutboundMatchService.get_summary(month, year)

        # Load suppliers once
        if not state['suppliers']:
            state['suppliers'] = SupplierService.get_all()

        # Update summary badges
        s = state['summary']
        if refs['total_badge']:
            refs['total_badge'].set_text(f"Total: {s['total']}")
        if refs['matched_badge']:
            refs['matched_badge'].set_text(f"Matched: {s['matched']}")
        if refs['unmatched_badge']:
            unmatched_count = s['unmatched'] + s.get('partially_matched', 0)
            refs['unmatched_badge'].set_text(f"Unmatched: {unmatched_count}")
        if refs['rate_label']:
            refs['rate_label'].set_text(f"Match Rate: {s['match_rate_pct']:.1f}%")

        if refs['status_label']:
            refs['status_label'].set_text(
                f"Loaded {month_names[month]} {year} - {s['total']} transactions"
            )

        # Apply active filter to table
        _apply_filter()

    # ==================== ACTION HANDLERS ====================

    def on_match_click(transaction_id):
        tx = next(
            (t for t in state['transactions'] if t['TransactionID'] == transaction_id),
            None,
        )
        if not tx:
            ui.notify('Transaction not found', type='warning')
            return

        state['selected_transaction'] = tx

        # Update dialog labels
        if refs['tx_date_label']:
            refs['tx_date_label'].set_text(str(tx.get('Date_operation', '')))
        if refs['tx_libelle_label']:
            refs['tx_libelle_label'].set_text(tx.get('Libelle', ''))
        if refs['tx_amount_label']:
            refs['tx_amount_label'].set_text(f"{tx.get('Montant', 0):,.2f}")

        # Populate supplier dropdown
        supplier_options = {s['idsupplier']: s['name'] for s in state['suppliers']}
        if refs['supplier_select']:
            refs['supplier_select'].options = supplier_options
            refs['supplier_select'].value = None
            refs['supplier_select'].update()

        # Set default date range (+-30 days from transaction date)
        tx_date_str = tx.get('Date_operation', '')
        try:
            tx_dt = datetime.strptime(tx_date_str, '%Y-%m-%d')
            default_from = (tx_dt - timedelta(days=30)).strftime('%Y-%m-%d')
            default_to = (tx_dt + timedelta(days=30)).strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            default_from = ''
            default_to = ''
        if refs['date_from_input']:
            refs['date_from_input'].value = default_from
        if refs['date_to_input']:
            refs['date_to_input'].value = default_to

        # Clear candidate factures
        state['candidate_factures'] = []
        refs['selected_facture_id'] = None
        if refs['factures_table']:
            refs['factures_table'].update_rows([])

        # Load already-matched factures for this transaction
        try:
            matched = OutboundMatchService.get_matched_factures(tx['TransactionID'])
        except Exception:
            matched = []
        if refs['matched_factures_table']:
            refs['matched_factures_table'].update_rows(matched)

        # Show tx remaining from the last matched row (running balance)
        if refs['matched_diff_label']:
            if matched:
                tx_remaining = matched[-1].get('tx_remaining', 0)
                if tx_remaining < 0.01:
                    refs['matched_diff_label'].set_text('(Fully justified)')
                    refs['matched_diff_label'].classes(replace='text-sm font-bold text-green-600')
                else:
                    refs['matched_diff_label'].set_text(
                        f'(Tx Remaining: {tx_remaining:,.2f})'
                    )
                    refs['matched_diff_label'].classes(replace='text-sm font-bold text-orange-600')
            else:
                refs['matched_diff_label'].set_text('')

        # Clear file tab
        refs['selected_archive_file'] = None
        if refs['archive_files_table']:
            refs['archive_files_table'].update_rows([])

        # Clear implicit tab
        if refs['implicit_note_input']:
            refs['implicit_note_input'].value = ''

        # Load archive files for file tab
        on_load_archive_files()

        match_dialog.open()

    def _refresh_candidates():
        """Re-query candidate factures using current supplier and date range."""
        tx = state['selected_transaction']
        supplier_id = refs['supplier_select'].value if refs['supplier_select'] else None
        if not supplier_id or not tx:
            return

        date_from = refs['date_from_input'].value if refs['date_from_input'] else None
        date_to = refs['date_to_input'].value if refs['date_to_input'] else None

        candidates = OutboundMatchService.find_candidates(
            supplier_id=supplier_id,
            amount=tx.get('Montant', 0),
            transaction_date=tx.get('Date_operation'),
            date_from=date_from or None,
            date_to=date_to or None,
            exclude_transaction_id=tx.get('TransactionID'),
        )
        state['candidate_factures'] = candidates
        refs['selected_facture_id'] = None

        if refs['factures_table']:
            refs['factures_table'].update_rows(candidates)

        if candidates:
            ui.notify(f"Found {len(candidates)} candidate facture(s)", type='positive')
        else:
            ui.notify("No matching factures found for this supplier", type='warning')

    def on_supplier_selected(supplier_id):
        tx = state['selected_transaction']
        if not supplier_id or not tx:
            return
        _refresh_candidates()

    def on_confirm_match_dialog():
        facture_id = refs.get('selected_facture_id')
        if not facture_id:
            ui.notify('Please select a facture', type='warning')
            return

        tx = state['selected_transaction']
        supplier_id = refs['supplier_select'].value if refs['supplier_select'] else None
        if not tx or not supplier_id:
            ui.notify('Missing transaction or supplier', type='warning')
            return

        try:
            OutboundMatchService.create_manual_match(
                transaction_id=tx['TransactionID'],
                facture_id=facture_id,
                supplier_id=supplier_id,
            )
            ui.notify('Match created successfully', type='positive')
            match_dialog.close()
            load_data()
        except Exception as e:
            ui.notify(f'Error creating match: {e}', type='negative')

    def on_delete_match(transaction_id):
        try:
            count = OutboundMatchService.delete_matches_for_transaction(transaction_id)
            ui.notify(f'{count} match(es) removed (un-justified)', type='positive')
            load_data()
        except Exception as e:
            ui.notify(f'Error removing matches: {e}', type='negative')

    def on_auto_match():
        ui.notify('Running auto-match...', type='info')
        try:
            stats = OutboundMatchService.auto_match(
                state['month'], state['year'],
            )
            total_matched = stats['facture_matched'] + stats['implicit_matched'] + stats['file_matched']
            msg = (
                f"Auto Match: {stats['facture_matched']} facture, "
                f"{stats['implicit_matched']} implicit, "
                f"{stats['file_matched']} receipt, "
                f"{stats['skipped']} skipped "
                f"(of {stats['processed']} total)"
            )
            notify_type = 'positive' if total_matched > 0 else 'warning'
            ui.notify(msg, type=notify_type, timeout=8000)
            load_data()
            _refresh_scan_badge()
        except Exception as e:
            ui.notify(f'Auto-match error: {e}', type='negative')

    def on_facture_select(e):
        if e.selection:
            refs['selected_facture_id'] = e.selection[0].get('idFacture')
        else:
            refs['selected_facture_id'] = None

    def on_archive_file_select(e):
        if e.selection:
            row = e.selection[0]
            refs['selected_archive_file'] = row.get('justification_name') or row.get('filename')
        else:
            refs['selected_archive_file'] = None

    def _current_justif_dir() -> str | None:
        return state['justif_dir'] or None

    def _display_justif_dir() -> str:
        if state['justif_dir']:
            return state['justif_dir']
        try:
            return OutboundMatchService.get_default_archive_dir()
        except Exception:
            return ''

    def _set_justif_dir(path: str | None):
        """Change the File Justification folder, persist it and reload the file list."""
        path = (path or '').strip()
        if path:
            p = Path(path).expanduser()
            if not p.is_dir():
                ui.notify(f'Folder not found: {path}', type='negative')
                return
            path = str(p.resolve())
            # Selecting the default archive dir means "no override"
            try:
                if path == OutboundMatchService.get_default_archive_dir():
                    path = ''
            except Exception:
                pass
        state['justif_dir'] = path
        app.storage.general['outbound_justif_dir'] = path
        if refs['justif_dir_input']:
            refs['justif_dir_input'].value = _display_justif_dir()
        on_load_archive_files()

    def _open_folder_browser():
        """Server-side folder browser to pick any folder on the disk."""
        dialog = refs['folder_browser_dialog']
        browse = {'path': _display_justif_dir()}

        def go(path: str):
            path = (path or '').strip()
            if not path or not Path(path).is_dir():
                ui.notify(f'Folder not found: {path}', type='warning')
                return
            browse['path'] = str(Path(path).resolve())
            render()

        def select(path: str):
            dialog.close()
            _set_justif_dir(path)

        def render():
            dialog.clear()
            current = browse['path']
            with dialog, ui.card().classes('p-4 min-w-[600px]'):
                ui.label('Select Justification Folder').classes('text-lg font-semibold mb-2')
                with ui.row().classes('w-full items-center gap-1'):
                    for root in OutboundMatchService.list_filesystem_roots():
                        ui.button(root, on_click=lambda _r=root: go(_r)).props(
                            'flat dense color=primary'
                        )
                path_input = ui.input('Path', value=current).classes('w-full').props('dense')
                path_input.on('keydown.enter', lambda: go(path_input.value))
                with ui.scroll_area().classes('w-full h-80 border rounded'):
                    if current:
                        parent = str(Path(current).parent)
                        if parent != current:
                            with ui.item(on_click=lambda: go(parent)).props('clickable dense'):
                                with ui.item_section().props('avatar'):
                                    ui.icon('arrow_upward', color='grey')
                                ui.item_section('..')
                        subdirs = OutboundMatchService.list_subdirectories(current)
                        if not subdirs:
                            ui.label('(no subfolders)').classes('text-sm text-gray-400 p-2')
                        for name in subdirs:
                            with ui.item(
                                on_click=lambda _n=name: go(str(Path(current) / _n))
                            ).props('clickable dense'):
                                with ui.item_section().props('avatar'):
                                    ui.icon('folder', color='amber')
                                ui.item_section(name)
                with ui.row().classes('w-full justify-end gap-2 mt-4'):
                    ui.button('Cancel', on_click=dialog.close).props('flat')
                    ui.button('Select This Folder', icon='check',
                              on_click=lambda: select(path_input.value)).props('color=primary')

        render()
        dialog.open()

    def on_load_archive_files():
        try:
            files = OutboundMatchService.list_archive_files(_current_justif_dir())
            if refs['archive_files_table']:
                refs['archive_files_table'].update_rows(files)
            refs['selected_archive_file'] = None
        except Exception as e:
            ui.notify(f'Error loading archive files: {e}', type='negative')

    async def on_ocr_file(filename: str):
        """Run on-demand OCR on an archive file and show results in a dialog."""
        ui.notify(f'Reading OCR data for {filename}...', type='info', timeout=3000)
        try:
            import asyncio
            result = await asyncio.get_event_loop().run_in_executor(
                None, OutboundMatchService.ocr_archived_image, filename,
                _current_justif_dir(),
            )
        except Exception as e:
            ui.notify(f'OCR failed: {e}', type='negative')
            return

        if result.get('source') == 'json_sidecar':
            ui.notify('Loaded from JSON sidecar', type='positive', timeout=2000)

        # Format result as readable text
        lines = []
        if result.get('success'):
            lines.append(f"Supplier:     {result.get('supplier_name') or '-'}")
            lines.append(f"Invoice #:    {result.get('facture_num') or '-'}")
            lines.append(f"Date:         {result.get('facture_date') or '-'}")
            lines.append(f"Amount HT:    {result.get('amount_ht') or '-'}")
            lines.append(f"Amount TVA:   {result.get('amount_tva') or '-'}")
            lines.append(f"Amount TTC:   {result.get('amount_ttc') or '-'}")
            if result.get('line_items'):
                lines.append('')
                lines.append('Line Items:')
                for li in result['line_items']:
                    desc = li.get('description', '')
                    qty = li.get('quantity', '')
                    up = li.get('unit_price', '')
                    tp = li.get('total_price', '')
                    lines.append(f"  - {desc}  qty={qty}  unit={up}  total={tp}")
            if result.get('archived_filename') != filename:
                lines.append('')
                lines.append(f"File renamed: {result.get('archived_filename')}")
        else:
            lines.append(f"OCR Error: {result.get('error', 'Unknown error')}")

        text = '\n'.join(lines)

        dialog = refs.get('ocr_result_dialog')
        if dialog:
            dialog.clear()
            with dialog, ui.card().classes('p-4 min-w-[600px] max-w-[800px]'):
                ui.label(f'OCR Result: {filename}').classes('text-lg font-semibold mb-2')
                ui.textarea(value=text).props('readonly autogrow').classes('w-full font-mono text-sm')
                with ui.row().classes('w-full justify-end mt-4'):
                    ui.button('Close', on_click=dialog.close).props('flat')
            dialog.open()

        # Refresh archive table since file may have been renamed
        on_load_archive_files()

    def on_confirm_file_match():
        filename = refs.get('selected_archive_file')
        if not filename:
            ui.notify('Please select a file', type='warning')
            return

        tx = state['selected_transaction']
        if not tx:
            ui.notify('No transaction selected', type='warning')
            return

        try:
            OutboundMatchService.create_file_match(
                transaction_id=tx['TransactionID'],
                filename=filename,
            )
            # Mark scanned receipt as matched if it came from scanning
            receipt_id = ScanSessionStore.find_by_filename(filename)
            if receipt_id:
                ScanSessionStore.mark_matched(receipt_id, tx['TransactionID'])
                _refresh_scan_badge()

            ui.notify(f'File justification created: {filename}', type='positive')
            match_dialog.close()
            load_data()
        except Exception as e:
            ui.notify(f'Error creating file match: {e}', type='negative')

    def on_confirm_implicit_match():
        tx = state['selected_transaction']
        if not tx:
            ui.notify('No transaction selected', type='warning')
            return

        note = ''
        if refs['implicit_note_input']:
            note = refs['implicit_note_input'].value or ''

        try:
            OutboundMatchService.create_implicit_match(
                transaction_id=tx['TransactionID'],
                note=note,
            )
            ui.notify('Implicit justification created', type='positive')
            match_dialog.close()
            load_data()
        except Exception as e:
            ui.notify(f'Error creating implicit match: {e}', type='negative')

    # ==================== UI LAYOUT ====================

    # Pre-create dialogs at page level (outside other dialog contexts)
    refs['manage_dialog'] = ui.dialog()
    refs['import_dialog'] = ui.dialog()
    refs['ocr_result_dialog'] = ui.dialog()
    refs['folder_browser_dialog'] = ui.dialog()

    # Justify Transaction Dialog (tabbed: Facture / File / Implicit)
    with ui.dialog().props('full-width') as match_dialog, ui.card().classes('p-4 max-w-[1400px] w-full max-h-[90vh] overflow-y-auto'):
        ui.label('Justify Transaction').classes('text-lg font-semibold mb-2')

        # Transaction details (shared across all tabs)
        with ui.card().classes('w-full bg-gray-50 dark:bg-gray-800 mb-4 p-3'):
            ui.label('Transaction Details').classes('text-sm font-medium mb-2')
            with ui.grid(columns=2).classes('gap-x-4 gap-y-1'):
                ui.label('Date:').classes('text-sm font-medium')
                refs['tx_date_label'] = ui.label('').classes('text-sm')
                ui.label('Libelle:').classes('text-sm font-medium')
                refs['tx_libelle_label'] = ui.label('').classes('text-sm')
                ui.label('Amount:').classes('text-sm font-medium')
                refs['tx_amount_label'] = ui.label('').classes('text-sm font-bold text-red-600')

        # Tabs
        with ui.tabs().classes('w-full') as tabs:
            facture_tab = ui.tab('facture', label='Facture Match', icon='receipt_long')
            file_tab = ui.tab('file', label='File Justification', icon='attach_file')
            implicit_tab = ui.tab('implicit', label='Implicit', icon='verified')

        with ui.tab_panels(tabs, value='facture').classes('w-full'):
            # === Tab 1: Facture Match (existing logic) ===
            with ui.tab_panel('facture'):
                with ui.row().classes('w-full items-end gap-4 mb-2'):
                    with ui.input('From', value='').classes('w-40') as date_from_input:
                        with date_from_input.add_slot('append'):
                            ui.icon('event').classes('cursor-pointer')
                        with ui.menu() as from_menu:
                            ui.date(on_change=lambda e: (
                                setattr(refs['date_from_input'], 'value', e.value),
                                from_menu.close(),
                                _refresh_candidates(),
                            )).props('mask="YYYY-MM-DD"')
                    refs['date_from_input'] = date_from_input

                    with ui.input('To', value='').classes('w-40') as date_to_input:
                        with date_to_input.add_slot('append'):
                            ui.icon('event').classes('cursor-pointer')
                        with ui.menu() as to_menu:
                            ui.date(on_change=lambda e: (
                                setattr(refs['date_to_input'], 'value', e.value),
                                to_menu.close(),
                                _refresh_candidates(),
                            )).props('mask="YYYY-MM-DD"')
                    refs['date_to_input'] = date_to_input

                refs['supplier_select'] = ui.select(
                    label='Select Supplier',
                    options={},
                    with_input=True,
                    on_change=lambda e: on_supplier_selected(e.value),
                ).classes('w-full mb-4')

                ui.label('Candidate Factures').classes('text-sm font-medium mb-2')
                facture_columns = [
                    {'name': 'factNum', 'label': 'Facture #', 'field': 'factNum', 'align': 'left'},
                    {'name': 'factDate', 'label': 'Date', 'field': 'factDate', 'align': 'center'},
                    {'name': 'factmontantttc', 'label': 'Amount TTC', 'field': 'factmontantttc', 'align': 'right'},
                    {'name': 'matched_so_far', 'label': 'Matched', 'field': 'matched_so_far', 'align': 'right'},
                    {'name': 'remaining', 'label': 'Fact. Remaining', 'field': 'remaining', 'align': 'right'},
                    {'name': 'tx_remaining', 'label': 'Tx Remaining', 'field': 'tx_remaining', 'align': 'right'},
                    {'name': 'amount_diff', 'label': 'Diff', 'field': 'amount_diff', 'align': 'right'},
                ]
                refs['factures_table'] = ui.table(
                    columns=facture_columns,
                    rows=[],
                    row_key='idFacture',
                    selection='single',
                    on_select=on_facture_select,
                ).classes('w-full')

                # Highlight partially-settled factures with badge next to facture #
                refs['factures_table'].add_slot('body-cell-factNum', '''
                    <q-td :props="props">
                        {{ props.row.factNum }}
                        <q-badge v-if="props.row.matched_so_far > 0" color="amber" class="q-ml-sm" dense>
                            Partial
                        </q-badge>
                    </q-td>
                ''')

                refs['factures_table'].add_slot('body-cell-factmontantttc', '''
                    <q-td :props="props" class="text-right">
                        <span class="font-medium">
                            {{ props.row.factmontantttc != null
                                ? props.row.factmontantttc.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                                : '-' }}
                        </span>
                    </q-td>
                ''')

                refs['factures_table'].add_slot('body-cell-matched_so_far', '''
                    <q-td :props="props" class="text-right">
                        <span :class="props.row.matched_so_far > 0 ? 'text-blue-600 font-medium' : 'text-gray-400'">
                            {{ props.row.matched_so_far != null
                                ? props.row.matched_so_far.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                                : '0.00' }}
                        </span>
                    </q-td>
                ''')

                refs['factures_table'].add_slot('body-cell-remaining', '''
                    <q-td :props="props" class="text-right">
                        <span class="font-semibold text-orange-700">
                            {{ props.row.remaining != null
                                ? props.row.remaining.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                                : '-' }}
                        </span>
                    </q-td>
                ''')

                refs['factures_table'].add_slot('body-cell-tx_remaining', '''
                    <q-td :props="props" class="text-right">
                        <span :class="props.row.tx_remaining < 0.01 ? 'text-green-600 font-bold' : 'text-purple-700 font-semibold'">
                            {{ props.row.tx_remaining != null
                                ? props.row.tx_remaining.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                                : '-' }}
                        </span>
                    </q-td>
                ''')

                refs['factures_table'].add_slot('body-cell-amount_diff', '''
                    <q-td :props="props" class="text-right">
                        <span :class="Math.abs(props.row.amount_diff) < 0.01 ? 'text-green-600 font-bold' : 'text-orange-600'"
                              class="font-medium">
                            {{ props.row.amount_diff != null
                                ? props.row.amount_diff.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                                : '-' }}
                        </span>
                    </q-td>
                ''')

                # Already matched factures (read-only)
                with ui.row().classes('w-full items-center mt-4 mb-2 gap-2'):
                    ui.label('Already Matched Factures').classes('text-sm font-medium')
                    refs['matched_diff_label'] = ui.label('').classes('text-sm font-bold')
                matched_columns = [
                    {'name': 'factNum', 'label': 'Facture #', 'field': 'factNum', 'align': 'left'},
                    {'name': 'factDate', 'label': 'Date', 'field': 'factDate', 'align': 'center'},
                    {'name': 'factmontantttc', 'label': 'Amount TTC', 'field': 'factmontantttc', 'align': 'right'},
                    {'name': 'consumed', 'label': 'Consumed', 'field': 'consumed', 'align': 'right'},
                    {'name': 'remaining', 'label': 'Fact. Remaining', 'field': 'remaining', 'align': 'right'},
                    {'name': 'tx_remaining', 'label': 'Tx Remaining', 'field': 'tx_remaining', 'align': 'right'},
                ]
                refs['matched_factures_table'] = ui.table(
                    columns=matched_columns,
                    rows=[],
                    row_key='idFacture',
                ).classes('w-full')

                refs['matched_factures_table'].add_slot('body-cell-factmontantttc', '''
                    <q-td :props="props" class="text-right">
                        <span class="font-medium">
                            {{ props.row.factmontantttc != null
                                ? props.row.factmontantttc.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                                : '-' }}
                        </span>
                    </q-td>
                ''')

                refs['matched_factures_table'].add_slot('body-cell-consumed', '''
                    <q-td :props="props" class="text-right">
                        <span class="text-blue-600 font-medium">
                            {{ props.row.consumed != null
                                ? props.row.consumed.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                                : '0.00' }}
                        </span>
                    </q-td>
                ''')

                refs['matched_factures_table'].add_slot('body-cell-remaining', '''
                    <q-td :props="props" class="text-right">
                        <span :class="props.row.remaining < 0.01 ? 'text-green-600 font-medium' : 'font-semibold text-orange-700'">
                            {{ props.row.remaining != null
                                ? props.row.remaining.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                                : '-' }}
                        </span>
                    </q-td>
                ''')

                refs['matched_factures_table'].add_slot('body-cell-tx_remaining', '''
                    <q-td :props="props" class="text-right">
                        <span :class="props.row.tx_remaining < 0.01 ? 'text-green-600 font-bold' : 'text-purple-700 font-semibold'">
                            {{ props.row.tx_remaining != null
                                ? props.row.tx_remaining.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                                : '-' }}
                        </span>
                    </q-td>
                ''')

                with ui.row().classes('w-full justify-end gap-2 mt-4'):
                    ui.button('Cancel', on_click=match_dialog.close).props('flat')
                    ui.button('Confirm Match', icon='link',
                              on_click=on_confirm_match_dialog).props('color=primary')

            # === Tab 2: File Justification ===
            with ui.tab_panel('file'):
                with ui.row().classes('w-full items-center gap-2 mb-2'):
                    refs['justif_dir_input'] = ui.input(
                        'Folder', value=_display_justif_dir(),
                    ).classes('flex-grow').props('dense outlined')
                    refs['justif_dir_input'].on(
                        'keydown.enter',
                        lambda: _set_justif_dir(refs['justif_dir_input'].value),
                    )
                    ui.button('Browse', icon='folder_open',
                              on_click=_open_folder_browser).props('flat dense color=primary')
                    ui.button(icon='restart_alt',
                              on_click=lambda: _set_justif_dir('')).props(
                        'flat dense round color=grey'
                    ).tooltip('Reset to default archive folder')
                    ui.button('Refresh Files', icon='refresh',
                              on_click=on_load_archive_files).props('flat dense color=primary')

                ui.label(
                    'Select a file from this folder to justify this transaction.'
                ).classes('text-sm text-gray-500 mb-2')

                archive_columns = [
                    {'name': 'filename', 'label': 'Filename', 'field': 'filename', 'align': 'left', 'sortable': True},
                    {'name': 'extension', 'label': 'Type', 'field': 'extension', 'align': 'center'},
                    {'name': 'size_bytes', 'label': 'Size', 'field': 'size_bytes', 'align': 'right'},
                    {'name': 'modified_at', 'label': 'Modified', 'field': 'modified_at', 'align': 'center', 'sortable': True},
                    {'name': 'actions', 'label': '', 'field': 'filename', 'align': 'center'},
                ]
                refs['archive_files_table'] = ui.table(
                    columns=archive_columns,
                    rows=[],
                    row_key='filename',
                    selection='single',
                    on_select=on_archive_file_select,
                    pagination=10,
                ).classes('w-full')

                refs['archive_files_table'].add_slot('top-right', '''
                    <q-input dense debounce="200" v-model="props.filter"
                             placeholder="Search filename..."
                             class="q-ml-md" style="min-width: 250px;">
                        <template v-slot:append>
                            <q-icon name="search" />
                        </template>
                    </q-input>
                ''')

                refs['archive_files_table'].add_slot('body-cell-size_bytes', '''
                    <q-td :props="props" class="text-right">
                        <span class="text-sm">
                            {{ props.row.size_bytes < 1024
                                ? props.row.size_bytes + ' B'
                                : props.row.size_bytes < 1048576
                                    ? (props.row.size_bytes / 1024).toFixed(1) + ' KB'
                                    : (props.row.size_bytes / 1048576).toFixed(1) + ' MB' }}
                        </span>
                    </q-td>
                ''')

                refs['archive_files_table'].add_slot('body-cell-actions', '''
                    <q-td :props="props" class="text-center">
                        <q-btn flat dense round icon="document_scanner" size="sm"
                               :color="props.row.has_json_sidecar ? 'green' : 'red'"
                               @click.stop="$parent.$emit('ocr-file', props.row.filename)">
                            <q-tooltip>{{ props.row.has_json_sidecar ? 'View receipt (JSON)' : 'Run OCR (Bedrock)' }}</q-tooltip>
                        </q-btn>
                    </q-td>
                ''')
                refs['archive_files_table'].on(
                    'ocr-file', lambda e: on_ocr_file(e.args),
                )

                with ui.row().classes('w-full justify-end gap-2 mt-4'):
                    ui.button('Cancel', on_click=match_dialog.close).props('flat')
                    ui.button('Confirm File Match', icon='attach_file',
                              on_click=on_confirm_file_match).props('color=primary')

            # === Tab 3: Implicit Justification ===
            with ui.tab_panel('implicit'):
                ui.label(
                    'Mark this transaction as implicitly justified. '
                    'The accounting team has the supporting information.'
                ).classes('text-sm text-gray-500 mb-4')

                refs['implicit_note_input'] = ui.textarea(
                    label='Note (optional)',
                    placeholder='Optional: reason for implicit justification',
                ).classes('w-full mb-4')

                with ui.row().classes('w-full justify-end gap-2 mt-4'):
                    ui.button('Cancel', on_click=match_dialog.close).props('flat')
                    ui.button('Confirm Implicit', icon='verified',
                              on_click=on_confirm_implicit_match).props('color=primary')

    # Page content
    with layout('Outbound Justification'):

        # Header card
        with ui.card().classes('w-full mb-4'):
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
                ui.button('Load', icon='search', on_click=load_data).props('color=primary')

                ui.space()

                refs['total_badge'] = ui.badge('Total: 0', color='blue').classes(
                    'text-sm px-3 py-1 cursor-pointer opacity-50'
                ).props('outline')
                refs['total_badge'].on('click', lambda: on_filter_click('total'))

                refs['matched_badge'] = ui.badge('Matched: 0', color='green').classes(
                    'text-sm px-3 py-1 cursor-pointer opacity-50'
                ).props('outline')
                refs['matched_badge'].on('click', lambda: on_filter_click('matched'))

                refs['unmatched_badge'] = ui.badge('Unmatched: 0', color='red').classes(
                    'text-sm px-3 py-1 cursor-pointer'
                )
                refs['unmatched_badge'].on('click', lambda: on_filter_click('unmatched'))

                refs['rate_label'] = ui.label('Match Rate: 0.0%').classes(
                    'text-sm font-semibold text-gray-600'
                )

            # AI auto-match + status row
            with ui.row().classes('w-full items-center gap-2 mt-2'):
                with ui.button(icon='receipt_long',
                               on_click=_open_manage_dialog).props(
                    'flat color=indigo dense'
                ).tooltip('Manage imported receipts'):
                    refs['scan_badge'] = ui.badge('0', color='red').props(
                        'floating'
                    )
                    refs['scan_badge'].set_visibility(False)
                ui.button('Import Receipts', icon='file_upload',
                          on_click=on_start_import).props('flat color=brown dense')
                ui.button('Auto Match', icon='auto_fix_high',
                          on_click=on_auto_match).props('flat color=teal dense')
                ui.space()
                refs['status_label'] = ui.label(
                    'Select month/year and click Load'
                ).classes('text-sm text-gray-500')

        # Transactions table
        with ui.card().classes('w-full'):
            ui.label('Outbound Transactions').classes('text-lg font-semibold mb-2')
            ui.label(
                'Match outbound bank transactions to supplier invoices'
            ).classes('text-xs text-gray-500 mb-2')

            # Export button
            def on_export_csv():
                """Export the currently filtered transactions to CSV."""
                import csv as csv_mod
                table = refs.get('transactions_table')
                if not table or not table.rows:
                    ui.notify('No data to export', type='warning')
                    return
                export_cols = [c for c in tx_columns if c['name'] != 'actions']
                buf = io.StringIO()
                buf.write('\ufeff')  # BOM for Excel
                writer = csv_mod.writer(buf)
                writer.writerow([c['label'] for c in export_cols])
                for row in table.rows:
                    writer.writerow([row.get(c['field'], '') for c in export_cols])
                month_name = month_names.get(state['month'], state['month'])
                filename = f'outbound_{month_name}_{state["year"]}.csv'
                ui.download(buf.getvalue().encode('utf-8-sig'), filename)

            with ui.row().classes('w-full items-center justify-between mb-3'):
                ui.button(
                    'Export CSV', icon='download', on_click=on_export_csv,
                ).props('flat dense color=primary')

            # Filter inputs
            with ui.row().classes('w-full items-end gap-3 mb-3'):
                ui.input(
                    label='Libelle', placeholder='Search libelle...',
                    on_change=lambda e: (state.update(filter_libelle=e.value), _apply_filter()),
                ).props('dense clearable').classes('w-60')
                ui.input(
                    label='Type', placeholder='e.g. VIR, PRLV...',
                    on_change=lambda e: (state.update(filter_type=e.value), _apply_filter()),
                ).props('dense clearable').classes('w-40')
                ui.input(
                    label='Amount', placeholder='Exact or partial...',
                    on_change=lambda e: (state.update(filter_amount=e.value), _apply_filter()),
                ).props('dense clearable').classes('w-40')

            tx_columns = [
                {'name': 'Date_operation', 'label': 'Date', 'field': 'Date_operation',
                 'align': 'center', 'sortable': True},
                {'name': 'Libelle', 'label': 'Libelle', 'field': 'Libelle',
                 'align': 'left', 'sortable': True},
                {'name': 'Qualifier', 'label': 'Type', 'field': 'Qualifier',
                 'align': 'left', 'sortable': True},
                {'name': 'Montant', 'label': 'Amount', 'field': 'Montant',
                 'align': 'right', 'sortable': True},
                {'name': 'match_status', 'label': 'Status', 'field': 'match_status',
                 'align': 'center', 'sortable': True},
                {'name': 'supplier_name', 'label': 'Supplier', 'field': 'supplier_name',
                 'align': 'left', 'sortable': True},
                {'name': 'facture_num', 'label': 'Facture', 'field': 'facture_num',
                 'align': 'left'},
                {'name': 'actions', 'label': 'Actions', 'field': 'TransactionID',
                 'align': 'center'},
            ]

            refs['transactions_table'] = ui.table(
                columns=tx_columns,
                rows=[],
                row_key='TransactionID',
                pagination=50,
            ).classes('w-full')

            # --- Custom table slots ---

            # Montant: formatted currency
            refs['transactions_table'].add_slot('body-cell-Montant', '''
                <q-td :props="props" class="text-right">
                    <span class="font-medium text-red-600">
                        {{ props.row.Montant != null
                            ? props.row.Montant.toLocaleString('fr-FR', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                            : '0.00' }}
                    </span>
                </q-td>
            ''')

            # Status: colored badges with match type indicator
            refs['transactions_table'].add_slot('body-cell-match_status', '''
                <q-td :props="props" class="text-center">
                    <q-badge v-if="props.row.match_status === 'CONFIRMED'" color="green" outline>
                        <q-icon name="check_circle" size="xs" class="q-mr-xs" />
                        Matched
                    </q-badge>
                    <q-badge v-else-if="props.row.match_status === 'PARTIALLY_MATCHED'" color="amber" outline>
                        <q-icon name="timelapse" size="xs" class="q-mr-xs" />
                        Partial
                    </q-badge>
                    <q-badge v-else color="red" outline>
                        <q-icon name="help_outline" size="xs" class="q-mr-xs" />
                        Unmatched
                    </q-badge>
                </q-td>
            ''')

            # Libelle
            refs['transactions_table'].add_slot('body-cell-Libelle', '''
                <q-td :props="props" style="max-width: 300px; white-space: normal;">
                    <div>{{ props.row.Libelle || '-' }}</div>
                </q-td>
            ''')

            # Supplier name
            refs['transactions_table'].add_slot('body-cell-supplier_name', '''
                <q-td :props="props">
                    <span v-if="props.row.supplier_name">{{ props.row.supplier_name }}</span>
                    <span v-else class="text-gray-400">-</span>
                </q-td>
            ''')

            # Facture number / justification info
            refs['transactions_table'].add_slot('body-cell-facture_num', '''
                <q-td :props="props">
                    <span v-if="props.row.facture_num">{{ props.row.facture_num }}</span>
                    <span v-else-if="props.row.match_type === 'FILE' && props.row.justification_filename"
                          class="text-blue-600 text-xs">
                        <q-icon name="attach_file" size="xs" class="q-mr-xs" />
                        {{ props.row.justification_filename }}
                    </span>
                    <span v-else-if="props.row.match_type === 'IMPLICIT'" class="text-purple-600 italic text-xs">
                        Implicit<span v-if="props.row.justification_note"> - {{ props.row.justification_note }}</span>
                    </span>
                    <span v-else class="text-gray-400">-</span>
                </q-td>
            ''')

            # Actions: conditional buttons per status
            refs['transactions_table'].add_slot('body-cell-actions', '''
                <q-td :props="props" class="text-center">
                    <div v-if="props.row.match_status === 'UNMATCHED'">
                        <q-btn flat dense icon="link" color="primary" size="sm"
                               @click.stop="$parent.$emit('match-tx', props.row.TransactionID)"
                               label="Match" />
                    </div>
                    <div v-else-if="props.row.match_status === 'CONFIRMED' || props.row.match_status === 'PARTIALLY_MATCHED'" class="q-gutter-xs">
                        <q-btn flat dense icon="add_link" color="primary" size="sm"
                               @click.stop="$parent.$emit('match-tx', props.row.TransactionID)"
                               label="Match" />
                        <q-btn flat dense icon="link_off" color="negative" size="sm"
                               @click.stop="$parent.$emit('delete-match', props.row.TransactionID)"
                               label="Un-justify" />
                    </div>
                </q-td>
            ''')

            # Wire events
            refs['transactions_table'].on('match-tx', lambda e: on_match_click(e.args))
            refs['transactions_table'].on('delete-match', lambda e: on_delete_match(e.args))

    # Initialise scanned receipts badge on page load
    _refresh_scan_badge()
