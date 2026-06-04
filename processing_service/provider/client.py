import anthropic


def get_anthropic_client(api_key: str) -> anthropic.AsyncAnthropic:
    """
    Single entry point for all Anthropic model calls.
    Swap this function body to change providers without touching any caller.
    """
    return anthropic.AsyncAnthropic(api_key=api_key)
