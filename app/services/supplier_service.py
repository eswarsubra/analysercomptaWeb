from typing import Optional

from analysercomptacore.services import SupplierService as CoreSupplierService
from app.database import get_db


class SupplierService:
    """Service for Supplier CRUD operations - wraps Core's SupplierService."""

    @staticmethod
    def get_all() -> list[dict]:
        """Get all suppliers."""
        with get_db() as db:
            return CoreSupplierService.get_all_suppliers(db)

    @staticmethod
    def get_all_with_counts() -> list[dict]:
        """Get all suppliers with product and facture counts."""
        with get_db() as db:
            return CoreSupplierService.get_all_suppliers_with_counts(db)

    @staticmethod
    def get_by_id(supplier_id: int) -> Optional[dict]:
        """Get a supplier by ID."""
        with get_db() as db:
            return CoreSupplierService.get_supplier_by_id(db, supplier_id)

    @staticmethod
    def create(name: str) -> dict:
        """Create a new supplier."""
        with get_db() as db:
            return CoreSupplierService.create_supplier(db, name)

    @staticmethod
    def update(supplier_id: int, name: str) -> Optional[dict]:
        """Update a supplier."""
        with get_db() as db:
            return CoreSupplierService.update_supplier(db, supplier_id, name)

    @staticmethod
    def delete(supplier_id: int) -> bool:
        """Delete a supplier."""
        with get_db() as db:
            return CoreSupplierService.delete_supplier(db, supplier_id)

    @staticmethod
    def search(query: str) -> list[dict]:
        """Search suppliers by name."""
        with get_db() as db:
            return CoreSupplierService.search_suppliers(db, query)
