from groq import Groq

from config import settings

SYSTEM_PROMPT ="You are a helpful, friendly assistant. Answer clearly and concisely."


client = Groq(api_key=settings.groq_api_key)


def get_reply(messages: list[dict]) -> tuple[str, int]:
    """Send the conversation to Groq and return (reply text, tokens used)."""
    response = client.chat.completions.create(
        model=settings.model_name,
        # the system prompt always goes first, and only the server sets it
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
        max_completion_tokens=settings.max_tokens,
    )

    reply = response.choices[0].message.content or ""

    if not reply:
        # gpt-oss thinks before answering; a low MAX_TOKENS can use it all up
        raise RuntimeError(f"empty reply (finish_reason={response.choices[0].finish_reason})")
    tokens_used = response.usage.total_tokens if response.usage else 0

    return reply,tokens_used


def stream_reply(messages: list[dict]):
    """Yield the reply piece by piece: {"type": "delta", "text"} events, then one {"type": "done", "tokens_used"}."""

    stream = client.chat.completions.create(
        model=settings.model_name,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
        max_completion_tokens=settings.max_tokens,
        stream=True,
    )
    tokens_used = 0
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield {"type": "delta", "text": chunk.choices[0].delta.content}
        # Groq sends token usage on the last chunk, inside x_groq
        if chunk.x_groq and chunk.x_groq.usage:
            tokens_used = chunk.x_groq.usage.total_tokens
    yield {"type": "done", "tokens_used": tokens_used}

