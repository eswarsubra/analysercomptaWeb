"""ScanSessionStore - user-storage backed store for scanned receipt OCR data.

Stores scanned receipt data in ``app.storage.user['scanned_receipts']``
(server-side, per-user, writable from event handlers) so it persists across
page navigations and is accessible from any page (outbound, factures, etc.).
"""
import copy
import logging
from datetime import datetime

from nicegui import app

logger = logging.getLogger(__name__)

STORAGE_KEY = 'scanned_receipts'


def _save(store: dict) -> None:
    """Persist the store by assigning a fresh copy so NiceGUI detects the change."""
    app.storage.user[STORAGE_KEY] = copy.deepcopy(store)


def _load() -> dict:
    """Read the current store (returns a mutable working copy)."""
    raw = app.storage.user.get(STORAGE_KEY)
    if not raw or not isinstance(raw, dict):
        return {}
    return dict(raw)


class ScanSessionStore:
    """Read/write helper for scanned receipts in user storage."""

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def get_all_receipts() -> dict:
        """Return the full receipts dict (all statuses)."""
        store = _load()
        logger.debug(f"ScanSessionStore.get_all_receipts: {len(store)} receipts")
        return store

    @staticmethod
    def get_available_receipts() -> dict:
        """Return only receipts with status 'ready' (not matched/imported)."""
        result = {
            rid: r for rid, r in _load().items()
            if r.get('status') == 'ready'
        }
        logger.debug(f"ScanSessionStore.get_available_receipts: {len(result)} available")
        return result

    @staticmethod
    def available_count() -> int:
        """Count of receipts with status 'ready'."""
        return sum(
            1 for r in _load().values()
            if r.get('status') == 'ready'
        )

    @staticmethod
    def find_by_filename(filename: str) -> str | None:
        """Reverse lookup: find receipt_id by archived_filename."""
        for rid, r in _load().items():
            if r.get('archived_filename') == filename:
                return rid
        return None

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    def add_receipt(
        receipt_id: str,
        ocr_result: dict | None,
        archived_filename: str | None,
        status: str = 'ready',
    ) -> None:
        """Add a scanned receipt to the store."""
        store = _load()
        store[receipt_id] = {
            'status': status,
            'ocr_result': ocr_result or {},
            'archived_filename': archived_filename,
            'scanned_at': datetime.utcnow().isoformat(),
            'matched_transaction_id': None,
            'imported_as_facture': False,
        }
        _save(store)
        logger.info(f"ScanSessionStore: added receipt {receipt_id} (status={status}), total={len(store)}")

    @staticmethod
    def mark_matched(receipt_id: str, transaction_id: int) -> None:
        """Mark a receipt as used for file justification."""
        store = _load()
        if receipt_id in store:
            store[receipt_id]['status'] = 'matched'
            store[receipt_id]['matched_transaction_id'] = transaction_id
            _save(store)
            logger.info(f"ScanSessionStore: marked {receipt_id} as matched (tx={transaction_id})")

    @staticmethod
    def mark_imported(receipt_id: str) -> None:
        """Mark a receipt as imported into a facture."""
        store = _load()
        if receipt_id in store:
            store[receipt_id]['status'] = 'imported'
            store[receipt_id]['imported_as_facture'] = True
            _save(store)
            logger.info(f"ScanSessionStore: marked {receipt_id} as imported")

    @staticmethod
    def mark_ready(receipt_id: str) -> None:
        """Reset a receipt back to 'ready' (e.g. after a failed import)."""
        store = _load()
        if receipt_id in store:
            store[receipt_id]['status'] = 'ready'
            store[receipt_id]['imported_as_facture'] = False
            store[receipt_id]['matched_transaction_id'] = None
            _save(store)
            logger.info(f"ScanSessionStore: reset {receipt_id} to ready")

    @staticmethod
    def update_ocr(receipt_id: str, ocr_result: dict) -> None:
        """Update a receipt's OCR data (e.g. after on-demand OCR for imported files)."""
        store = _load()
        if receipt_id in store:
            store[receipt_id]['ocr_result'] = ocr_result
            # Update archived_filename if it changed (e.g. renamed with supplier name)
            if ocr_result.get('archived_filename'):
                store[receipt_id]['archived_filename'] = ocr_result['archived_filename']
            _save(store)
            logger.info(f"ScanSessionStore: updated OCR for {receipt_id}")

    @staticmethod
    def remove_receipt(receipt_id: str) -> None:
        """Remove a single receipt from the store."""
        store = _load()
        if receipt_id in store:
            del store[receipt_id]
            _save(store)
            logger.info(f"ScanSessionStore: removed receipt {receipt_id}")

    @staticmethod
    def clear_all() -> None:
        """Remove all receipts from the store."""
        _save({})
        logger.info("ScanSessionStore: cleared all receipts")
