// Pulso suave sintetizado (sem ficheiro de áudio) enquanto o Duarte pensa.
let ctx: AudioContext | null = null;
let gain: GainNode | null = null;

function start() {
  ctx = new AudioContext();
  gain = ctx.createGain();
  gain.gain.value = 0;
  gain.connect(ctx.destination);
  const tone = ctx.createOscillator();
  tone.frequency.value = 196;
  const lfo = ctx.createOscillator();
  lfo.frequency.value = 1.4;
  const depth = ctx.createGain();
  depth.gain.value = 0.02;
  lfo.connect(depth).connect(gain.gain);
  tone.connect(gain);
  tone.start();
  lfo.start();
}

export function setThinkingSound(on: boolean) {
  try {
    if (on && !ctx) start();
    if (!ctx || !gain) return;
    void ctx.resume();
    gain.gain.setTargetAtTime(on ? 0.03 : 0, ctx.currentTime, 0.15);
  } catch {
    // sem áudio disponível: o visual chega
  }
}
