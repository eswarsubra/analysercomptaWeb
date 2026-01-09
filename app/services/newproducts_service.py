from typing import Optional

from analysercomptacore.services import SupplierService as CoreSupplierService
from analysercomptacore.models.suppliers import NEWPRODUCT_STATUS_CHOICES
from app.database import get_db
from app.logging_config import get_logger

logger = get_logger(__name__)


class NewProductsService:
    """Service for SupplierNewProducts operations - wraps Core's SupplierService."""

    @staticmethod
    def get_all(status: Optional[str] = None,
                supplier_id: Optional[str] = None,
                facture_id: Optional[str] = None,
                exclude_closed: bool = False) -> list[dict]:
        """Get all new products, optionally filtered, with supplier name."""
        with get_db() as db:
            return CoreSupplierService.get_all_staging(
                db,
                status=status,
                supplier_id=supplier_id,
                facture_id=facture_id,
                exclude_closed=exclude_closed
            )

    @staticmethod
    def get_by_id(product_id: int) -> Optional[dict]:
        """Get a new product by ID."""
        with get_db() as db:
            return CoreSupplierService.get_staging_by_id(db, product_id)

    @staticmethod
    def create(**kwargs) -> dict:
        """Create a new staging record."""
        with get_db() as db:
            return CoreSupplierService.create_staging(db, **kwargs)

    @staticmethod
    def update_status(product_id: int, status: str) -> Optional[dict]:
        """Update status of a new product."""
        with get_db() as db:
            return CoreSupplierService.update_staging_status(db, product_id, status)

    @staticmethod
    def update(product_id: int, **kwargs) -> Optional[dict]:
        """Update a new product fields."""
        with get_db() as db:
            return CoreSupplierService.update_staging(db, product_id, **kwargs)

    @staticmethod
    def duplicate(product_id: int) -> Optional[dict]:
        """Duplicate a new product record."""
        with get_db() as db:
            return CoreSupplierService.duplicate_staging(db, product_id)

    @staticmethod
    def bulk_update_status(product_ids: list[int], status: str) -> int:
        """Bulk update status for multiple products."""
        with get_db() as db:
            return CoreSupplierService.bulk_update_staging_status(db, product_ids, status)

    @staticmethod
    def get_status_counts() -> dict:
        """Get count of products by status."""
        with get_db() as db:
            return CoreSupplierService.get_staging_status_counts(db)

    @staticmethod
    def get_pending_count() -> int:
        """Get count of pending items (not CLOSED or OBSOLETE)."""
        with get_db() as db:
            return CoreSupplierService.get_staging_pending_count(db)

    @staticmethod
    def get_facture_ids() -> list[str]:
        """Get distinct facture IDs from staging table (excluding CLOSED/OBSOLETE)."""
        with get_db() as db:
            return CoreSupplierService.get_staging_facture_ids(db)

    @staticmethod
    def get_supplier_ids() -> list[str]:
        """Get all unique supplier IDs."""
        with get_db() as db:
            return CoreSupplierService.get_staging_supplier_ids(db)

    @staticmethod
    def resolve_anomalies(facture_id: Optional[str] = None) -> dict:
        """Resolve new products anomalies - creates products and facture items based on status."""
        with get_db() as db:
            result = CoreSupplierService.resolve_staging_anomalies(db, facture_id)
            logger.info(f"Resolved staging anomalies: {result}")
            return result

    @staticmethod
    def check_product_consistency(facture_id: Optional[str] = None,
                                   supplier_id: Optional[str] = None,
                                   exclude_closed: bool = True) -> list[dict]:
        """Check for product consistency issues."""
        with get_db() as db:
            return CoreSupplierService.check_staging_consistency(db, facture_id, supplier_id)

    @staticmethod
    def purge_closed() -> int:
        """Delete all records with STATUS = 'CLOSED'."""
        with get_db() as db:
            count = CoreSupplierService.purge_closed_staging(db)
            logger.info(f"Purged {count} CLOSED records from staging table")
            return count

    @staticmethod
    def undo_facture(facture_id: str) -> bool:
        """Undo a staged facture - mark staging as OBSOLETE and delete facture items."""
        with get_db() as db:
            return CoreSupplierService.undo_facture(db, facture_id)
