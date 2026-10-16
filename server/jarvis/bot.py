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
from pipecat.turns.user_stop import SpeechTimeoutUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner

from .config import settings
from .language import LanguageState
from .stt import BilingualWhisperSTT
from .tools import memory, news, weather, web_search
from .voices import BilingualTTS

SYSTEM = """You are Jarvis, Gustavo's personal voice assistant, in the style of Tony Stark's J.A.R.V.I.S.: calm, witty and precise.

Language: always reply in the language Gustavo just spoke. That is English or European Portuguese (Portugal, never Brazilian Portuguese).

Your words are spoken aloud by a speech synthesizer, so:
- Keep answers short and conversational: one to three sentences unless he asks for detail.
- Never use Markdown, lists, emojis, URLs or symbols. Write numbers and units the way they are said.

Tools:
- get_news for today's Portuguese headlines; summarise the main stories by theme instead of reading titles.
- get_weather for the weather; if no place is given, use {city}.
- search_web for anything current you do not know.
- save_memory when Gustavo tells you a preference, a habit or a fact about his life worth remembering. Do it quietly and keep talking.

What you already remember about Gustavo:
{memory}"""

# Silêncio (s) que fecha a tua vez: o VAD marca a pausa e depois espera mais um pouco por si
# continuares a falar. Total ~0,9 s.
STOP_SECS = 0.5
SPEECH_TIMEOUT = 0.4

FILLERS = {"pt": "Um momento.", "en": "One moment."}


async def get_news(params: FunctionCallParams):
    """Get the latest headlines from the main Portuguese newspapers."""
    await params.result_callback(await asyncio.to_thread(news.get_news))


async def get_weather(params: FunctionCallParams, city: str):
    """Get the current weather and the forecast for today and tomorrow.

    Args:
        city: Name of the city or town, e.g. "Lisboa".
    """
    await params.result_callback(await asyncio.to_thread(weather.get_weather, city))


async def search_web(params: FunctionCallParams, query: str):
    """Search the web for current information.

    Args:
        query: What to search for, phrased as a full question.
    """
    await params.result_callback(await web_search.search(query))


async def save_memory(params: FunctionCallParams, topic: str, fact: str):
    """Remember a fact about Gustavo for future conversations.

    Args:
        topic: Short note title the fact belongs to, e.g. "Preferências de notícias" or "Família".
        fact: The fact itself, in one sentence. Mention related notes as [[Note title]].
    """
    await params.result_callback(memory.save(topic, fact))


TOOLS = [get_news, get_weather, search_web, save_memory]


def system_prompt() -> str:
    remembered = memory.load_context() or "(nothing yet)"
    return SYSTEM.format(city=settings.default_city, memory=remembered)


async def run_bot(connection: SmallWebRTCConnection):
    language = LanguageState(current=settings.default_language)

    transport = SmallWebRTCTransport(
        webrtc_connection=connection,
        params=TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    )
    stt = BilingualWhisperSTT(language)
    tts = BilingualTTS(language)
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
        # Uma frase curta para não haver silêncio enquanto a ferramenta corre.
        await tts.queue_frame(TTSSpeakFrame(FILLERS.get(language.current, FILLERS["en"])))

    context = LLMContext(tools=TOOLS)
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=STOP_SECS)),
            # Fim de turno só por silêncio. O padrão do Pipecat usa um modelo Smart Turn que
            # se carrega a cada ligação (arranque lento) e na CPU do servidor não fecha o turno.
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=SPEECH_TIMEOUT)]
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
        greeting_lang = "European Portuguese" if language.current == "pt" else "English"
        context.add_message(
            {
                "role": "user",
                "content": f"(It is {now}. Gustavo just opened the app. Greet him in one short "
                f"sentence in {greeting_lang}.)",
            }
        )
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await runner.cancel()

    await runner.run()
