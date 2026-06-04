import logging

import anthropic

logger = logging.getLogger(__name__)


def test_api_key(provider: str, plaintext_key: str, model: str) -> bool:
    """
    Make one minimal live call to validate an API key.
    Returns True on success, False on any failure.
    The key is NEVER logged — only pass/fail is recorded.
    """
    if provider == "anthropic":
        return _test_anthropic(plaintext_key, model)
    logger.warning("test_api_key: unsupported provider %r — cannot validate", provider)
    return False


def _test_anthropic(plaintext_key: str, model: str) -> bool:
    try:
        client = anthropic.Anthropic(api_key=plaintext_key)
        # count_tokens is free and validates auth + model without running inference
        client.messages.count_tokens(
            model=model,
            messages=[{"role": "user", "content": "hi"}],
        )
        logger.info("anthropic key test passed")
        return True
    except Exception:
        logger.info("anthropic key test failed")
        return False
