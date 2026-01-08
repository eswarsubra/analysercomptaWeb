from sqlalchemy.orm import Session, joinedload
from typing import Optional
from app.database import get_db
from app.models import Supplier, SupplierProduct


class ProductService:
    """Service for SupplierProduct CRUD operations."""

    @staticmethod
    def get_all(supplier_id: Optional[int] = None, category: Optional[str] = None) -> list[dict]:
        """Get all products, optionally filtered by supplier or category."""
        with get_db() as db:
            query = db.query(SupplierProduct).options(joinedload(SupplierProduct.supplier))

            if supplier_id:
                query = query.filter(SupplierProduct.idsupplier == supplier_id)
            if category:
                query = query.filter(SupplierProduct.category == category)

            products = query.order_by(SupplierProduct.designation).all()
            return [p.to_dict() for p in products]

    @staticmethod
    def get_by_id(product_id: int) -> Optional[dict]:
        """Get a product by ID."""
        with get_db() as db:
            product = db.query(SupplierProduct).options(
                joinedload(SupplierProduct.supplier)
            ).filter(SupplierProduct.idsupplierproduct == product_id).first()
            return product.to_dict() if product else None

    @staticmethod
    def create(code: str, designation: str, unitprice: float, tva: str = None,
               category: str = None, idsupplier: int = None) -> dict:
        """Create a new product."""
        with get_db() as db:
            product = SupplierProduct(
                code=code,
                designation=designation,
                unitprice=unitprice,
                tva=tva,
                category=category,
                idsupplier=idsupplier
            )
            db.add(product)
            db.flush()
            # Reload with supplier info
            db.refresh(product)
            return product.to_dict()

    @staticmethod
    def update(product_id: int, **kwargs) -> Optional[dict]:
        """Update a product."""
        with get_db() as db:
            product = db.query(SupplierProduct).filter(
                SupplierProduct.idsupplierproduct == product_id
            ).first()
            if product:
                for key, value in kwargs.items():
                    if hasattr(product, key):
                        setattr(product, key, value)
                db.flush()
                return product.to_dict()
            return None

    @staticmethod
    def delete(product_id: int) -> bool:
        """Delete a product."""
        with get_db() as db:
            product = db.query(SupplierProduct).filter(
                SupplierProduct.idsupplierproduct == product_id
            ).first()
            if product:
                db.delete(product)
                return True
            return False

    @staticmethod
    def search(query: str) -> list[dict]:
        """Search products by code or designation."""
        with get_db() as db:
            products = db.query(SupplierProduct).options(
                joinedload(SupplierProduct.supplier)
            ).filter(
                (SupplierProduct.code.ilike(f'%{query}%')) |
                (SupplierProduct.designation.ilike(f'%{query}%'))
            ).order_by(SupplierProduct.designation).all()
            return [p.to_dict() for p in products]

    @staticmethod
    def get_categories() -> list[str]:
        """Get all unique categories."""
        with get_db() as db:
            categories = db.query(SupplierProduct.category).distinct().filter(
                SupplierProduct.category.isnot(None)
            ).all()
            return [c[0] for c in categories if c[0]]
