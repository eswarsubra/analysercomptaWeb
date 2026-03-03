"""Reconciliation Service - wraps Core's ReconciliationService for web operations."""
import logging
from datetime import date
from typing import Optional

from analysercomptacore.services import ReconciliationService as CoreReconciliationService
from app.database import get_db
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

MONTH_SUMMARY_SYSTEM_PROMPT = (
    "You are a financial analyst. Based on the individual payment type justifications "
    "and reconciliation data for the month, draft a consolidated monthly reconciliation "
    "summary in French. Synthesize the key points from each payment type, highlight any "
    "significant deltas, and provide an overall assessment. Keep it to 4-6 sentences."
)

JUSTIFICATION_SYSTEM_PROMPT = (
    "You are a financial analyst helping with monthly bank vs sales reconciliation. "
    "Based on the provided reconciliation data, draft a concise justification in French "
    "explaining the delta between bank transactions and sales records. "
    "Be factual and specific about the amounts. Reference any manual adjustments. "
    "If the delta is zero or negligible, state that bank and sales are reconciled. "
    "Keep the justification to 2-4 sentences maximum."
)


class ReconciliationService:
    """Service for Reconciliation operations - wraps Core's ReconciliationService."""

    @staticmethod
    def get_summary(month: int, year: int) -> list[dict]:
        """Get reconciliation summary for all payment types."""
        with get_db() as db:
            return CoreReconciliationService.build_reconciliation_summary(db, month, year)

    @staticmethod
    def get_daily_breakdown(month: int, year: int, payment_type: str) -> dict:
        """Get daily breakdown for a payment type."""
        with get_db() as db:
            return CoreReconciliationService.build_daily_breakdown(db, month, year, payment_type)

    @staticmethod
    def get_month_status(month: int, year: int) -> dict:
        """Get reconciliation status for a month."""
        with get_db() as db:
            return CoreReconciliationService.get_month_status(db, month, year)

    @staticmethod
    def close_month(month: int, year: int) -> dict:
        """Close a reconciliation month."""
        with get_db() as db:
            recon = CoreReconciliationService.get_or_create_month(db, month, year)
            return CoreReconciliationService.close_month(db, recon.id)

    @staticmethod
    def reopen_month(month: int, year: int) -> dict:
        """Reopen a reconciliation month."""
        with get_db() as db:
            recon = CoreReconciliationService.get_or_create_month(db, month, year)
            return CoreReconciliationService.reopen_month(db, recon.id)

    @staticmethod
    def save_justification(
        month: int, year: int, payment_type: str,
        justification: str, bank_total: float, sales_total: float, delta: float
    ) -> dict:
        """Save justification for a payment type."""
        with get_db() as db:
            recon = CoreReconciliationService.get_or_create_month(db, month, year)
            return CoreReconciliationService.save_justification(
                db, recon.id, payment_type, justification, bank_total, sales_total, delta
            )

    @staticmethod
    def get_justification(month: int, year: int, payment_type: str) -> Optional[dict]:
        """Get persisted justification for a payment type."""
        with get_db() as db:
            recon = CoreReconciliationService.get_or_create_month(db, month, year)
            return CoreReconciliationService.get_justification(db, recon.id, payment_type)

    @staticmethod
    def get_adjustments(month: int, year: int, payment_type: str) -> list[dict]:
        """Get manual adjustments for a payment type."""
        with get_db() as db:
            recon = CoreReconciliationService.get_or_create_month(db, month, year)
            return CoreReconciliationService.get_adjustments(db, recon.id, payment_type)

    @staticmethod
    def add_adjustment(
        month: int, year: int, payment_type: str,
        label: str, amount: float, entry_date: Optional[date] = None
    ) -> dict:
        """Add a manual adjustment entry."""
        with get_db() as db:
            recon = CoreReconciliationService.get_or_create_month(db, month, year)
            return CoreReconciliationService.add_adjustment(
                db, recon.id, payment_type, label, amount, entry_date
            )

    @staticmethod
    def delete_adjustment(adjustment_id: int) -> dict:
        """Delete a manual adjustment entry."""
        with get_db() as db:
            return CoreReconciliationService.delete_adjustment(db, adjustment_id)

    @staticmethod
    def generate_ai_justification(
        month: int, year: int, payment_type: str, provider: str = 'ollama'
    ) -> str:
        """Generate AI-drafted justification text.

        Args:
            month: Month number
            year: Year
            payment_type: Payment type (CB, AMEX, CTR, CHEQUE, CASH)
            provider: 'ollama' or 'bedrock'

        Returns:
            Generated justification text
        """
        # Build context from Core
        with get_db() as db:
            context = CoreReconciliationService.generate_justification_context(
                db, month, year, payment_type
            )

        prompt = (
            f"Draft a reconciliation justification for the following data:\n\n{context}"
        )

        if provider == 'bedrock':
            return LLMService.generate_with_bedrock(prompt, JUSTIFICATION_SYSTEM_PROMPT)
        else:
            return LLMService.generate_with_ollama(prompt, JUSTIFICATION_SYSTEM_PROMPT)

    @staticmethod
    def get_all_justifications(month: int, year: int) -> list[dict]:
        """Get justification data for all payment types in a month."""
        with get_db() as db:
            recon = CoreReconciliationService.get_or_create_month(db, month, year)
            return CoreReconciliationService.get_all_justifications(db, recon.id)

    @staticmethod
    def save_month_summary(month: int, year: int, summary_text: str) -> dict:
        """Save consolidated monthly summary text."""
        with get_db() as db:
            recon = CoreReconciliationService.get_or_create_month(db, month, year)
            return CoreReconciliationService.save_month_summary(db, recon.id, summary_text)

    @staticmethod
    def get_month_summary(month: int, year: int) -> Optional[str]:
        """Get the consolidated monthly summary text."""
        with get_db() as db:
            recon = CoreReconciliationService.get_or_create_month(db, month, year)
            return recon.summary

    @staticmethod
    def generate_ai_month_summary(
        month: int, year: int, provider: str = 'ollama'
    ) -> str:
        """Generate AI-drafted consolidated monthly summary."""
        with get_db() as db:
            context = CoreReconciliationService.generate_month_summary_context(
                db, month, year
            )

        prompt = (
            f"Draft a consolidated monthly reconciliation summary for the following data:\n\n{context}"
        )

        if provider == 'bedrock':
            return LLMService.generate_with_bedrock(prompt, MONTH_SUMMARY_SYSTEM_PROMPT)
        else:
            return LLMService.generate_with_ollama(prompt, MONTH_SUMMARY_SYSTEM_PROMPT)
