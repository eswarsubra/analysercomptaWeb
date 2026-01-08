from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.models import Supplier, SupplierFacture, SupplierFactItem


class FactureService:
    """Service for SupplierFacture operations."""

    @staticmethod
    def get_all(supplier_id: Optional[int] = None,
                date_from: Optional[datetime] = None,
                date_to: Optional[datetime] = None) -> list[dict]:
        """Get all factures, optionally filtered."""
        with get_db() as db:
            query = db.query(SupplierFacture).options(joinedload(SupplierFacture.supplier))

            if supplier_id:
                query = query.filter(SupplierFacture.idsupplier == supplier_id)
            if date_from:
                query = query.filter(SupplierFacture.factDate >= date_from)
            if date_to:
                query = query.filter(SupplierFacture.factDate <= date_to)

            factures = query.order_by(SupplierFacture.factDate.desc()).all()
            return [f.to_dict() for f in factures]

    @staticmethod
    def get_by_id(facture_id: int) -> Optional[dict]:
        """Get a facture by ID with items."""
        with get_db() as db:
            facture = db.query(SupplierFacture).options(
                joinedload(SupplierFacture.supplier),
                joinedload(SupplierFacture.items).joinedload(SupplierFactItem.product)
            ).filter(SupplierFacture.idFacture == facture_id).first()

            if facture:
                result = facture.to_dict()
                result['items'] = [item.to_dict() for item in facture.items]
                return result
            return None

    @staticmethod
    def get_items(facture_id: int) -> list[dict]:
        """Get all items for a facture."""
        with get_db() as db:
            items = db.query(SupplierFactItem).options(
                joinedload(SupplierFactItem.product)
            ).filter(SupplierFactItem.idsupplierfacture == facture_id).all()
            return [item.to_dict() for item in items]

    @staticmethod
    def get_summary() -> dict:
        """Get summary statistics for factures."""
        with get_db() as db:
            total_count = db.query(func.count(SupplierFacture.idFacture)).scalar()
            total_ht = db.query(func.sum(SupplierFacture.factmontantHT)).scalar() or 0
            total_ttc = db.query(func.sum(SupplierFacture.factmontantttc)).scalar() or 0
            total_tva = db.query(func.sum(SupplierFacture.factmontantTVA)).scalar() or 0

            return {
                'count': total_count,
                'total_ht': float(total_ht),
                'total_ttc': float(total_ttc),
                'total_tva': float(total_tva)
            }

    @staticmethod
    def get_recent(limit: int = 5) -> list[dict]:
        """Get most recent factures."""
        with get_db() as db:
            factures = db.query(SupplierFacture).options(
                joinedload(SupplierFacture.supplier)
            ).order_by(SupplierFacture.createdon.desc()).limit(limit).all()
            return [f.to_dict() for f in factures]
