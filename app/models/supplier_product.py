from sqlalchemy import Column, BigInteger, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class SupplierProduct(Base):
    """SupplierProduct model - represents a product from a supplier."""

    __tablename__ = 'supplierproduct'

    idsupplierproduct = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(45), nullable=False, unique=True)
    designation = Column(String(500), nullable=False)
    unitprice = Column(Numeric(15, 2), nullable=False)
    tva = Column(String(45), nullable=True)
    category = Column(String(45), nullable=True)
    idsupplier = Column(BigInteger, ForeignKey('supplier.idsupplier'), nullable=True)

    # Relationships
    supplier = relationship("Supplier", back_populates="products")
    factitems = relationship("SupplierFactItem", back_populates="product", lazy="dynamic")

    def __repr__(self):
        return f"<SupplierProduct(id={self.idsupplierproduct}, code='{self.code}')>"

    def to_dict(self):
        return {
            'idsupplierproduct': self.idsupplierproduct,
            'code': self.code,
            'designation': self.designation,
            'unitprice': float(self.unitprice) if self.unitprice else 0.0,
            'tva': self.tva,
            'category': self.category,
            'idsupplier': self.idsupplier,
            'supplier_name': self.supplier.name if self.supplier else None
        }
