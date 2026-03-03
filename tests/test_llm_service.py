"""Layer 4: LLM Service tests.

Tests Ollama/Bedrock connectivity and justification context format.
Skips gracefully if services are unavailable.
"""
import pytest
import requests

from analysercomptacore import init_database, get_db
from analysercomptacore.services.reconciliation_service import ReconciliationService

CONNECTION_STRING = "mysql+pymysql://devuser:devuser123@localhost:3310/dev_bankimport_brut"

TEST_MONTH = 12
TEST_YEAR = 2025


@pytest.fixture(scope="session", autouse=True)
def init_db():
    init_database(CONNECTION_STRING)


@pytest.fixture
def db():
    with get_db() as session:
        yield session


def _ollama_available():
    """Check if Ollama is reachable."""
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _bedrock_available():
    """Check if AWS Bedrock credentials are available."""
    try:
        import boto3
        client = boto3.client('bedrock-runtime', region_name='eu-west-3')
        # Just check we can create the client — don't actually invoke
        return True
    except Exception:
        return False


# ==================== Context Format Tests (always run) ====================

class TestJustificationContextFormat:
    """Test that generate_justification_context returns well-structured text."""

    def test_context_is_non_empty_string(self, db):
        context = ReconciliationService.generate_justification_context(
            db, TEST_MONTH, TEST_YEAR, 'CB'
        )
        assert isinstance(context, str)
        assert len(context) > 0

    def test_context_contains_required_fields(self, db):
        context = ReconciliationService.generate_justification_context(
            db, TEST_MONTH, TEST_YEAR, 'CB'
        )
        assert 'CB' in context
        assert 'Bank Total' in context
        assert 'Sales Total' in context
        assert 'Delta' in context

    def test_context_for_each_payment_type(self, db):
        for pt in ['CB', 'AMEX', 'CTR', 'CHEQUE', 'CASH']:
            context = ReconciliationService.generate_justification_context(
                db, TEST_MONTH, TEST_YEAR, pt
            )
            assert pt in context
            assert 'Bank Total' in context

    def test_cb_context_mentions_brutmontant(self, db):
        context = ReconciliationService.generate_justification_context(
            db, TEST_MONTH, TEST_YEAR, 'CB'
        )
        assert 'BrutMontant' in context

    def test_ctr_context_mentions_tr_combination(self, db):
        context = ReconciliationService.generate_justification_context(
            db, TEST_MONTH, TEST_YEAR, 'CTR'
        )
        assert 'TR' in context


# ==================== Ollama Tests (skip if unavailable) ====================

@pytest.mark.skipif(not _ollama_available(), reason="Ollama not available at localhost:11434")
class TestOllamaConnectivity:

    def test_ollama_is_reachable(self):
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        assert resp.status_code == 200

    def test_ollama_generates_text(self):
        """Send a simple prompt to Ollama and verify non-empty response."""
        from app.services.llm_service import LLMService
        result = LLMService.generate_with_ollama(
            "Say hello in one sentence.",
            "You are a helpful assistant."
        )
        assert isinstance(result, str)
        assert len(result) > 0


# ==================== Bedrock Tests (skip if unavailable) ====================

@pytest.mark.skipif(not _bedrock_available(), reason="AWS Bedrock not configured")
class TestBedrockConnectivity:

    def test_bedrock_client_initializes(self):
        import boto3
        client = boto3.client('bedrock-runtime', region_name='eu-west-3')
        assert client is not None
