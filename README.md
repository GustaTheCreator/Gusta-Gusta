# Gusta-Gusta

Assistente pessoal de voz ao estilo do J.A.R.V.I.S., para correr num homeserver modesto e usar a partir do telemóvel.

A página tem só uma bola. Tocas nela e falas: fica azul e mexe-se com a tua voz, e fica dourada quando o Jarvis responde. Ele percebe se falaste em português ou em inglês e responde na mesma língua, com voz masculina.

```
Telemóvel (browser) ──WebRTC por Tailscale──► homeserver (Docker)
  microfone ─► Silero VAD ─► Whisper (local) ─► Claude ─► voz (Piper) ─► altifalante
                                                  │
                                    notícias, meteorologia, pesquisa web, memória
```

## O que precisas

- Docker no servidor
- Uma chave da API da Anthropic
- Tailscale no servidor e no telemóvel

## Instalação

```bash
git clone https://github.com/GustaTheCreator/Gusta-Gusta.git && cd Gusta-Gusta
cp .env.example .env            # mete a ANTHROPIC_API_KEY
./scripts/download_voices.sh    # vozes Piper
docker compose up -d --build    # o Whisper descarrega-se no primeiro arranque
```

O browser só deixa usar o microfone em HTTPS, por isso publica a app na tua tailnet:

```bash
sudo tailscale serve --bg 7860
```

Abre `https://<nome-do-servidor>.<a-tua-tailnet>.ts.net` no telemóvel e toca na bola. No iPhone podes usar "Adicionar ao ecrã principal" para a teres como app.

## Configuração

Tudo no `.env` (nunca vai para o git). Os campos principais:

| Variável | Para que serve |
|---|---|
| `CLAUDE_MODEL` | `claude-opus-5-5` por omissão. `claude-haiku-5-5` responde mais depressa e é muito mais barato |
| `CLAUDE_EFFORT` | `low` chega para conversa |
| `WHISPER_MODEL` | `base` por omissão; `small` percebe melhor mas é mais lento no CPU |
| `DEFAULT_LANGUAGE` | língua da saudação inicial, `pt` ou `en` |
| `DEFAULT_CITY` | cidade usada quando pedes o tempo sem dizer onde |

## Memória

Quando lhe contas uma preferência ou um facto, o Jarvis guarda-o em `data/memory/` como notas Markdown ligadas por `[[ligações]]`. Essa pasta está no `.gitignore`. Podes abri-la como vault no Obsidian para ver o grafo e editar à mão (por exemplo, sincronizando-a com o Syncthing).

## Desenvolvimento

```bash
# servidor
cd server && python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest
python -m jarvis.server          # http://localhost:7860

# página (noutro terminal), com hot reload e proxy para o servidor
cd web && npm install && npm run dev
```

## Estrutura

- `server/jarvis/bot.py`: o pipeline de voz e as ferramentas que o Claude pode usar
- `server/jarvis/stt.py`: Whisper com deteção de português/inglês
- `server/jarvis/voices.py`: uma voz Piper por língua (Alan e Tugão)
- `server/jarvis/tools/`: notícias (RSS), meteorologia (Open-Meteo), pesquisa web e memória
- `web/src/Orb.tsx`: a bola
