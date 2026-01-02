from sqlalchemy import Column, BigInteger, String, Text
from app.database import Base


# Valid status values for supplier new products
NEWPRODUCT_STATUS_CHOICES = [
    'CLOSED',
    'CREATE PRODUCT',
    'IGNORE PRODUCT',
    'FULL IGNORE',
    'OBSOLETE'
]


class SupplierNewProducts(Base):
    """SupplierNewProducts model - staging table for new/modified products."""

    __tablename__ = 'suppliernewproducts'

    idsuppliernewproducts = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(500), nullable=True)
    designation = Column(String(500), nullable=True)
    unitprice = Column(String(45), nullable=True)
    tva = Column(String(45), nullable=True)
    category = Column(String(45), nullable=True)
    misc = Column(Text, nullable=True)
    quantity = Column(String(45), nullable=True)
    ItemPrice = Column(String(45), nullable=True)
    Status = Column(String(45), nullable=True)
    idFacture = Column(String(45), nullable=True)
    idsupplier = Column(String(45), nullable=True)

    def __repr__(self):
        return f"<SupplierNewProducts(id={self.idsuppliernewproducts}, code='{self.code}', status='{self.Status}')>"

    def to_dict(self):
        return {
            'idsuppliernewproducts': self.idsuppliernewproducts,
            'code': self.code,
            'designation': self.designation,
            'unitprice': self.unitprice,
            'tva': self.tva,
            'category': self.category,
            'misc': self.misc,
            'quantity': self.quantity,
            'ItemPrice': self.ItemPrice,
            'Status': self.Status,
            'idFacture': self.idFacture,
            'idsupplier': self.idsupplier
        }

    def clone(self):
        """Create a copy of this record for duplication."""
        return {
            'code': self.code,
            'designation': self.designation,
            'unitprice': self.unitprice,
            'tva': self.tva,
            'category': self.category,
            'misc': self.misc,
            'quantity': self.quantity,
            'ItemPrice': self.ItemPrice,
            'Status': 'CREATE PRODUCT',  # Default status for duplicated rows
            'idFacture': self.idFacture,
            'idsupplier': self.idsupplier
        }
