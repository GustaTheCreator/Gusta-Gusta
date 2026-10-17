import { useEffect, useRef, useState } from "react";

import { RTVIEvent } from "@pipecat-ai/client-js";
import {
  usePipecatClientMediaTrack,
  usePipecatClientTransportState,
  useRTVIClientEvent,
} from "@pipecat-ai/client-react";
import { Plasma, type PlasmaConfig, type PlasmaRef } from "@pipecat-ai/voice-ui-kit/webgl";

import { setThinkingSound } from "./thinkingSound";

type Props = {
  onConnect?: () => void | Promise<void>;
  onDisconnect?: () => void | Promise<void>;
  error?: string | null;
};

// Azul enquanto ouve, violeta enquanto pensa, dourado enquanto o Gusta-Gusta fala, cinzento desligado.
const IDLE: PlasmaConfig = {
  useCustomColors: true,
  backgroundColor: "#000000",
  color1: "#3a4150",
  color2: "#1c2230",
  color3: "#5b6475",
  intensity: 1.2,
  radius: 1.4,
  plasmaSpeed: 0.2,
  effectScale: 0.5,
  ringVisibility: 0.15,
  audioEnabled: true,
  audioSensitivity: 1.5,
  // Ataque rápido e descida lenta: o movimento segue a voz sem tremer.
  audioSmoothing: 0.9,
  audioLerpSpeed: 0.1,
};
const LISTENING: PlasmaConfig = {
  ...IDLE,
  color1: "#2fb8ff",
  color2: "#0a4b8f",
  color3: "#8fe3ff",
  intensity: 1.9,
  radius: 1.65,
  plasmaSpeed: 0.35,
  ringVisibility: 0.3,
};
const THINKING: PlasmaConfig = {
  ...LISTENING,
  color1: "#a78bfa",
  color2: "#4c1d95",
  color3: "#e9d5ff",
  intensity: 1.6,
  plasmaSpeed: 1.1,
  ringVisibility: 0.55,
  audioEnabled: false,
};
const SPEAKING: PlasmaConfig = {
  ...LISTENING,
  color1: "#ffb347",
  color2: "#c2410c",
  color3: "#ffe08a",
  intensity: 2.2,
  plasmaSpeed: 0.6,
};
const CONNECTING: PlasmaConfig = { ...LISTENING, plasmaSpeed: 3, colorCycleSpeed: 3 };

export function Orb({ onConnect, onDisconnect, error }: Props) {
  const state = usePipecatClientTransportState();
  const micTrack = usePipecatClientMediaTrack("audio", "local");
  const botTrack = usePipecatClientMediaTrack("audio", "bot");
  const [botSpeaking, setBotSpeaking] = useState(false);
  const [userSpeaking, setUserSpeaking] = useState(false);
  // Entre o fim da tua frase e a primeira palavra da resposta (inclui esperas por ferramentas).
  const [waiting, setWaiting] = useState(false);
  const [llmActive, setLlmActive] = useState(false);
  const plasma = useRef<PlasmaRef>(null);

  useRTVIClientEvent(RTVIEvent.BotStartedSpeaking, () => {
    setBotSpeaking(true);
    setWaiting(false);
  });
  useRTVIClientEvent(RTVIEvent.BotStoppedSpeaking, () => setBotSpeaking(false));
  useRTVIClientEvent(RTVIEvent.UserStartedSpeaking, () => {
    setUserSpeaking(true);
    setWaiting(false);
  });
  useRTVIClientEvent(RTVIEvent.UserStoppedSpeaking, () => {
    setUserSpeaking(false);
    setWaiting(true);
  });
  useRTVIClientEvent(RTVIEvent.BotLlmStarted, () => setLlmActive(true));
  useRTVIClientEvent(RTVIEvent.BotLlmStopped, () => {
    setLlmActive(false);
    // Se a resposta falhar e nunca chegar a falar, não fica a pensar para sempre.
    setTimeout(() => setWaiting(false), 3000);
  });

  const connected = state === "ready";
  const busy = !connected && state !== "disconnected" && state !== "error";

  const thinking = connected && !botSpeaking && !userSpeaking && (waiting || llmActive);

  useEffect(() => {
    if (!connected) {
      setBotSpeaking(false);
      setUserSpeaking(false);
      setWaiting(false);
      setLlmActive(false);
    }
    plasma.current?.updateConfig(
      connected
        ? botSpeaking
          ? SPEAKING
          : thinking
            ? THINKING
            : LISTENING
        : busy
          ? CONNECTING
          : IDLE,
    );
  }, [connected, busy, botSpeaking, thinking]);

  useEffect(() => setThinkingSound(thinking), [thinking]);

  // A bola reage à voz de quem estiver a falar.
  const track = connected ? (botSpeaking ? botTrack : micTrack) : null;

  const label = error
    ? "Não consegui ligar. Toca para tentar outra vez."
    : busy
      ? "A ligar…"
      : connected
        ? botSpeaking
          ? "Gusta-Gusta"
          : thinking
            ? "A pensar…"
            : "Estou a ouvir"
        : "Toca para falar com o Gusta-Gusta";

  const toggle = () => {
    if (busy) return;
    if (connected) void onDisconnect?.();
    else void onConnect?.();
  };

  return (
    <main className="stage">
      <button className="orb" onClick={toggle} aria-label={connected ? "Desligar" : "Ligar"}>
        <Plasma ref={plasma} initialConfig={IDLE} audioTrack={track} className="plasma" />
      </button>
      <p className="label">{label}</p>
    </main>
  );
}
