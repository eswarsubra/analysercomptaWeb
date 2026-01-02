from sqlalchemy import Column, BigInteger, String
from sqlalchemy.orm import relationship
from app.database import Base


class Supplier(Base):
    """Supplier model - represents a supplier entity."""

    __tablename__ = 'supplier'

    idsupplier = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=False)

    # Relationships
    products = relationship("SupplierProduct", back_populates="supplier", lazy="dynamic")
    factures = relationship("SupplierFacture", back_populates="supplier", lazy="dynamic")

    def __repr__(self):
        return f"<Supplier(id={self.idsupplier}, name='{self.name}')>"

    def to_dict(self):
        return {
            'idsupplier': self.idsupplier,
            'name': self.name
        }
