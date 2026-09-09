from functools import lru_cache
from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    path = (PROMPT_DIR / name).resolve()
    root = PROMPT_DIR.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ValueError(f"Invalid prompt name: {name}")
    return path.read_text(encoding="utf-8").strip()


def load_prompt_template(name: str, **values: object) -> str:
    return load_prompt(name).format(**values)
