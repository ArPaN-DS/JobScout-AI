from pathlib import Path

from .models import CandidateProfile, EvidenceSource, ProfileClaim
from .schemas import normalize_claim


EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
    "tmp_uploads",
    "data",
    "sessions",
}

EXCLUDED_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "db.sqlite3",
    "master_profile.json",
    "credentials.json",
    "secrets.json",
}

ALLOWED_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
}

MAX_FILE_BYTES = 160_000
MAX_FILES = 80


def iter_candidate_files(root_path: str | Path):
    root = Path(root_path).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError("Project folder does not exist or is not a directory.")

    yielded = 0
    for path in root.rglob("*"):
        if yielded >= MAX_FILES:
            break
        if _is_excluded(path, root):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        try:
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yielded += 1
        yield path


def scan_local_folder(profile: CandidateProfile, root_path: str | Path) -> EvidenceSource:
    root = Path(root_path).expanduser().resolve()
    source = EvidenceSource.objects.create(
        profile=profile,
        source_type=EvidenceSource.SourceType.LOCAL_FOLDER,
        label=root.name,
        uri=str(root),
        metadata={"max_files": MAX_FILES, "max_file_bytes": MAX_FILE_BYTES},
    )

    technologies: set[str] = set()
    project_notes: list[str] = []
    for path in iter_candidate_files(root):
        rel_path = str(path.relative_to(root))
        text = _read_text(path)
        if not text:
            continue
        if path.name.lower() in {"readme.md", "readme.txt"}:
            first_lines = [line.strip() for line in text.splitlines() if line.strip()][:6]
            if first_lines:
                project_notes.append(f"{rel_path}: {' '.join(first_lines)[:400]}")
        technologies.update(_detect_technologies(path, text))

    for tech in sorted(technologies):
        _create_claim(profile, source, ProfileClaim.Category.SKILL, tech, evidence_text=f"Detected in {root}")
    for note in project_notes[:20]:
        _create_claim(profile, source, ProfileClaim.Category.PROJECT, note, evidence_text=note)
    return source


def _is_excluded(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    lowered_parts = {part.lower() for part in rel_parts}
    if lowered_parts & EXCLUDED_DIRS:
        return True
    if path.name.lower() in EXCLUDED_NAMES:
        return True
    if path.suffix.lower() in {".sqlite3", ".db", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".zip"}:
        return True
    return False


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _detect_technologies(path: Path, text: str) -> set[str]:
    lowered = f"{path.name}\n{text[:20000]}".lower()
    checks = {
        "Python": [".py", "django", "fastapi", "pydantic", "pytest"],
        "Django": ["django"],
        "FastAPI": ["fastapi"],
        "JavaScript": [".js", "javascript"],
        "TypeScript": [".ts", ".tsx", "typescript"],
        "React": ["react", "jsx", "tsx"],
        "HTML": [".html", "<html"],
        "CSS": [".css", "stylesheet"],
        "Docker": ["dockerfile", "docker-compose"],
        "SQL": ["select ", "insert into", "sqlite", "postgres"],
        "Machine Learning": ["machine learning", "sklearn", "pytorch", "tensorflow"],
        "LLMs": ["llm", "openai", "gemini", "anthropic", "ollama"],
    }
    found = set()
    for tech, markers in checks.items():
        if any(marker in lowered for marker in markers):
            found.add(tech)
    return found


def _create_claim(profile, source, category, value, evidence_text=""):
    ProfileClaim.objects.update_or_create(
        profile=profile,
        category=category,
        normalized_value=normalize_claim(value),
        defaults={
            "source": source,
            "value": value,
            "evidence_text": evidence_text,
            "status": ProfileClaim.Status.EVIDENCE_BACKED,
        },
    )
