from pathlib import Path


def read_md_files(folder: str) -> str:
    path = Path(folder).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"폴더가 존재하지 않습니다: {folder}")

    md_files = sorted(path.glob("*.md"))
    if not md_files:
        return ""

    parts = []
    for f in md_files:
        parts.append(f"## [{f.name}]\n\n{f.read_text(encoding='utf-8')}")

    return "\n\n---\n\n".join(parts)
