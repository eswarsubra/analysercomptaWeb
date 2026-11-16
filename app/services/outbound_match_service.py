"""Outbound Match Service - wraps Core's OutboundMatchService for web operations."""
import io
import re
import logging
from pathlib import Path
from datetime import datetime as dt
from typing import Optional

from sqlalchemy import extract

from analysercomptacore.services import OutboundMatchService as CoreOutboundMatchService
from analysercomptacore.services import SupplierService as CoreSupplierService
from analysercomptacore.services import ArchiveService
from analysercomptacore.models.suppliers import SupplierProduct, SupplierFactItem, SupplierFacture
from app.database import get_db
from app.services.scan_session_store import ScanSessionStore

logger = logging.getLogger(__name__)

OCR_MAX_IMAGE_WIDTH = 1500  # px – sufficient for invoice text


def _resize_image_bytes(image_bytes: bytes, max_width: int = OCR_MAX_IMAGE_WIDTH) -> bytes:
    """Downscale an image if wider than max_width, return JPEG bytes."""
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes))
    if img.width <= max_width:
        return image_bytes
    ratio = max_width / img.width
    new_size = (max_width, int(img.height * ratio))
    img = img.resize(new_size, Image.LANCZOS)
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    logger.info(f"Resized image: {img.width}x{img.height} ({len(image_bytes)} -> {buf.tell()} bytes)")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# OCR sidecar JSON parser
# ---------------------------------------------------------------------------

# Matches both formats: "1,286.98" (period decimal) and "60,00" (comma decimal).
# Also handles optional currency suffix/prefix like €, EGP, EUR etc.
_AMT_PERIOD_RE = re.compile(r'(\d{1,3}(?:,\d{3})*\.\d{2})\s*(?:€|EGP|EUR|USD|MAD|GBP)?')
_AMT_COMMA_RE = re.compile(r'(\d{1,3}(?:\.\d{3})*,\d{2})\s*(?:€|EGP|EUR|USD|MAD|GBP)?')


def _detect_decimal_style(text: str) -> str:
    """Detect whether the OCR text uses period or comma as decimal separator.

    Heuristic: look for currency-adjacent patterns.  ``60,00 €`` → comma,
    ``1,286.98EGP`` → period.  Default to period.
    """
    # "xx,xx €" or "xx,xx€" → European comma style
    if re.search(r'\d,\d{2}\s*€', text):
        return 'comma'
    # "xx.xxEGP" or "xx.xx EUR" → period style
    if re.search(r'\d\.\d{2}\s*(?:EGP|USD|GBP|MAD)', text):
        return 'period'
    # Count which pattern appears more
    period_hits = len(_AMT_PERIOD_RE.findall(text))
    comma_hits = len(_AMT_COMMA_RE.findall(text))
    return 'comma' if comma_hits > period_hits else 'period'


def _parse_amount(text: str, style: str) -> float | None:
    """Return the first decimal amount found in *text*, or None."""
    if style == 'comma':
        m = _AMT_COMMA_RE.search(text)
        if m:
            return float(m.group(1).replace('.', '').replace(',', '.'))
    else:
        m = _AMT_PERIOD_RE.search(text)
        if m:
            return float(m.group(1).replace(',', ''))
    return None


def _all_amounts(text: str, style: str) -> list[float]:
    """Return every decimal amount found in *text*."""
    results = []
    regex = _AMT_COMMA_RE if style == 'comma' else _AMT_PERIOD_RE
    for m in regex.finditer(text):
        raw = m.group(1)
        if style == 'comma':
            results.append(float(raw.replace('.', '').replace(',', '.')))
        else:
            results.append(float(raw.replace(',', '')))
    return results


def _parse_ocr_sidecar(data: dict) -> dict:
    """Parse a JSON sidecar with ``supplier`` + ``ocrText`` into a structured OCR result.

    Handles multiple receipt formats (European comma decimals, period decimals,
    various keyword languages, etc.).

    Returns a dict with keys: supplier_name, facture_num, facture_date,
    amount_ht, amount_tva, amount_ttc, line_items.
    """
    supplier_name = data.get('supplier') or None
    ocr_text = data.get('ocrText') or ''

    if not ocr_text:
        return {
            'supplier_name': supplier_name,
            'facture_num': None, 'facture_date': None,
            'amount_ht': None, 'amount_tva': None, 'amount_ttc': None,
            'line_items': [],
        }

    style = _detect_decimal_style(ocr_text)
    lines = [l.strip() for l in ocr_text.split('\n') if l.strip()]

    # --- Invoice / check number ---
    facture_num = None
    _inv_re = re.compile(
        r'(CHK|INV|Invoice|Facture|Receipt|Bill|Check|Ticket)\s*#?\s*(\S+)',
        re.IGNORECASE,
    )
    for line in lines:
        m = _inv_re.match(line)
        if m:
            facture_num = f"{m.group(1)} {m.group(2)}"
            break
    # Also try "N Ticket vente XXXX" or "Ticket XXXX"
    if not facture_num:
        for line in lines:
            m = re.search(r'(?:N\s+)?Ticket\s+(?:vente\s+)?(\d+)', line, re.IGNORECASE)
            if m:
                facture_num = f"Ticket {m.group(1)}"
                break

    # --- Date ---
    facture_date = None
    _date_patterns = [
        # "10 Feb'26"  /  "10 Feb 26"  /  "10 Feb 2026"
        re.compile(
            r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
            r"['\s]?\s*(\d{2,4})", re.IGNORECASE,
        ),
        # dd/mm/yyyy  dd-mm-yyyy  dd.mm.yyyy
        re.compile(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})'),
        # dd/mm/yy
        re.compile(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2})\b'),
        # yyyy-mm-dd
        re.compile(r'(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})'),
    ]
    for line in lines:
        for pat in _date_patterns:
            m = pat.search(line)
            if m:
                facture_date = m.group(0).strip()
                break
        if facture_date:
            break

    # --- Collect every amount in the full text ---
    every_amount: list[float] = []
    for line in lines:
        every_amount.extend(_all_amounts(line, style))

    # --- Labeled amounts ---
    # Search current line + up to 3 lines ahead for the nearest amount.
    def _nearby_amount(idx: int, window: int = 3) -> float | None:
        for j in range(idx, min(idx + window, len(lines))):
            amt = _parse_amount(lines[j], style)
            if amt:
                return amt
        return None

    amount_tva = None
    amount_ht = None

    _vat_re = re.compile(
        r'\b(vat|tva|mt\.?\s*tva|taxe|tax|gst)\b', re.IGNORECASE,
    )
    _ht_re = re.compile(
        r'\b(sub\s*total|subtotal|total\s*ht|montant\s*h[ti]'
        r'|mt\.?\s*h\.?[ti]\.?|net\s*ht|h\.?t\.?)\b',
        re.IGNORECASE,
    )
    _ttc_re = re.compile(
        r'\b(net\s*ttc|total\s*ttc|montant\s*ttc|mt\.?\s*ttc|t\.?t\.?c\.?)\b',
        re.IGNORECASE,
    )

    amount_ttc_labeled = None

    for i, line in enumerate(lines):
        # Take the first match only for each label
        if _vat_re.search(line) and not _ht_re.search(line):
            if amount_tva is None:
                amt = _nearby_amount(i)
                if amt is not None:
                    amount_tva = amt
        elif _ht_re.search(line):
            if amount_ht is None:
                amt = _nearby_amount(i)
                if amt is not None:
                    amount_ht = amt
        elif _ttc_re.search(line):
            if amount_ttc_labeled is None:
                amt = _nearby_amount(i)
                if amt is not None:
                    amount_ttc_labeled = amt

    # TTC: prefer labeled TTC, otherwise largest amount in the receipt
    amount_ttc = amount_ttc_labeled or (max(every_amount) if every_amount else None)

    # Derive HT if not explicitly found
    if not amount_ht and amount_ttc and amount_tva:
        amount_ht = round(amount_ttc - amount_tva, 2)

    # --- Line items ---
    line_items: list[dict] = []

    # "2 CK Shawerma $ @ 133.40 266.80"  or  "2HibiscUs Limgade @ 54.72 109.44"
    item_at_re = re.compile(
        r'^(\d+)\s*(.+?)\s+@\s*([\d.,]+)\s+([\d.,]+)$'
    )
    # "A 4x L.Lait Ríz Lait Van111 2,45 9,80" — qty x description price price
    item_qty_x_re = re.compile(
        r'^[A-Z]?\s*(\d+)\s*x\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)$', re.IGNORECASE,
    )
    # "1 Mint Limead 84.85" or "LOT 12 BAR OU DAURA 60,00 €"
    # Require a decimal separator (. or ,) in the amount to avoid matching zip codes etc.
    item_simple_re = re.compile(
        r'^(\d+)\s+(.+?)\s+(\d[\d.]*[.,]\d{2})\s*(?:€|EGP|EUR|USD|MAD|GBP)?$'
    )
    skip_kw = {
        'total', 'vat', 'tva', 'tax', 'service', 'subtotal', 'charge',
        'montant', 'net', 'grand', 'due', 'gst', 'especes', 'carte',
        'bancaire', 'siret', 'naf', 'taux', 'brut',
    }

    def _to_float(s: str) -> float:
        s = s.strip().rstrip('€').strip()
        if style == 'comma':
            return float(s.replace('.', '').replace(',', '.'))
        return float(s.replace(',', ''))

    for line in lines:
        # @ pattern: qty desc @ unit total
        m = item_at_re.match(line)
        if m:
            qty = int(m.group(1))
            desc = m.group(2).strip().rstrip('$').strip()
            unit_price = _to_float(m.group(3))
            total_price = _to_float(m.group(4))
            line_items.append({
                'description': desc, 'quantity': qty,
                'unit_price': unit_price, 'total_price': total_price,
            })
            continue

        # Nx pattern: qty x desc unit total
        m = item_qty_x_re.match(line)
        if m:
            qty = int(m.group(1))
            desc = m.group(2).strip()
            unit_price = _to_float(m.group(3))
            total_price = _to_float(m.group(4))
            line_items.append({
                'description': desc, 'quantity': qty,
                'unit_price': unit_price, 'total_price': total_price,
            })
            continue

        # Simple: qty desc total
        m = item_simple_re.match(line)
        if m:
            qty = int(m.group(1))
            desc = m.group(2).strip()
            if any(kw in desc.lower() for kw in skip_kw):
                continue
            total_price = _to_float(m.group(3))
            unit_price = round(total_price / qty, 2) if qty > 0 else total_price
            line_items.append({
                'description': desc, 'quantity': qty,
                'unit_price': unit_price, 'total_price': total_price,
            })

    return {
        'supplier_name': supplier_name,
        'facture_num': facture_num,
        'facture_date': facture_date,
        'amount_ht': amount_ht,
        'amount_tva': amount_tva,
        'amount_ttc': amount_ttc,
        'line_items': line_items,
    }


# Keyword patterns for implicit institutional justification.
# Each entry: (list of keywords to match in Libelle, justification note)
IMPLICIT_PATTERNS = [
    (['URSSAF', 'DGFIP'],                       'URSSAF social charges'),
    (['SALAIRE', 'PAIE', 'VIREMENT SALAIRE','versement epar-enfants','Renum'],   'Salary payment'),
    (['TRESOR PUBLIC', 'DGFIP'],                'Tax payment (Treasury)'),
    (['RSI'],                                    'RSI social charges'),
    (['ENGIE'],                                  'Energy bill'),
]

# Fallback alias patterns for supplier name matching in bank Libelles.
# Key: keyword to match in Libelle (case-insensitive), Value: supplier name as stored in DB.
SUPPLIER_ALIAS_PATTERNS = {
    'DS RESTAURATION': 'DSI Val',
}


class OutboundMatchService:
    """Service for outbound transaction matching - wraps Core service + LLM integration."""

    # --- Core wrappers ---

    @staticmethod
    def get_transactions_for_month(month: int, year: int) -> list[dict]:
        """Get outbound transactions enriched with match status."""
        with get_db() as db:
            return CoreOutboundMatchService.get_outbound_transactions_for_month(
                db, month, year
            )

    @staticmethod
    def get_summary(month: int, year: int) -> dict:
        """Get match summary counts for a month."""
        with get_db() as db:
            return CoreOutboundMatchService.get_match_summary(db, month, year)

    @staticmethod
    def create_manual_match(
        transaction_id: int,
        facture_id: int,
        supplier_id: int,
    ) -> dict:
        """Manually link a transaction to an existing facture."""
        with get_db() as db:
            match = CoreOutboundMatchService.create_match(
                db,
                transaction_id=transaction_id,
                match_type='MANUAL',
                supplier_id=supplier_id,
                facture_id=facture_id,
                match_status='CONFIRMED',
            )
            return match.to_dict()

    @staticmethod
    def confirm_match(match_id: int) -> dict:
        """Confirm a pending match."""
        with get_db() as db:
            match = CoreOutboundMatchService.confirm_match(db, match_id)
            return match.to_dict()

    @staticmethod
    def reject_match(match_id: int) -> None:
        """Reject and delete a pending match."""
        with get_db() as db:
            CoreOutboundMatchService.reject_match(db, match_id)

    @staticmethod
    def delete_match(match_id: int) -> None:
        """Delete a confirmed match (un-justify)."""
        with get_db() as db:
            CoreOutboundMatchService.delete_match(db, match_id)

    @staticmethod
    def get_matched_factures(transaction_id: int) -> list[dict]:
        """Get already-matched facture details for a transaction."""
        with get_db() as db:
            return CoreOutboundMatchService.get_matched_factures_for_transaction(db, transaction_id)

    @staticmethod
    def delete_matches_for_transaction(transaction_id: int) -> int:
        """Delete all matches for a transaction (un-justify completely)."""
        with get_db() as db:
            return CoreOutboundMatchService.delete_matches_for_transaction(db, transaction_id)

    @staticmethod
    def find_candidates(
        supplier_id: int,
        amount: float,
        transaction_date: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        exclude_transaction_id: Optional[int] = None,
    ) -> list[dict]:
        """Find candidate factures for linking."""
        with get_db() as db:
            return CoreOutboundMatchService.find_candidate_factures(
                db, supplier_id, amount, transaction_date,
                date_from=date_from, date_to=date_to,
                exclude_transaction_id=exclude_transaction_id,
            )

    # --- File & Implicit justification ---

    @staticmethod
    def create_file_match(transaction_id: int, filename: str) -> dict:
        """Justify a transaction with an archived file."""
        with get_db() as db:
            match = CoreOutboundMatchService.create_match(
                db,
                transaction_id=transaction_id,
                match_type='FILE',
                match_status='CONFIRMED',
                justification_filename=filename,
            )
            return match.to_dict()

    @staticmethod
    def create_implicit_match(transaction_id: int, note: str = '') -> dict:
        """Justify a transaction implicitly (accounting has the information)."""
        with get_db() as db:
            match = CoreOutboundMatchService.create_match(
                db,
                transaction_id=transaction_id,
                match_type='IMPLICIT',
                match_status='CONFIRMED',
                justification_note=note or None,
            )
            return match.to_dict()

    # --- Justification source folder ---

    @staticmethod
    def get_default_archive_dir() -> str:
        """Return the configured archive invoice directory as an absolute path."""
        return str(Path(ArchiveService._get_archive_dir()).resolve())

    @staticmethod
    def _resolve_source_dir(directory: Optional[str]) -> Path:
        """Return the folder to use for file justification (default: archive dir)."""
        if directory:
            return Path(directory).expanduser().resolve()
        return Path(ArchiveService._get_archive_dir()).resolve()

    @staticmethod
    def _is_default_dir(path: Path) -> bool:
        try:
            return path.resolve() == Path(ArchiveService._get_archive_dir()).resolve()
        except Exception:
            return False

    @staticmethod
    def list_filesystem_roots() -> list[str]:
        """List filesystem roots (drive letters on Windows, '/' elsewhere)."""
        import os
        import string
        if os.name == 'nt':
            return [f'{d}:/' for d in string.ascii_uppercase if os.path.exists(f'{d}:/')]
        return ['/']

    @staticmethod
    def list_subdirectories(directory: str) -> list[str]:
        """List immediate (non-hidden) subdirectory names of a folder, sorted."""
        path = Path(directory)
        subdirs = []
        try:
            for child in path.iterdir():
                try:
                    if child.is_dir() and not child.name.startswith(('.', '$')):
                        subdirs.append(child.name)
                except OSError:
                    continue
        except OSError as e:
            logger.warning(f"Cannot list {directory}: {e}")
        return sorted(subdirs, key=str.lower)

    @staticmethod
    def list_archive_files(directory: Optional[str] = None) -> list[dict]:
        """List files available in the justification folder, excluding already-used files.

        Args:
            directory: Folder to scan. Defaults to the configured archive invoice directory.

        Each row has 'filename' (relative to the folder) and 'justification_name' —
        the value stored on the match: the relative name for the default archive
        directory, the absolute path for any other folder.
        """
        from analysercomptacore.models.banking import OutboundMatch
        source_dir = OutboundMatchService._resolve_source_dir(directory)
        is_default = OutboundMatchService._is_default_dir(source_dir)
        all_files = ArchiveService.list_archived_files(source_dir)

        # Build set of JSON sidecar basenames (without extension) for quick lookup
        json_basenames = {
            f['filename'].rsplit('.', 1)[0]
            for f in all_files
            if f['filename'].lower().endswith('.json')
        }

        with get_db() as db:
            used = db.query(OutboundMatch.justification_filename).filter(
                OutboundMatch.match_type == 'FILE',
                OutboundMatch.justification_filename.isnot(None),
            ).all()
            used_filenames = {row[0] for row in used}

        results = []
        for f in all_files:
            f['justification_name'] = (
                f['filename'] if is_default
                else (source_dir / f['filename']).as_posix()
            )
            if f['justification_name'] in used_filenames:
                continue
            if f['filename'].lower().endswith('.json'):
                continue
            basename = f['filename'].rsplit('.', 1)[0]
            f['has_json_sidecar'] = basename in json_basenames
            results.append(f)
        return results

    # --- 3-step auto-matching pipeline ---

    @staticmethod
    def auto_match(month: int, year: int) -> dict:
        """Run 3-step auto-matching for all unmatched outbound transactions.

        Step 1: Deterministic facture match (supplier name in Libelle + exact amount + same month)
        Step 2: Implicit institutional match (keyword patterns for salary, URSSAF, TVA, etc.)
        Step 3: Scanned receipt file match (OCR data from ScanSessionStore)

        Returns:
            Dict with: processed, facture_matched, implicit_matched, file_matched, skipped, errors
        """
        stats = {
            'processed': 0,
            'facture_matched': 0,
            'implicit_matched': 0,
            'file_matched': 0,
            'skipped': 0,
            'errors': 0,
        }

        with get_db() as db:
            all_tx = CoreOutboundMatchService.get_outbound_transactions_for_month(
                db, month, year
            )
            unmatched = [t for t in all_tx if t['match_status'] == 'UNMATCHED']
            stats['processed'] = len(unmatched)

            if not unmatched:
                return stats

            # Load suppliers once for Steps 1 and 3
            suppliers = CoreOutboundMatchService.get_all_suppliers(db)

            # === Step 1: Deterministic facture match ===
            matched_tx_ids = set()
            supplier_by_name = {s['name'].lower(): s for s in suppliers}
            for tx in unmatched:
                try:
                    libelle = (tx.get('Libelle') or '').lower()
                    tx_amount = abs(float(tx.get('Montant', 0)))
                    tx_date_str = tx.get('Date_operation', '')

                    if not libelle or not tx_amount:
                        continue

                    try:
                        tx_date = dt.strptime(tx_date_str, '%Y-%m-%d')
                    except (ValueError, TypeError):
                        continue

                    # Find supplier whose name appears in the Libelle
                    matched_supplier = None
                    for s in suppliers:
                        if s['name'].lower() in libelle:
                            matched_supplier = s
                            break

                    # Fallback: check alias patterns
                    if not matched_supplier:
                        for alias, supplier_name in SUPPLIER_ALIAS_PATTERNS.items():
                            if alias.lower() in libelle:
                                matched_supplier = supplier_by_name.get(supplier_name.lower())
                                break

                    if not matched_supplier:
                        continue

                    # Find factures: exact amount + same month
                    factures = db.query(SupplierFacture).filter(
                        SupplierFacture.idsupplier == matched_supplier['id'],
                        SupplierFacture.factmontantttc == tx_amount,
                        extract('month', SupplierFacture.factDate) == tx_date.month,
                        extract('year', SupplierFacture.factDate) == tx_date.year,
                    ).all()

                    if not factures:
                        continue

                    # Skip fully consumed factures
                    facture_ids = [f.idFacture for f in factures]
                    matched_amounts = CoreOutboundMatchService._compute_facture_matched_amounts(
                        db, facture_ids
                    )

                    matched_facture = None
                    for f in factures:
                        ttc = float(f.factmontantttc or 0)
                        already_consumed = matched_amounts.get(f.idFacture, 0)
                        if ttc - already_consumed >= tx_amount - 0.01:
                            matched_facture = f
                            break

                    if not matched_facture:
                        continue

                    CoreOutboundMatchService.create_match(
                        db,
                        transaction_id=tx['TransactionID'],
                        match_type='AUTO',
                        supplier_id=matched_supplier['id'],
                        facture_id=matched_facture.idFacture,
                        match_status='CONFIRMED',
                    )
                    matched_tx_ids.add(tx['TransactionID'])
                    stats['facture_matched'] += 1

                except Exception as e:
                    logger.error(f"Step 1 error for tx {tx.get('TransactionID')}: {e}")
                    stats['errors'] += 1

            # === Step 2: Implicit institutional match ===
            still_unmatched = [t for t in unmatched if t['TransactionID'] not in matched_tx_ids]
            for tx in still_unmatched:
                try:
                    libelle = (tx.get('Libelle') or '').lower()
                    if not libelle:
                        continue

                    note = None
                    for keywords, justification_note in IMPLICIT_PATTERNS:
                        if any(kw.lower() in libelle for kw in keywords):
                            note = justification_note
                            break

                    if not note:
                        continue

                    CoreOutboundMatchService.create_match(
                        db,
                        transaction_id=tx['TransactionID'],
                        match_type='IMPLICIT',
                        match_status='CONFIRMED',
                        justification_note=note,
                    )
                    matched_tx_ids.add(tx['TransactionID'])
                    stats['implicit_matched'] += 1

                except Exception as e:
                    logger.error(f"Step 2 error for tx {tx.get('TransactionID')}: {e}")
                    stats['errors'] += 1

            # === Step 3: Scanned receipt file match ===
            still_unmatched = [t for t in unmatched if t['TransactionID'] not in matched_tx_ids]
            if still_unmatched:
                try:
                    available_receipts = ScanSessionStore.get_available_receipts()
                except Exception:
                    available_receipts = {}

                for tx in still_unmatched:
                    try:
                        libelle = (tx.get('Libelle') or '').lower()
                        tx_amount = abs(float(tx.get('Montant', 0)))

                        if not libelle or not tx_amount:
                            continue

                        matched_receipt_id = None
                        matched_filename = None

                        for rid, receipt in available_receipts.items():
                            ocr = receipt.get('ocr_result') or {}
                            ocr_amount = ocr.get('amount_ttc')
                            ocr_supplier = (ocr.get('supplier_name') or '').lower()

                            if not ocr_amount or not ocr_supplier:
                                continue

                            # Exact amount + supplier name in Libelle
                            if abs(float(ocr_amount) - tx_amount) < 0.01 and ocr_supplier in libelle:
                                matched_receipt_id = rid
                                matched_filename = receipt.get('archived_filename')
                                break

                        if not matched_receipt_id or not matched_filename:
                            continue

                        CoreOutboundMatchService.create_match(
                            db,
                            transaction_id=tx['TransactionID'],
                            match_type='FILE',
                            match_status='CONFIRMED',
                            justification_filename=matched_filename,
                        )
                        ScanSessionStore.mark_matched(matched_receipt_id, tx['TransactionID'])
                        # Remove from available so it's not matched again
                        del available_receipts[matched_receipt_id]
                        matched_tx_ids.add(tx['TransactionID'])
                        stats['file_matched'] += 1

                    except Exception as e:
                        logger.error(f"Step 3 error for tx {tx.get('TransactionID')}: {e}")
                        stats['errors'] += 1

        stats['skipped'] = stats['processed'] - stats['facture_matched'] - stats['implicit_matched'] - stats['file_matched'] - stats['errors']
        logger.info(
            f"Auto-match complete: {stats['processed']} processed, "
            f"{stats['facture_matched']} facture, {stats['implicit_matched']} implicit, "
            f"{stats['file_matched']} file, {stats['skipped']} skipped, {stats['errors']} errors"
        )
        return stats

    # --- Create facture + match in one transaction ---

    @staticmethod
    def create_facture_and_match(
        transaction_id: int,
        supplier_id: int,
        facture_num: str,
        facture_date,
        ttc: float,
        ht: float,
        tva: float,
        line_items: list[dict],
        filename: str = 'WEB_MANUAL',
        match_type: str = 'MANUAL',
    ) -> dict:
        """Create facture + products + factitems + outbound match in one transaction.

        Args:
            transaction_id: Bank transaction TransactionID.
            supplier_id: Supplier ID.
            facture_num: Invoice number.
            facture_date: Invoice date (datetime or date).
            ttc: Amount TTC.
            ht: Amount HT.
            tva: Amount TVA.
            line_items: List of dicts, each with:
                - product_id: existing product ID, or None for new product
                - code, designation, unitprice, tva, category: new product fields (when product_id is None)
                - quantity: line quantity
                - item_price: line total
                - unit_price_snap: unit price at time of invoice
            filename: Source filename ('WEB_MANUAL' or archived image filename from OCR).
            match_type: 'MANUAL' or 'VISION_OCR'.

        Returns:
            Dict with facture_id, match_id, products_created.
        """
        with get_db() as db:
            # 1. Create facture
            facture_id = CoreSupplierService.persist_invoice(
                db, supplier_id, facture_num, facture_date, ttc, ht, tva, filename
            )

            # 2. Process line items
            products_created = 0
            for item in line_items:
                product_id = item.get('product_id')

                # Create new product if needed
                if not product_id:
                    new_product = SupplierProduct(
                        code=item['code'],
                        designation=item['designation'],
                        unitprice=item['unitprice'],
                        tva=item.get('tva'),
                        category=item.get('category'),
                        idsupplier=supplier_id,
                    )
                    db.add(new_product)
                    db.flush()
                    product_id = new_product.idsupplierproduct
                    products_created += 1

                # Create fact item
                fact_item = SupplierFactItem(
                    idsupplier=supplier_id,
                    idsupplierfacture=facture_id,
                    idsupplierproduct=product_id,
                    quantity=item['quantity'],
                    itemPrice=item['item_price'],
                    unitPriceSnap=item['unit_price_snap'],
                )
                db.add(fact_item)
                db.flush()

            # 3. Create outbound match
            match = CoreOutboundMatchService.create_match(
                db,
                transaction_id=transaction_id,
                match_type=match_type,
                supplier_id=supplier_id,
                facture_id=facture_id,
                match_status='CONFIRMED',
            )

            logger.info(
                f"Created facture+match: facture_id={facture_id}, match_id={match.id}, "
                f"products_created={products_created}, items={len(line_items)}"
            )

            return {
                'facture_id': facture_id,
                'match_id': match.id,
                'products_created': products_created,
            }

    # --- Receipt OCR via InvoiceImagetor ---

    @staticmethod
    def extract_invoice_from_image(image_bytes: bytes, file_extension: str) -> dict:
        """Extract invoice data from a receipt image using InvoiceImagetor.

        Archives the image first (as UNKNOWN), runs OCR, then renames with supplier name.

        Args:
            image_bytes: Raw image bytes.
            file_extension: File extension with dot (e.g., '.jpg').

        Returns:
            Dict with: supplier_name, facture_num, facture_date, amount_ht,
            amount_tva, amount_ttc, line_items, archived_filename
        """
        from analyser_invoice_imagetor import InvoiceAnalyser
        from analyser_invoice_imagetor.config import (
            AppConfig, AWSConfig, BedrockConfig, ValidationConfig,
        )
        from app.config import config

        # Archive image immediately with UNKNOWN name
        archived_filename = ArchiveService.archive_image(
            image_bytes, file_extension, supplier_name=None
        )

        # Configure InvoiceImagetor from web config
        env = config.get_env()
        full_config = config._config.get(env, {})
        llm_config = full_config.get('llm', {})
        bedrock_config = llm_config.get('bedrock', {})

        app_config = AppConfig(
            aws=AWSConfig(region=bedrock_config.get('region', 'us-east-1')),
            bedrock=BedrockConfig(
                model_id=bedrock_config.get('model_id', 'arn:aws:bedrock:us-east-1:857928859285:inference-profile/us.anthropic.claude-sonnet-4-6'),
            ),
            validation=ValidationConfig(enabled=True, min_confidence=0.5),
        )

        analyser = InvoiceAnalyser(app_config)

        try:
            result = analyser.extract(image_bytes)
        except Exception as e:
            logger.error(f"InvoiceImagetor extraction failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'archived_filename': archived_filename,
                'supplier_name': None,
                'facture_num': None,
                'facture_date': None,
                'amount_ht': None,
                'amount_tva': None,
                'amount_ttc': None,
                'line_items': [],
            }

        if not result.success:
            logger.warning(f"Invoice extraction unsuccessful: {result.error_message}")
            return {
                'success': False,
                'error': result.error_message,
                'archived_filename': archived_filename,
                'supplier_name': None,
                'facture_num': None,
                'facture_date': None,
                'amount_ht': None,
                'amount_tva': None,
                'amount_ttc': None,
                'line_items': [],
            }

        inv = result.invoice

        # Rename archived image with supplier name
        if inv.supplier and inv.supplier.name:
            archived_filename = ArchiveService.rename_archived_image(
                archived_filename, inv.supplier.name
            )

        return {
            'success': True,
            'error': None,
            'archived_filename': archived_filename,
            'supplier_name': inv.supplier.name if inv.supplier else None,
            'facture_num': inv.invoice_reference,
            'facture_date': str(inv.invoice_date) if inv.invoice_date else None,
            'amount_ht': inv.total_ht,
            'amount_tva': round(inv.total_ttc - inv.total_ht, 2) if inv.total_ttc and inv.total_ht else None,
            'amount_ttc': inv.total_ttc,
            'line_items': [
                {
                    'description': li.description,
                    'quantity': li.quantity,
                    'unit_price': li.unit_price,
                    'total_price': li.total,
                }
                for li in inv.line_items
            ],
        }

    @staticmethod
    def ocr_archived_image(archived_filename: str, directory: Optional[str] = None) -> dict:
        """Return OCR data for an archived image.

        First checks for a JSON sidecar file with the same basename.
        Falls back to Haiku-based InvoiceImagetor when no JSON is found.
        On success, renames the file with the detected supplier name.

        Returns:
            Dict with same format as extract_invoice_from_image().
        """
        import json as _json
        from app.config import config

        archive_dir = OutboundMatchService._resolve_source_dir(directory)
        image_path = archive_dir / archived_filename

        # --- Try JSON sidecar first ---
        json_path = image_path.with_suffix('.json')
        if json_path.exists():
            try:
                data = _json.loads(json_path.read_text(encoding='utf-8'))
                logger.info(f"Loaded OCR from JSON sidecar: {json_path.name}")
                parsed = _parse_ocr_sidecar(data)
                return {
                    'success': True,
                    'error': None,
                    'source': 'json_sidecar',
                    'archived_filename': archived_filename,
                    **parsed,
                }
            except Exception as e:
                logger.warning(f"Failed to read JSON sidecar {json_path.name}, falling back to LLM OCR: {e}")

        # --- Fallback: Haiku LLM OCR ---
        from analyser_invoice_imagetor import InvoiceAnalyser
        from analyser_invoice_imagetor.config import (
            AppConfig, AWSConfig, BedrockConfig, ValidationConfig,
        )

        if not image_path.exists():
            logger.error(f"Archived image not found: {image_path}")
            return {
                'success': False,
                'error': f'File not found: {archived_filename}',
                'archived_filename': archived_filename,
                'supplier_name': None, 'facture_num': None,
                'facture_date': None, 'amount_ht': None,
                'amount_tva': None, 'amount_ttc': None,
                'line_items': [],
            }

        image_bytes = image_path.read_bytes()

        # Resize to reduce Bedrock payload and processing time
        image_bytes = _resize_image_bytes(image_bytes)

        env = config.get_env()
        full_config = config._config.get(env, {})
        llm_config = full_config.get('llm', {})
        bedrock_config = llm_config.get('bedrock', {})

        app_config = AppConfig(
            aws=AWSConfig(region=bedrock_config.get('region', 'us-east-1')),
            bedrock=BedrockConfig(
                model_id=bedrock_config.get('model_id', 'arn:aws:bedrock:us-east-1:857928859285:inference-profile/us.anthropic.claude-haiku-4-5-v1'),
            ),
            validation=ValidationConfig(enabled=True, min_confidence=0.5),
        )

        analyser = InvoiceAnalyser(app_config)

        try:
            result = analyser.extract(image_bytes)
        except Exception as e:
            logger.error(f"OCR failed for archived image {archived_filename}: {e}")
            return {
                'success': False, 'error': str(e),
                'archived_filename': archived_filename,
                'supplier_name': None, 'facture_num': None,
                'facture_date': None, 'amount_ht': None,
                'amount_tva': None, 'amount_ttc': None,
                'line_items': [],
            }

        if not result.success:
            logger.warning(f"OCR unsuccessful for {archived_filename}: {result.error_message}")
            return {
                'success': False, 'error': result.error_message,
                'archived_filename': archived_filename,
                'supplier_name': None, 'facture_num': None,
                'facture_date': None, 'amount_ht': None,
                'amount_tva': None, 'amount_ttc': None,
                'line_items': [],
            }

        inv = result.invoice

        # Rename archived file with supplier name
        final_filename = archived_filename
        if inv.supplier and inv.supplier.name:
            try:
                final_filename = ArchiveService.rename_archived_image(
                    archived_filename, inv.supplier.name, archive_dir,
                )
            except OSError as e:
                logger.warning(f"Rename failed for {archived_filename}: {e}")

        ocr_result = {
            'success': True, 'error': None,
            'archived_filename': final_filename,
            'supplier_name': inv.supplier.name if inv.supplier else None,
            'facture_num': inv.invoice_reference,
            'facture_date': str(inv.invoice_date) if inv.invoice_date else None,
            'amount_ht': inv.total_ht,
            'amount_tva': round(inv.total_ttc - inv.total_ht, 2) if inv.total_ttc and inv.total_ht else None,
            'amount_ttc': inv.total_ttc,
            'line_items': [
                {
                    'description': li.description,
                    'quantity': li.quantity,
                    'unit_price': li.unit_price,
                    'total_price': li.total,
                }
                for li in inv.line_items
            ],
        }

        return ocr_result
