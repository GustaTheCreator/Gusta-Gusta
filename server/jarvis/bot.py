"""Pipeline de voz: microfone -> Whisper -> Claude -> voz, tudo em tempo real por WebRTC."""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner

from . import curator
from .config import settings
from .stt import EnglishWhisperSTT
from .tools import memory, news, weather, web_search
from .turns import PatientTurnStop
from .voices import make_tts

SYSTEM = """You are Gusta-Gusta, Gustavo's personal voice assistant, in the style of Tony Stark's J.A.R.V.I.S.: calm, witty and precise. You always speak English. Gustavo lives in Portugal.

Your words are spoken aloud by a speech synthesizer, so:
- Keep answers short and conversational: one to three sentences unless he asks for detail.
- Never use Markdown, lists, emojis, URLs or symbols. Write numbers and units the way they are said.
- His words come from speech recognition and can be slightly wrong. If a sentence makes little sense, go with the most likely meaning; ask only when you really cannot tell.

Interruptions: if he cuts you off, stop that thread. If he only says something like "stop", "that's enough", "okay thanks" or "never mind", reply with two or three words at most, or a simple "Of course.", and wait.

Tools:
- get_news for today's headlines from Portuguese newspapers. Summarise the main stories by theme, in English, instead of reading titles. Lead with stories about the topics he follows, listed below.
- get_weather for the weather; if no place is given, use {city}.
- search_web for anything current you do not know, including more detail on a news story.
- recall_memory to read everything saved about one topic, when he asks what you know or when the details matter for the answer.
- remember only when he explicitly asks you to remember something, or tells you something important about himself. Use the existing topic it belongs to. Everything else is reviewed and saved automatically after the conversation, so do not call it for routine requests or loose questions. Do it quietly and keep talking.

What you remember about Gustavo:
{memory}"""

# Silêncio (s) que fecha a tua vez: o VAD marca a pausa e depois espera mais um pouco por si
# continuares a falar. Total ~0,9 s; se a frase ficou a meio ("and the..."), mais 1,2 s.
STOP_SECS = 0.5
SPEECH_TIMEOUT = 0.4
UNFINISHED_EXTRA = 1.2
# Voz contínua (s) antes de contar como fala: ruídos curtos e tosse já não cortam o Gusta-Gusta.
START_SECS = 0.3

FILLER = "One moment."
# Ferramentas que demoram o suficiente para justificar a frase de espera.
SLOW_TOOLS = {"get_news", "get_weather", "search_web"}


async def get_news(params: FunctionCallParams):
    """Get today's headlines from the main Portuguese newspapers (in Portuguese; summarise them in English)."""
    await params.result_callback(await asyncio.to_thread(news.get_news))


async def get_weather(params: FunctionCallParams, city: str):
    """Get the current weather and the forecast for today and tomorrow.

    Args:
        city: Name of the city or town, e.g. "Lisbon".
    """
    await params.result_callback(await asyncio.to_thread(weather.get_weather, city))


async def search_web(params: FunctionCallParams, query: str):
    """Search the web for current information.

    Args:
        query: What to search for, phrased as a full question.
    """
    await params.result_callback(await web_search.search(query))


async def recall_memory(params: FunctionCallParams, topic: str):
    """Read everything saved about one topic, plus a summary of related topics.

    Args:
        topic: The topic, ideally one of the existing memory topics, e.g. "Formula 1".
    """
    await params.result_callback(await asyncio.to_thread(memory.recall, topic))


async def remember(params: FunctionCallParams, topic: str, fact: str, kind: str):
    """Save a fact about Gustavo that he explicitly asked you to remember.

    Args:
        topic: The existing memory topic it belongs to, or a short new English noun phrase
            such as "Family" or "Formula 1". Never a routine request like "news" or "weather".
        fact: The fact in one English sentence, in the third person, e.g. "He prefers tech news."
        kind: One of "preference", "person", "habit", "fact" or "interest".
    """
    await params.result_callback(await asyncio.to_thread(memory.save, topic, fact, kind))


TOOLS = [get_news, get_weather, search_web, recall_memory, remember]

# Revisões de memória ainda a correr; a referência impede que o asyncio as perca.
_reviews: set[asyncio.Task] = set()


def system_prompt() -> str:
    remembered = memory.load_context() or "(nothing yet)"
    return SYSTEM.format(city=settings.default_city, memory=remembered)


def review_later(messages: list):
    task = asyncio.create_task(curator.review(list(messages)))
    _reviews.add(task)
    task.add_done_callback(_reviews.discard)


async def run_bot(connection: SmallWebRTCConnection):
    transport = SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )
    stt = EnglishWhisperSTT()
    tts = make_tts()
    llm = AnthropicLLMService(
        api_key=settings.anthropic_api_key,
        settings=AnthropicLLMService.Settings(
            model=settings.claude_model,
            system_instruction=system_prompt(),
            max_tokens=4000,
            enable_prompt_caching=True,
            thinking=AnthropicLLMService.ThinkingConfig(type="adaptive"),
            # O Pipecat fixa os betas do pedido em streaming, por isso aqui não dá para
            # ligar os fallbacks do servidor; a pesquisa web (pedido à parte) usa-os.
            extra={"output_config": {"effort": settings.claude_effort}},
        ),
    )

    @llm.event_handler("on_function_calls_started")
    async def on_function_calls_started(service, function_calls):
        # Uma frase curta para não haver silêncio enquanto uma ferramenta lenta corre.
        if any(call.function_name in SLOW_TOOLS for call in function_calls):
            await tts.queue_frame(TTSSpeakFrame(FILLER))

    context = LLMContext(tools=TOOLS)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(start_secs=START_SECS, stop_secs=STOP_SECS)
            ),
            # Fim de turno por silêncio. O padrão do Pipecat usa um modelo Smart Turn que
            # se carrega a cada ligação (arranque lento) e na CPU do servidor não fecha o turno.
            user_turn_strategies=UserTurnStrategies(
                stop=[
                    PatientTurnStop(
                        user_speech_timeout=SPEECH_TIMEOUT, unfinished_extra=UNFINISHED_EXTRA
                    )
                ]
            ),
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )
    worker = PipelineWorker(pipeline, params=PipelineParams(enable_metrics=True))
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected")
        now = datetime.now(ZoneInfo("Europe/Lisbon")).strftime("%A %d %B %Y, %H:%M")
        context.add_message(
            {
                "role": "user",
                "content": f"{curator.GREETING_MARK}{now}. Gustavo just opened the app. "
                "Greet him in one short sentence.)",
            }
        )
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        review_later(context.get_messages())
        await runner.cancel()

    await runner.run()
