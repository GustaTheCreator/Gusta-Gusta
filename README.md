# Duarte

Assistente pessoal de voz ao estilo do J.A.R.V.I.S., para correr num homeserver modesto e usar a partir do telemóvel.

A página tem só uma bola. Tocas nela e falas: fica azul e mexe-se com a tua voz, e fica dourada quando o Duarte responde. Falas-lhe em português e ele responde em inglês, com a voz Piper Alan: o Whisper corre com a língua fixada em português, sem deteção automática. As notícias vêm dos jornais portugueses, resumidas em inglês.

```
Telemóvel (browser) ──WebRTC por Tailscale──► homeserver (Docker)
  microfone ─► Silero VAD ─► Whisper (local) ─► Claude (Agent SDK) ─► voz (Piper) ─► altifalante
                                                  │
                                    notícias, meteorologia, pesquisa web (WebSearch do Claude), memória
```

## O que precisas

- Docker no servidor
- Uma subscrição Claude (Pro/Max): o servidor usa o Claude Agent SDK, sem custo por token
- Tailscale no servidor e no telemóvel

## Instalação

```bash
git clone https://github.com/GustaTheCreator/Gusta-Gusta.git && cd Gusta-Gusta
claude setup-token              # num PC com o Claude Code: gera o token da subscrição
cp .env.example .env            # mete-o em CLAUDE_CODE_OAUTH_TOKEN
./scripts/download_voices.sh    # voz Piper (Alan, inglês)
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
| `CLAUDE_MODEL` | `claude-haiku-5-5` por omissão: responde depressa e poupa os limites da subscrição |
| `CLAUDE_EFFORT` | `low` chega para conversa |
| `WHISPER_MODEL` | `small` por omissão (multilingue, é o mínimo que percebe bem português); `base` é mais rápido mas erra mais |
| `WHISPER_BEAM_SIZE` | `3` por omissão; `1` é mais rápido, `5` percebe melhor |
| `MEMORY_MODEL` | modelo que revê a conversa no fim e decide o que guardar; por omissão o `CLAUDE_MODEL` |
| `DEFAULT_CITY` | cidade usada quando pedes o tempo sem dizer onde |

## Memória

A memória fica em `data/memory/` como notas Markdown, **uma por tópico**, ligadas por `[[ligações]]`. Essa pasta está no `.gitignore` e nunca vai para o repositório. Podes abri-la como vault no Obsidian para ver o grafo e editar à mão, por exemplo sincronizando-a com o Syncthing. As linhas que escreveres à mão mantêm-se.

Como decide o que guardar:

- **No fim de cada conversa** (quando desligas), o Claude relê-a e escolhe o que vale a pena guardar. Isto corre fora da conversa, por isso não atrasa as respostas.
- **Pedidos de rotina não ficam guardados.** "Quais são as notícias?" ou "Como está o tempo?" não criam tópicos.
- **Ficam guardados os interesses a sério.** Se pedes as notícias e depois perguntas mais sobre uma delas, esse assunto passa a ser um tópico de interesse. Nos dias seguintes, o Gusta-Gusta começa as notícias por aí.
- **Uma pergunta solta** sobre um assunto fica como candidata em `data/memory/.jarvis/`. Só passa a tópico se voltares a ela noutro dia.
- **Cada assunto vai para o tópico que já existe** (pelo título, pelos aliases ou por um nome parecido), em vez de criar uma nota nova. Os nomes alternativos ficam em `aliases`.
- Se lhe pedires explicitamente ("remember that..."), guarda logo.

Cada nota tem propriedades (`type`, `aliases`, `mentions`, `updated`). O prompt recebe um resumo com o perfil, os interesses mais falados e a lista de tópicos. Quando os pormenores contam, o Duarte lê a nota inteira com a ferramenta `recall_memory`. A nota `Jarvis.md` é o índice e é regenerada automaticamente.

## Conversa

- **Fim da tua vez:** o Duarte responde depois de ~0,9 s de silêncio. Se a frase parecer a meio ("fala-me das..."), espera mais 1,2 s. Os valores estão no topo de `server/duarte/bot.py`.
- **Interromper:** fala por cima dele e ele cala-se. Ruídos curtos (menos de 0,3 s) já não o cortam. Se só disseres "stop" ou "that's enough", responde com duas palavras e espera.

## Desenvolvimento

```bash
# servidor
cd server && python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest
python -m duarte.server          # http://localhost:7860

# página (noutro terminal), com hot reload e proxy para o servidor
cd web && npm install && npm run dev
```

## Estrutura

- `server/duarte/bot.py`: o pipeline de voz e as ferramentas que o Claude pode usar
- `server/duarte/stt.py`: Whisper só em português
- `server/duarte/turns.py`: quando é que acabaste de falar
- `server/duarte/voices.py`: a voz Piper (Alan)
- `server/duarte/curator.py`: revisão da conversa no fim, para a memória
- `server/duarte/tools/`: notícias (RSS), meteorologia (Open-Meteo), pesquisa web e memória por tópicos
- `web/src/Orb.tsx`: a bola
