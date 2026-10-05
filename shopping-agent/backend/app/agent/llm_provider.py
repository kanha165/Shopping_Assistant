"""
LLM Provider - returns the correct LangChain LLM based on config.
Supports OpenAI GPT-4o, Google Gemini (new AQ. key format), and Ollama (local).
"""
from langchain_core.language_models import BaseChatModel
from app.core.config import settings
from app.core.logger import app_logger


def get_llm() -> BaseChatModel:
    """Return configured LLM instance based on LLM_PROVIDER in .env"""
    provider = settings.LLM_PROVIDER.lower()

    # ── OpenAI ────────────────────────────────────────────────────────────────
    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is not set in .env")
        from langchain_openai import ChatOpenAI
        app_logger.info(f"Using OpenAI model: {settings.OPENAI_MODEL}")
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.2,
            max_tokens=4096,
        )

    # ── Google Gemini (supports new AQ. key format) ───────────────────────────
    elif provider == "google":
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set in .env")
        from langchain_google_genai import ChatGoogleGenerativeAI
        import os
        # Set env var so google SDK picks up the key
        os.environ["GOOGLE_API_KEY"] = settings.GOOGLE_API_KEY
        app_logger.info(f"Using Google Gemini model: {settings.GOOGLE_MODEL}")
        return ChatGoogleGenerativeAI(
            model=settings.GOOGLE_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.2,
            max_output_tokens=4096,
            convert_system_message_to_human=True,  # Gemini compatibility
        )

    # ── Ollama (Local - Free, No API Key) ─────────────────────────────────────
    elif provider == "ollama":
        from langchain_community.chat_models import ChatOllama
        app_logger.info(f"Using Ollama local model: {settings.OLLAMA_MODEL}")
        return ChatOllama(
            model=settings.OLLAMA_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.2,
        )

    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER: '{provider}'. "
            "Valid options: 'openai', 'google', 'ollama'"
        )
