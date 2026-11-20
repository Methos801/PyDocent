"""Loads lesson definitions from JSON files in lessons/data/.

Adding a new lesson is as simple as dropping a new NN_name.json file in the
data folder — it is picked up automatically, sorted by filename.
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _data_files():
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted(f for f in os.listdir(DATA_DIR) if f.endswith(".json"))


def load_all():
    """Return the full list of lessons, sorted by filename."""
    lessons = []
    for fname in _data_files():
        path = os.path.join(DATA_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                lessons.append(json.load(fh))
        except (json.JSONDecodeError, OSError) as exc:
            # Skip a broken lesson file rather than crashing the whole app.
            print(f"[loader] skipping {fname}: {exc}")
    return lessons


def load_summaries():
    """Lightweight list for the sidebar — no section bodies."""
    out = []
    for lesson in load_all():
        out.append({
            "id": lesson.get("id"),
            "title": lesson.get("title", "Untitled"),
            "subtitle": lesson.get("subtitle", ""),
            "emoji": lesson.get("emoji", "📘"),
            "minutes": lesson.get("minutes", 5),
            "xp": lesson.get("xp", 50),
            "accent": lesson.get("accent", "#00d4ff"),
        })
    return out


def load_one(lesson_id):
    """Return the full lesson dict for a given id, or None."""
    for lesson in load_all():
        if lesson.get("id") == lesson_id:
            return lesson
    return None
