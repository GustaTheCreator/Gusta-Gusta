2026-10-16 — Piper (Alan) only, English only, Whisper base.en local — simplest, audio stays on server
2026-10-16 — Two separate memories: dev vault (Obsidian) vs runtime memory (data/memory on server), no sync — assistant never reads dev notes
2026-10-17 — Renamed to Gusta-Gusta
2026-10-17 — Chat and curator use Claude Agent SDK on the subscription, not the paid API; ANTHROPIC_API_KEY dropped from env — no per-token cost
2026-10-17 — Own web_search tool removed; SDK WebSearch used — less code
2026-10-17 — Runtime memory stays only on the server, no copy/sync to the PC — keeps assistant memory private and separate from the dev vault
2026-10-18 — App renamed to Duarte (repo/package/container unchanged); Portuguese-only: Piper pt_PT-tugao-medium, Whisper small multilingual forced to pt, English voice removed; memory notes stay in English — user request
2026-10-18 — Revised: Gustavo speaks Portuguese (Whisper small, forced pt), Duarte answers in English with Piper en_GB-alan-medium; Portuguese voice dropped — user happy with an English voice, and ElevenLabs free tier cannot use Portuguese library voices
2026-10-18 — Project renamed to Duarte: Python package duarte, container/service duarte, MCP server name duarte; memory state dir stays .jarvis to keep existing server data
