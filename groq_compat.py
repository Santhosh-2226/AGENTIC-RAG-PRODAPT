"""
groq_compat.py

Drop-in compatibility shim that lets layer files written with Anthropic SDK
syntax (client.messages.create) work unchanged against the Groq SDK
(client.chat.completions.create).

Usage — replace get_client() calls in agent.py with get_compat_client():

    from groq_compat import get_compat_client
    client = get_compat_client()

Then pass this client into compose_answer(), reflect(), etc.
They can call client.messages.create(...) and it will work.
"""

import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_client = None


def get_compat_client() -> "GroqCompatClient":
    global _client
    if _client is None:
        raw = Groq(api_key=os.environ["GROQ_API_KEY"])
        _client = GroqCompatClient(raw)
    return _client


class _MessagesNamespace:
    """
    Mimics the Anthropic  client.messages  namespace.
    Translates  .create(**kwargs)  to  client.chat.completions.create(**kwargs).
    """

    def __init__(self, groq_client: Groq):
        self._groq = groq_client

    def create(
        self,
        model: str,
        messages: list,
        max_tokens: int = 1024,
        temperature: float = 0,
        system: str = None,
        **kwargs,
    ):
        """
        Translate Anthropic-style arguments to Groq/OpenAI style.

        Key differences handled:
        - Anthropic passes `system` as a top-level kwarg; Groq expects it
          as the first message with role="system".
        - Anthropic uses `max_tokens`; Groq uses `max_completion_tokens`.
        - Anthropic returns response.content[0].text; Groq returns
          response.choices[0].message.content.
          We wrap the response so callers get the same interface.
        """
        groq_messages = list(messages)

        # Prepend system message if provided as kwarg (Anthropic style)
        if system:
            groq_messages = [{"role": "system", "content": system}] + groq_messages

        # Strip any remaining Anthropic-only kwargs we don't want to forward
        kwargs.pop("stop_sequences", None)
        kwargs.pop("stream", None)

        response = self._groq.chat.completions.create(
            model=model,
            messages=groq_messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            **kwargs,
        )

        return _CompatResponse(response)


class _CompatResponse:
    """
    Wraps a Groq chat completion response to expose the Anthropic interface:
        response.content[0].text
    while also preserving the Groq interface:
        response.choices[0].message.content
    """

    def __init__(self, groq_response):
        self._groq_response = groq_response
        # Build an Anthropic-style .content list
        text = ""
        if groq_response.choices:
            text = groq_response.choices[0].message.content or ""
        self.content = [_TextBlock(text)]

        # Expose Groq-style attributes too so nothing else breaks
        self.choices = groq_response.choices
        self.model = groq_response.model
        self.usage = groq_response.usage
        self.id = groq_response.id

    def __repr__(self):
        return f"<CompatResponse content={self.content!r}>"


class _TextBlock:
    """Mimics Anthropic's ContentBlock with a .text attribute."""

    def __init__(self, text: str):
        self.text = text
        self.type = "text"

    def __repr__(self):
        return f"<TextBlock text={self.text[:60]!r}>"


class GroqCompatClient:
    """
    Wraps a raw Groq client and adds a `.messages` namespace so that
    Anthropic-style code works without modification.

    Also exposes `.chat.completions.create(...)` directly so agent.py's
    _safe_llm_call() continues to work unchanged.
    """

    def __init__(self, groq_client: Groq):
        self._groq = groq_client
        self.messages = _MessagesNamespace(groq_client)
        self.chat = groq_client.chat   # direct passthrough for _safe_llm_call

    # Make the compat client itself behave like the raw client for anything
    # we haven't explicitly wrapped (audio, models, etc.)
    def __getattr__(self, name: str):
        return getattr(self._groq, name)