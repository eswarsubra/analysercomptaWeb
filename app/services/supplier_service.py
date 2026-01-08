from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from app.database import get_db
from app.models import Supplier, SupplierProduct, SupplierFacture


class SupplierService:
    """Service for Supplier CRUD operations."""

    @staticmethod
    def get_all() -> list[dict]:
        """Get all suppliers."""
        with get_db() as db:
            suppliers = db.query(Supplier).order_by(Supplier.name).all()
            return [s.to_dict() for s in suppliers]

    @staticmethod
    def get_all_with_counts() -> list[dict]:
        """Get all suppliers with product and facture counts."""
        with get_db() as db:
            suppliers = db.query(
                Supplier,
                func.count(func.distinct(SupplierProduct.idsupplierproduct)).label('product_count'),
                func.count(func.distinct(SupplierFacture.idFacture)).label('facture_count')
            ).outerjoin(
                SupplierProduct, Supplier.idsupplier == SupplierProduct.idsupplier
            ).outerjoin(
                SupplierFacture, Supplier.idsupplier == SupplierFacture.idsupplier
            ).group_by(Supplier.idsupplier).order_by(Supplier.name).all()

            return [{
                'idsupplier': s.Supplier.idsupplier,
                'name': s.Supplier.name,
                'product_count': s.product_count,
                'facture_count': s.facture_count
            } for s in suppliers]

    @staticmethod
    def get_by_id(supplier_id: int) -> Optional[dict]:
        """Get a supplier by ID."""
        with get_db() as db:
            supplier = db.query(Supplier).filter(Supplier.idsupplier == supplier_id).first()
            return supplier.to_dict() if supplier else None

    @staticmethod
    def create(name: str) -> dict:
        """Create a new supplier."""
        with get_db() as db:
            supplier = Supplier(name=name)
            db.add(supplier)
            db.flush()
            return supplier.to_dict()

    @staticmethod
    def update(supplier_id: int, name: str) -> Optional[dict]:
        """Update a supplier."""
        with get_db() as db:
            supplier = db.query(Supplier).filter(Supplier.idsupplier == supplier_id).first()
            if supplier:
                supplier.name = name
                db.flush()
                return supplier.to_dict()
            return None

    @staticmethod
    def delete(supplier_id: int) -> bool:
        """Delete a supplier."""
        with get_db() as db:
            supplier = db.query(Supplier).filter(Supplier.idsupplier == supplier_id).first()
            if supplier:
                db.delete(supplier)
                return True
            return False

    @staticmethod
    def search(query: str) -> list[dict]:
        """Search suppliers by name."""
        with get_db() as db:
            suppliers = db.query(Supplier).filter(
                Supplier.name.ilike(f'%{query}%')
            ).order_by(Supplier.name).all()
            return [s.to_dict() for s in suppliers]
