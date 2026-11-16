"""LLM Service - abstraction over LLM providers for text generation."""
import json
import logging
import ollama
from app.config import config

logger = logging.getLogger(__name__)


class LLMService:
    """Abstraction over LLM providers for text generation."""

    @staticmethod
    def generate_with_ollama(prompt: str, system: str) -> str:
        """Generate text using local Ollama (Qwen model).

        Args:
            prompt: User prompt with data context
            system: System prompt describing the task

        Returns:
            Generated text response
        """
        llm_config = LLMService._get_llm_config()
        ollama_config = llm_config.get('ollama', {})
        host = ollama_config.get('base_url', 'http://localhost:11434')
        model = ollama_config.get('model', 'qwen2.5')

        try:
            client = ollama.Client(host=host)
            response = client.chat(
                model=model,
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': prompt},
                ],
            )
            return response['message']['content']
        except ollama.ResponseError as e:
            logger.error(f"Ollama response error: {e}")
            raise RuntimeError(f"Ollama error: {e}")
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise RuntimeError(f"Ollama error: {e}. Is the server running?")

    @staticmethod
    def generate_with_bedrock(prompt: str, system: str) -> str:
        """Generate text using AWS Bedrock (Claude Sonnet).

        Args:
            prompt: User prompt with data context
            system: System prompt describing the task

        Returns:
            Generated text response
        """
        try:
            import boto3
        except ImportError:
            raise RuntimeError("boto3 is not installed. Install it with: pip install boto3")

        llm_config = LLMService._get_llm_config()
        bedrock_config = llm_config.get('bedrock', {})
        region = bedrock_config['region']
        model_id = bedrock_config['model_id']

        try:
            client = boto3.client('bedrock-runtime', region_name=region)

            body = json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 1024,
                'system': system,
                'messages': [
                    {'role': 'user', 'content': prompt},
                ],
            })

            response = client.invoke_model(
                modelId=model_id,
                body=body,
                contentType='application/json',
                accept='application/json',
            )

            response_body = json.loads(response['body'].read())
            return response_body.get('content', [{}])[0].get('text', '')

        except Exception as e:
            logger.error(f"Bedrock error: {e}")
            raise RuntimeError(f"AWS Bedrock error: {e}")

    @staticmethod
    def _get_llm_config() -> dict:
        """Get LLM configuration from app config."""
        env = config.get_env()
        full_config = config._config.get(env, {})
        return full_config.get('llm', {})
