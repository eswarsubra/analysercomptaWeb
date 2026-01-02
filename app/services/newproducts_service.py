from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import Optional
from app.database import get_db, get_session
from app.models.supplier_newproducts import SupplierNewProducts, NEWPRODUCT_STATUS_CHOICES
from app.models.supplier_product import SupplierProduct
from app.models.supplier_factitem import SupplierFactItem
from app.models.supplier_facture import SupplierFacture
from app.models.supplier import Supplier
from app.logging_config import get_logger

logger = get_logger(__name__)


class NewProductsService:
    """Service for SupplierNewProducts operations - staging table management."""

    @staticmethod
    def get_all(status: Optional[str] = None,
                supplier_id: Optional[str] = None,
                facture_id: Optional[str] = None,
                exclude_closed: bool = False) -> list[dict]:
        """Get all new products, optionally filtered, with supplier name."""
        with get_db() as db:
            query = db.query(SupplierNewProducts)

            if status:
                query = query.filter(SupplierNewProducts.Status == status)
            if supplier_id:
                query = query.filter(SupplierNewProducts.idsupplier == supplier_id)
            if facture_id:
                query = query.filter(SupplierNewProducts.idFacture == facture_id)
            if exclude_closed:
                query = query.filter(SupplierNewProducts.Status.notin_(['CLOSED', 'OBSOLETE']))

            results = query.order_by(SupplierNewProducts.idsuppliernewproducts.desc()).all()

            # Build supplier lookup dict
            supplier_ids = set(r.idsupplier for r in results if r.idsupplier)
            suppliers = {}
            if supplier_ids:
                supplier_records = db.query(Supplier).filter(
                    Supplier.idsupplier.in_([int(s) for s in supplier_ids if s.isdigit()])
                ).all()
                suppliers = {str(s.idsupplier): s.name for s in supplier_records}

            # Build result with supplier_name included
            products = []
            for row in results:
                product_dict = row.to_dict()
                product_dict['supplier_name'] = suppliers.get(row.idsupplier, 'Unknown')
                products.append(product_dict)
            return products

    @staticmethod
    def get_by_id(product_id: int) -> Optional[dict]:
        """Get a new product by ID."""
        with get_db() as db:
            product = db.query(SupplierNewProducts).filter(
                SupplierNewProducts.idsuppliernewproducts == product_id
            ).first()
            return product.to_dict() if product else None

    @staticmethod
    def create(**kwargs) -> dict:
        """Create a new staging record."""
        # Validate status if provided
        if 'Status' in kwargs and kwargs['Status'] not in NEWPRODUCT_STATUS_CHOICES:
            raise ValueError(f"Invalid status: {kwargs['Status']}")

        with get_db() as db:
            product = SupplierNewProducts(
                code=kwargs.get('code'),
                designation=kwargs.get('designation'),
                unitprice=kwargs.get('unitprice'),
                tva=kwargs.get('tva'),
                category=kwargs.get('category'),
                misc=kwargs.get('misc'),
                quantity=kwargs.get('quantity'),
                ItemPrice=kwargs.get('ItemPrice'),
                Status=kwargs.get('Status', 'CREATE PRODUCT'),
                idFacture=kwargs.get('idFacture'),
                idsupplier=kwargs.get('idsupplier')
            )
            db.add(product)
            db.flush()
            return product.to_dict()

    @staticmethod
    def update_status(product_id: int, status: str) -> Optional[dict]:
        """Update status of a new product."""
        if status not in NEWPRODUCT_STATUS_CHOICES:
            raise ValueError(f"Invalid status: {status}. Must be one of {NEWPRODUCT_STATUS_CHOICES}")

        with get_db() as db:
            product = db.query(SupplierNewProducts).filter(
                SupplierNewProducts.idsuppliernewproducts == product_id
            ).first()
            if product:
                product.Status = status
                db.flush()
                return product.to_dict()
            return None

    @staticmethod
    def update(product_id: int, **kwargs) -> Optional[dict]:
        """Update a new product fields."""
        with get_db() as db:
            product = db.query(SupplierNewProducts).filter(
                SupplierNewProducts.idsuppliernewproducts == product_id
            ).first()
            if product:
                # Validate status if provided
                if 'Status' in kwargs and kwargs['Status'] not in NEWPRODUCT_STATUS_CHOICES:
                    raise ValueError(f"Invalid status: {kwargs['Status']}")

                for key, value in kwargs.items():
                    if hasattr(product, key):
                        setattr(product, key, value)
                db.flush()
                return product.to_dict()
            return None

    @staticmethod
    def duplicate(product_id: int) -> Optional[dict]:
        """Duplicate a new product record."""
        with get_db() as db:
            original = db.query(SupplierNewProducts).filter(
                SupplierNewProducts.idsuppliernewproducts == product_id
            ).first()

            if original:
                new_product = SupplierNewProducts(
                    code=original.code,
                    designation=original.designation,
                    unitprice=original.unitprice,
                    tva=original.tva,
                    category=original.category,
                    misc=original.misc,
                    quantity=original.quantity,
                    ItemPrice=original.ItemPrice,
                    Status='CREATE PRODUCT',
                    idFacture=original.idFacture,
                    idsupplier=original.idsupplier
                )
                db.add(new_product)
                db.flush()
                return new_product.to_dict()
            return None

    @staticmethod
    def bulk_update_status(product_ids: list[int], status: str) -> int:
        """Bulk update status for multiple products."""
        if status not in NEWPRODUCT_STATUS_CHOICES:
            raise ValueError(f"Invalid status: {status}")

        with get_db() as db:
            count = db.query(SupplierNewProducts).filter(
                SupplierNewProducts.idsuppliernewproducts.in_(product_ids)
            ).update({SupplierNewProducts.Status: status}, synchronize_session=False)
            return count

    @staticmethod
    def get_status_counts() -> dict:
        """Get count of products by status."""
        with get_db() as db:
            counts = db.query(
                SupplierNewProducts.Status,
                func.count(SupplierNewProducts.idsuppliernewproducts)
            ).group_by(SupplierNewProducts.Status).all()

            return {status: count for status, count in counts}

    @staticmethod
    def get_pending_count() -> int:
        """Get count of pending items (not CLOSED or OBSOLETE)."""
        with get_db() as db:
            return db.query(func.count(SupplierNewProducts.idsuppliernewproducts)).filter(
                SupplierNewProducts.Status.notin_(['CLOSED', 'OBSOLETE'])
            ).scalar()

    @staticmethod
    def get_facture_ids() -> list[str]:
        """Get all unique facture IDs."""
        with get_db() as db:
            factures = db.query(SupplierNewProducts.idFacture).distinct().filter(
                SupplierNewProducts.idFacture.isnot(None)
            ).all()
            return [f[0] for f in factures if f[0]]

    @staticmethod
    def get_supplier_ids() -> list[str]:
        """Get all unique supplier IDs."""
        with get_db() as db:
            suppliers = db.query(SupplierNewProducts.idsupplier).distinct().filter(
                SupplierNewProducts.idsupplier.isnot(None)
            ).all()
            return [s[0] for s in suppliers if s[0]]

    @staticmethod
    def _extract_product_ref_id(misc: str) -> Optional[int]:
        """Extract product reference ID from misc field.
        Format: 'Product Reference ID:{id}-'
        """
        if not misc:
            return None
        if 'Product Reference ID:' in misc:
            try:
                extracted = misc.split('Product Reference ID:')[1].split('-')[0].strip()
                return int(extracted)
            except (IndexError, ValueError):
                pass
        return None

    @staticmethod
    def resolve_anomalies(facture_id: Optional[str] = None) -> dict:
        """
        Resolve new products anomalies - adapted from AnalyzerCompta SupplierUploader.
        Creates products and facture items based on status.

        Handles duplicate products across invoices:
        - Groups CREATE PRODUCT items by (code, supplier)
        - Creates product once for first occurrence
        - Updates all other duplicates to IGNORE PRODUCT with Product Reference ID
        """
        db = get_session()
        try:
            # Build query for pending items (include FULL IGNORE to mark as CLOSED)
            query = db.query(SupplierNewProducts).filter(
                SupplierNewProducts.Status.notin_(['CLOSED', 'OBSOLETE', 'INCOMPLETE'])
            )
            if facture_id:
                query = query.filter(SupplierNewProducts.idFacture == facture_id)

            records = query.all()

            stats = {'created': 0, 'ignored': 0, 'full_ignored': 0, 'errors': 0, 'duplicates_converted': 0}

            # Cache for product creation: key = (code, supplier_id), value = product_id
            cache_product_creation = {}

            # Pre-process: Group CREATE PRODUCT records by (code, supplier) to identify duplicates
            create_product_groups = {}
            for record in records:
                if record.Status == 'CREATE PRODUCT':
                    key = (record.code, record.idsupplier)
                    if key not in create_product_groups:
                        create_product_groups[key] = []
                    create_product_groups[key].append(record)

            # Process duplicates: for each group, keep first as CREATE PRODUCT, convert rest to IGNORE PRODUCT
            for key, group_records in create_product_groups.items():
                if len(group_records) > 1:
                    # First record creates the product
                    first_record = group_records[0]
                    code, idsupplier = key

                    # Create the product
                    new_product = SupplierProduct(
                        code=first_record.code,
                        designation=first_record.designation,
                        unitprice=float(first_record.unitprice) if first_record.unitprice else 0,
                        tva=first_record.tva,
                        category=first_record.category,
                        idsupplier=int(idsupplier) if idsupplier else None
                    )
                    db.add(new_product)
                    db.flush()
                    new_product_id = new_product.idsupplierproduct
                    cache_product_creation[key] = new_product_id

                    # Update all OTHER records in this group to IGNORE PRODUCT
                    for dup_record in group_records[1:]:
                        dup_record.Status = 'IGNORE PRODUCT'
                        dup_record.misc = f"Product Reference ID:{new_product_id}-"
                        stats['duplicates_converted'] += 1

            for record in records:
                try:
                    id_facture = record.idFacture
                    idsupplier = record.idsupplier
                    key = (record.code, idsupplier)

                    if record.Status == 'CREATE PRODUCT':
                        # Check cache first (may have been created during duplicate processing)
                        if key in cache_product_creation:
                            new_product_id = cache_product_creation[key]
                        else:
                            # Create new product
                            new_product = SupplierProduct(
                                code=record.code,
                                designation=record.designation,
                                unitprice=float(record.unitprice) if record.unitprice else 0,
                                tva=record.tva,
                                category=record.category,
                                idsupplier=int(idsupplier) if idsupplier else None
                            )
                            db.add(new_product)
                            db.flush()
                            new_product_id = new_product.idsupplierproduct
                            cache_product_creation[key] = new_product_id

                        # Create facture item
                        fact_item = SupplierFactItem(
                            idsupplier=int(idsupplier) if idsupplier else 0,
                            idsupplierfacture=int(id_facture) if id_facture else 0,
                            idsupplierproduct=new_product_id,
                            quantity=float(record.quantity) if record.quantity else 0,
                            itemPrice=float(record.ItemPrice) if record.ItemPrice else 0,
                            unitPriceSnap=float(record.unitprice) if record.unitprice else 0
                        )
                        db.add(fact_item)
                        stats['created'] += 1

                    elif record.Status == 'IGNORE PRODUCT':
                        # Product exists, just create facture item
                        extracted_id = NewProductsService._extract_product_ref_id(record.misc)
                        if extracted_id:
                            fact_item = SupplierFactItem(
                                idsupplier=int(idsupplier) if idsupplier else 0,
                                idsupplierfacture=int(id_facture) if id_facture else 0,
                                idsupplierproduct=extracted_id,
                                quantity=float(record.quantity) if record.quantity else 0,
                                itemPrice=float(record.ItemPrice) if record.ItemPrice else 0,
                                unitPriceSnap=float(record.unitprice) if record.unitprice else 0
                            )
                            db.add(fact_item)
                            stats['ignored'] += 1
                        else:
                            record.Status = 'INCOMPLETE'
                            stats['errors'] += 1
                            continue

                    elif record.Status == 'FULL IGNORE':
                        # No product or facture item creation, just mark as closed
                        stats['full_ignored'] += 1

                    # Mark as closed
                    record.Status = 'CLOSED'

                except Exception as e:
                    record.Status = 'INCOMPLETE'
                    stats['errors'] += 1
                    logger.error(f"Error processing record {record.idsuppliernewproducts}: {e}")

            db.commit()
            return stats

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()

    @staticmethod
    def check_product_consistency(facture_id: Optional[str] = None,
                                   supplier_id: Optional[str] = None,
                                   exclude_closed: bool = True) -> list[dict]:
        """
        Check for product consistency issues - finds staging records with CREATE PRODUCT
        status where a product with the same code already exists for that supplier.

        Returns list of dicts with: staging record id, existing product id, code, supplier_id
        """
        with get_db() as db:
            # Build query for CREATE PRODUCT records
            query = db.query(SupplierNewProducts).filter(
                SupplierNewProducts.Status == 'CREATE PRODUCT'
            )

            if facture_id:
                query = query.filter(SupplierNewProducts.idFacture == facture_id)
            if supplier_id:
                query = query.filter(SupplierNewProducts.idsupplier == supplier_id)
            if exclude_closed:
                query = query.filter(SupplierNewProducts.Status.notin_(['CLOSED', 'OBSOLETE']))

            staging_records = query.all()

            if not staging_records:
                return []

            # Get all unique (code, supplier_id) pairs from staging
            code_supplier_pairs = set()
            for record in staging_records:
                if record.code and record.idsupplier:
                    code_supplier_pairs.add((record.code, record.idsupplier))

            if not code_supplier_pairs:
                return []

            # Find existing products matching these codes
            existing_products = {}
            for code, supplier_id_str in code_supplier_pairs:
                try:
                    supplier_id_int = int(supplier_id_str) if supplier_id_str else None
                    if supplier_id_int:
                        product = db.query(SupplierProduct).filter(
                            SupplierProduct.code == code,
                            SupplierProduct.idsupplier == supplier_id_int
                        ).first()
                        if product:
                            existing_products[(code, supplier_id_str)] = product.idsupplierproduct
                except (ValueError, TypeError):
                    continue

            # Build list of inconsistent records
            inconsistent = []
            for record in staging_records:
                key = (record.code, record.idsupplier)
                if key in existing_products:
                    inconsistent.append({
                        'idsuppliernewproducts': record.idsuppliernewproducts,
                        'existing_product_id': existing_products[key],
                        'code': record.code,
                        'idsupplier': record.idsupplier
                    })

            return inconsistent

    @staticmethod
    def purge_closed() -> int:
        """
        Delete all records with STATUS = 'CLOSED'.

        Returns:
            Number of records deleted
        """
        with get_db() as db:
            count = db.query(SupplierNewProducts).filter(
                SupplierNewProducts.Status == 'CLOSED'
            ).delete(synchronize_session=False)
            logger.info(f"Purged {count} CLOSED records from staging table")
            return count

    @staticmethod
    def undo_facture(facture_id: str) -> bool:
        """
        Undo a staged facture - mark staging as OBSOLETE and delete facture items.
        Adapted from AnalyzerCompta SupplierUploader.undoStagedInvoice.
        """
        db = get_session()
        try:
            # Mark staging records as OBSOLETE
            db.query(SupplierNewProducts).filter(
                SupplierNewProducts.idFacture == facture_id
            ).update({SupplierNewProducts.Status: 'OBSOLETE'}, synchronize_session=False)

            # Delete facture items
            db.query(SupplierFactItem).filter(
                SupplierFactItem.idsupplierfacture == int(facture_id)
            ).delete(synchronize_session=False)

            # Delete facture
            db.query(SupplierFacture).filter(
                SupplierFacture.idFacture == int(facture_id)
            ).delete(synchronize_session=False)

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
