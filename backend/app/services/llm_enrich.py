from __future__ import annotations

from typing import Optional


def try_generate_example(term: str, definition: Optional[str] = None) -> Optional[str]:
    """Try to generate an example sentence using llm_api_loader if configured.

    If the LLM isn't configured or import fails, return None.
    """
    try:
        # Import lazily to avoid mandatory dependency
        from llm_api_loader.llm_loader import load_llm_client  # type: ignore
    except Exception:
        return None

    try:
        client = load_llm_client()
        prompt = (
            f"Give one short natural English example sentence using the word '{term}'. "
            f"Keep it simple. Only output the sentence."
        )
        if definition:
            prompt = (
                f"Word: {term}\nMeaning: {definition}\n"
                "Give one short natural English example sentence using this word in its meaning."
            )
        res = client.generate(prompt)
        # DashScope returns object with output_text sometimes; we try generic access
        text = None
        try:
            text = getattr(res, "output_text", None)
        except Exception:
            text = None
        if not text:
            text = str(res)
        # Post-process
        text = text.strip().strip('"')
        # Ensure it includes the term (best-effort)
        if term.lower() not in text.lower():
            text = f"{text} ({term})"
        return text
    except Exception:
        return None

