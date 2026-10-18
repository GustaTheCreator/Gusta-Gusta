"""Cérebro do Duarte: uma sessão do Claude Agent SDK por ligação, em vez da API.

O SDK corre o Claude Code por baixo e usa a subscrição (CLAUDE_CODE_OAUTH_TOKEN), por isso não
há custo por token. Uma só sessão vive durante a ligação inteira: o contexto fica quente e o
texto é enviado para a voz à medida que chega. As ferramentas correm no próprio servidor.
"""
import asyncio

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    StreamEvent,
    create_sdk_mcp_server,
    tool,
)
from loguru import logger
from pipecat.frames.frames import (
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.llm_service import LLMService
from pipecat.services.settings import LLMSettings

from .config import settings
from .tools import memory, news, weather

SERVER = "duarte"
FILLER = "One moment."
# Ferramentas que demoram o suficiente para justificar a frase de espera.
SLOW_TOOLS = {f"mcp__{SERVER}__get_news", f"mcp__{SERVER}__get_weather", "WebSearch"}


def _text(value: str) -> dict:
    return {"content": [{"type": "text", "text": value}]}


@tool("get_news", "Get today's headlines from the main Portuguese newspapers (in Portuguese; summarise them in English).", {})
async def get_news(args):
    return _text(await asyncio.to_thread(news.get_news))


@tool("get_weather", "Get the current weather and the forecast for today and tomorrow. city: e.g. \"Lisbon\".", {"city": str})
async def get_weather(args):
    return _text(await asyncio.to_thread(weather.get_weather, args.get("city")))


@tool(
    "recall_memory",
    "Read everything saved about one topic, plus a summary of related topics. topic: ideally an existing memory topic, e.g. \"Formula 1\".",
    {"topic": str},
)
async def recall_memory(args):
    return _text(await asyncio.to_thread(memory.recall, args["topic"]))


@tool(
    "remember",
    "Save a fact about Gustavo that he explicitly asked you to remember. topic: the existing memory topic it belongs to, "
    "or a short new English noun phrase such as \"Family\"; never a routine request like \"news\". fact: one English "
    "sentence in the third person, e.g. \"He prefers tech news.\" kind: one of preference, person, habit, fact or interest.",
    {"topic": str, "fact": str, "kind": str},
)
async def remember(args):
    return _text(await asyncio.to_thread(memory.save, args["topic"], args["fact"], args["kind"]))


TOOLS = [get_news, get_weather, recall_memory, remember]
ALLOWED = ["WebSearch", *(f"mcp__{SERVER}__{t.name}" for t in TOOLS)]


def base_options(**overrides) -> ClaudeAgentOptions:
    """Opções comuns: sem ferramentas do Claude Code, sem CLAUDE.md nem definições do utilizador."""
    defaults = dict(
        model=settings.claude_model,
        effort=settings.claude_effort,
        thinking={"type": "disabled"},  # a voz não espera por raciocínio
        setting_sources=[],
        tools=[],
    )
    return ClaudeAgentOptions(**{**defaults, **overrides})


def voice_options(system_prompt: str) -> ClaudeAgentOptions:
    return base_options(
        system_prompt=system_prompt,
        tools=["WebSearch"],
        allowed_tools=ALLOWED,
        mcp_servers={SERVER: create_sdk_mcp_server(SERVER, tools=TOOLS)},
        include_partial_messages=True,
    )


class AgentLLMService(LLMService):
    """Serviço LLM do Pipecat que fala com uma sessão ClaudeSDKClient."""

    def __init__(self, system_prompt: str, **kwargs):
        super().__init__(
            settings=LLMSettings(
                model=settings.claude_model,
                system_instruction=None,
                temperature=None,
                max_tokens=None,
                top_p=None,
                top_k=None,
                frequency_penalty=None,
                presence_penalty=None,
                seed=None,
                filter_incomplete_user_turns=False,
                user_turn_completion_config=None,
            ),
            **kwargs,
        )
        self._options = voice_options(system_prompt)
        self._client: ClaudeSDKClient | None = None
        self._dirty = False  # a resposta anterior foi cortada antes do ResultMessage

    async def _connect(self) -> ClaudeSDKClient:
        if self._client is None:
            client = ClaudeSDKClient(options=self._options)
            try:
                await client.connect()
            except BaseException:  # inclui o cancelamento por interrupção: não deixa meia-sessão guardada
                await client.disconnect()
                raise
            self._client = client
        return self._client

    async def _settle(self, client: ClaudeSDKClient):
        """Depois de uma interrupção, deita fora o resto da resposta antiga antes da pergunta nova."""
        if self._dirty:
            await client.interrupt()
            async for msg in client.receive_response():
                pass
            self._dirty = False

    async def _respond(self, text: str):
        client = await self._connect()
        await self._settle(client)
        await self.start_ttfb_metrics()
        self._dirty = True
        await client.query(text)
        async for msg in client.receive_response():
            if isinstance(msg, StreamEvent):
                await self._on_stream_event(msg.event)
            elif isinstance(msg, ResultMessage):
                if msg.is_error:
                    logger.warning(f"Claude session error: {msg.result}")
        self._dirty = False

    async def _on_stream_event(self, event: dict):
        kind = event.get("type")
        if kind == "content_block_delta" and event["delta"].get("type") == "text_delta":
            await self.stop_ttfb_metrics()
            await self._push_llm_text(event["delta"]["text"])
        elif kind == "content_block_start" and event["content_block"].get("type") == "tool_use":
            if event["content_block"]["name"] in SLOW_TOOLS:
                await self.push_frame(TTSSpeakFrame(FILLER))

    async def process_frame(self, frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if not isinstance(frame, LLMContextFrame):
            await self.push_frame(frame, direction)
            return
        user = next((m for m in reversed(frame.context.get_messages()) if m.get("role") == "user"), None)
        if user is None:
            return
        await self.push_frame(LLMFullResponseStartFrame())
        try:
            await self._respond(content_text(user["content"]))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.push_error(error_msg=f"Claude session failed: {exc}", exception=exc)
            self._client = None  # a próxima pergunta abre uma sessão nova
        finally:
            await self.push_frame(LLMFullResponseEndFrame())

    async def stop(self, frame):
        await self._close()
        await super().stop(frame)

    async def cancel(self, frame):
        await self._close()
        await super().cancel(frame)

    async def _close(self):
        client, self._client = self._client, None
        if client:
            await client.disconnect()


def content_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""
