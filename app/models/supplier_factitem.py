from sqlalchemy import Column, BigInteger, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class SupplierFactItem(Base):
    """SupplierFactItem model - represents a line item in a supplier invoice."""

    __tablename__ = 'supplierfactitem'

    idsupplierfactitem = Column(BigInteger, primary_key=True, autoincrement=True)
    idsupplier = Column(BigInteger, nullable=False)
    idsupplierfacture = Column(BigInteger, ForeignKey('supplierfacture.idFacture'), nullable=False)
    idsupplierproduct = Column(BigInteger, ForeignKey('supplierproduct.idsupplierproduct'), nullable=False)
    quantity = Column(Numeric(15, 2), nullable=False)
    itemPrice = Column(Numeric(15, 2), nullable=True)
    unitPriceSnap = Column(Numeric(15, 2), nullable=False)

    # Relationships
    facture = relationship("SupplierFacture", back_populates="items")
    product = relationship("SupplierProduct", back_populates="factitems")

    def __repr__(self):
        return f"<SupplierFactItem(id={self.idsupplierfactitem}, facture={self.idsupplierfacture})>"

    def to_dict(self):
        return {
            'idsupplierfactitem': self.idsupplierfactitem,
            'idsupplier': self.idsupplier,
            'idsupplierfacture': self.idsupplierfacture,
            'idsupplierproduct': self.idsupplierproduct,
            'product_code': self.product.code if self.product else None,
            'product_designation': self.product.designation if self.product else None,
            'quantity': float(self.quantity) if self.quantity else 0.0,
            'itemPrice': float(self.itemPrice) if self.itemPrice else 0.0,
            'unitPriceSnap': float(self.unitPriceSnap) if self.unitPriceSnap else 0.0
        }
