from typing import Optional

from analysercomptacore.services import SupplierService as CoreSupplierService
from app.database import get_db


class ProductService:
    """Service for SupplierProduct CRUD operations - wraps Core's SupplierService."""

    @staticmethod
    def get_all(supplier_id: Optional[int] = None, category: Optional[str] = None) -> list[dict]:
        """Get all products, optionally filtered by supplier or category."""
        with get_db() as db:
            return CoreSupplierService.get_all_products(db, supplier_id, category)

    @staticmethod
    def get_by_id(product_id: int) -> Optional[dict]:
        """Get a product by ID."""
        with get_db() as db:
            return CoreSupplierService.get_product_by_id(db, product_id)

    @staticmethod
    def create(code: str, designation: str, unitprice: float, tva: str = None,
               category: str = None, idsupplier: int = None) -> dict:
        """Create a new product."""
        with get_db() as db:
            return CoreSupplierService.create_product(
                db,
                code=code,
                designation=designation,
                unitprice=unitprice,
                tva=tva,
                category=category,
                idsupplier=idsupplier
            )

    @staticmethod
    def update(product_id: int, **kwargs) -> Optional[dict]:
        """Update a product."""
        with get_db() as db:
            return CoreSupplierService.update_product(db, product_id, **kwargs)

    @staticmethod
    def delete(product_id: int) -> bool:
        """Delete a product."""
        with get_db() as db:
            return CoreSupplierService.delete_product(db, product_id)

    @staticmethod
    def search(query: str) -> list[dict]:
        """Search products by code or designation."""
        with get_db() as db:
            return CoreSupplierService.search_products(db, query)

    @staticmethod
    def get_categories() -> list[str]:
        """Get all unique categories."""
        with get_db() as db:
            return CoreSupplierService.get_product_categories(db)
