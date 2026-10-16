from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from jarvis.tools import memory


@pytest.fixture(autouse=True)
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "settings", SimpleNamespace(memory_dir=tmp_path))
    return tmp_path


def test_facts_go_to_the_existing_topic(vault):
    assert memory.save("Formula 1", "He follows the championship fight.", "interest").startswith("Saved under a new")
    assert "existing topic Formula 1" in memory.save("formula 1", "He supports McLaren.", "interest")
    # Variantes do mesmo nome caem na mesma nota.
    for name in ("Formula 1 season", "the Formula 1", "formula 1"):
        memory.save(name, f"Fact about {name}.", "interest")
    files = sorted(p.name for p in vault.glob("*.md"))
    assert "Formula 1.md" in files and "Formula 1 season.md" not in files
    note = memory.find("formula 1")
    assert note.kind == "interest" and note.mentions >= 4
    assert "Formula 1 season" in note.aliases


def test_routine_requests_are_never_topics(vault):
    for topic in ("News", "Today's news", "daily news", "Weather", "the headlines", "Small talk"):
        assert memory.save(topic, "He asked for the news.").startswith("Not saved")
        assert memory.note_candidate(topic, "He asked for the news.") == "ignored"
    assert not list(vault.glob("*.md"))


def test_duplicate_facts_are_not_repeated(vault):
    memory.save("Family", "His mum is called Ana.", "person")
    assert memory.save("family", "His mum is called Ana", "person").startswith("Already known")
    assert memory.find("Family").facts[0].startswith("His mum is called Ana.")
    assert len(memory.find("Family").facts) == 1


def test_note_round_trip_keeps_hand_edits(vault):
    memory.save("Benfica", "He is a Benfica supporter.", "interest", related=["Football"])
    path = vault / "Benfica.md"
    path.write_text(path.read_text() + "\nWritten by hand in Obsidian.\n")
    memory.save("Benfica", "He goes to home games.", "interest")
    text = path.read_text()
    assert text.startswith("---\ntype: interest\n")
    assert "Linked to [[Jarvis]]" in text and "Related: [[Football]]" in text
    assert "Written by hand in Obsidian." in text
    assert text.count("\n- He") == 2
    index = (vault / "Jarvis.md").read_text()
    assert "## Interests" in index and "- [[Benfica]]" in index


def test_old_notes_without_frontmatter_still_work(vault):
    (vault / "Preferências de notícias.md").write_text(
        "# Preferências de notícias\n\nLigado a [[Jarvis]]\n\n- Prefere tecnologia. _(2026-10-01)_\n",
        encoding="utf-8",
    )
    assert "existing topic Preferências de notícias" in memory.save(
        "preferencias de noticias", "Gosta do Benfica."
    )
    note = memory.find("Preferências de notícias")
    assert len(note.facts) == 2 and note.mentions == 2
    assert "Ligado a" not in (vault / "Preferências de notícias.md").read_text(encoding="utf-8")


def test_loose_question_becomes_interest_only_when_it_comes_back(vault, monkeypatch):
    assert memory.note_candidate("Lisbon metro strike", "He asked when the strike ends.") == "pending"
    assert memory.note_candidate("Lisbon metro strike", "Asked again the same day.") == "pending"
    assert memory.find("Lisbon metro strike") is None

    tomorrow = date.today() + timedelta(days=1)
    monkeypatch.setattr(memory, "date", SimpleNamespace(today=lambda: tomorrow, fromtimestamp=date.fromtimestamp))
    assert memory.note_candidate("Lisbon Metro strikes", "He asked about the new strike day.") == "promoted"
    note = memory.find("Lisbon metro strike")
    assert note is not None and note.kind == "interest" and len(note.facts) == 3


def test_candidate_for_existing_topic_counts_as_mention(vault):
    memory.save("Benfica", "He is a Benfica supporter.", "interest")
    assert memory.note_candidate("Benfica", "He asked about the next match.") == "existing"
    assert memory.find("Benfica").mentions == 2


def test_recall_and_context(vault):
    memory.save("Football", "He plays five-a-side on Thursdays.", "habit")
    memory.save("Benfica", "He is a Benfica supporter.", "interest", related=["Football"])
    out = memory.recall("benfica")
    assert "He is a Benfica supporter." in out and "Related, Football: He plays five-a-side" in out
    assert memory.recall("Tennis").startswith("Nothing saved about Tennis")

    context = memory.load_context()
    assert "About him:" in context and "Football: He plays five-a-side on Thursdays." in context
    assert "Topics he follows" in context and "Benfica (mentioned 1 times" in context
    assert context.splitlines()[-1].startswith("Existing memory topics: ")
    assert {"Benfica", "Football"} == set(context.splitlines()[-1].split(": ")[1].split(", "))
