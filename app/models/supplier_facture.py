from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, ForeignKey, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class SupplierFacture(Base):
    """SupplierFacture model - represents a supplier invoice."""

    __tablename__ = 'supplierfacture'

    idFacture = Column(BigInteger, primary_key=True, autoincrement=True)
    idsupplier = Column(BigInteger, ForeignKey('supplier.idsupplier'), nullable=True)
    factNum = Column(String(120), nullable=False)
    factDate = Column(DateTime, nullable=True)
    factmontantttc = Column(Numeric(15, 2), nullable=True)
    factmontantHT = Column(Numeric(15, 2), nullable=True)
    factmontantTVA = Column(Numeric(15, 2), nullable=True)
    createdon = Column(TIMESTAMP, server_default=func.current_timestamp(), nullable=True)
    filename = Column(String(100), nullable=True)

    # Relationships
    supplier = relationship("Supplier", back_populates="factures")
    items = relationship("SupplierFactItem", back_populates="facture")

    def __repr__(self):
        return f"<SupplierFacture(id={self.idFacture}, num='{self.factNum}')>"

    def to_dict(self):
        return {
            'idFacture': self.idFacture,
            'idsupplier': self.idsupplier,
            'supplier_name': self.supplier.name if self.supplier else None,
            'factNum': self.factNum,
            'factDate': self.factDate.strftime('%Y-%m-%d') if self.factDate else None,
            'factmontantttc': float(self.factmontantttc) if self.factmontantttc else 0.0,
            'factmontantHT': float(self.factmontantHT) if self.factmontantHT else 0.0,
            'factmontantTVA': float(self.factmontantTVA) if self.factmontantTVA else 0.0,
            'createdon': self.createdon.strftime('%Y-%m-%d %H:%M:%S') if self.createdon else None,
            'filename': self.filename
        }
