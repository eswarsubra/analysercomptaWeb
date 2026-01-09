from typing import Optional
from datetime import datetime

from analysercomptacore.services import SupplierService as CoreSupplierService
from app.database import get_db


class FactureService:
    """Service for SupplierFacture operations - wraps Core's SupplierService."""

    @staticmethod
    def get_all(supplier_id: Optional[int] = None,
                date_from: Optional[datetime] = None,
                date_to: Optional[datetime] = None) -> list[dict]:
        """Get all factures, optionally filtered."""
        with get_db() as db:
            return CoreSupplierService.get_all_factures(db, supplier_id, date_from, date_to)

    @staticmethod
    def get_by_id(facture_id: int) -> Optional[dict]:
        """Get a facture by ID with items."""
        with get_db() as db:
            return CoreSupplierService.get_facture_by_id(db, facture_id)

    @staticmethod
    def get_items(facture_id: int) -> list[dict]:
        """Get all items for a facture."""
        with get_db() as db:
            return CoreSupplierService.get_facture_items(db, facture_id)

    @staticmethod
    def get_summary() -> dict:
        """Get summary statistics for factures."""
        with get_db() as db:
            return CoreSupplierService.get_facture_summary(db)

    @staticmethod
    def get_recent(limit: int = 5) -> list[dict]:
        """Get most recent factures."""
        with get_db() as db:
            return CoreSupplierService.get_recent_factures(db, limit)
