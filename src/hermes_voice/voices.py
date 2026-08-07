"""Voice catalog: public Piper index (35 languages) and Kokoro (9 languages).

Two sources, two natures:

  Piper   -- community catalog with hundreds of voices in 35 languages. We
             don't hardcode a list here: we query the voices.json published on
             Hugging Face at runtime, with MD5 verification from the index
             itself. A new upstream voice appears without a release from us.

  Kokoro  -- a single weights file with 54 built-in voices, 9 languages. Static
             list because there's nothing to discover: either the file is there,
             or it isn't.

Nothing here requires an account, API key, or accepting terms. Every download is
from a public source, with declared license.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("hermes.voices")

PIPER_TAG = "v1.0.0"
PIPER_REPO = f"https://huggingface.co/rhasspy/piper-voices/resolve/{PIPER_TAG}"
PIPER_INDEX_URL = f"{PIPER_REPO}/voices.json"
PIPER_RELEASE = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2"
KOKORO_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
SILERO_URL = (
    "https://raw.githubusercontent.com/snakers4/silero-vad/master/"
    "src/silero_vad/data/silero_vad.onnx"
)

INDEX_CACHE = "cache/piper-voices.json"
INDEX_MAX_AGE_S = 7 * 24 * 3600

DEFAULT_VOICE = "pt_BR-faber-medium"
DEFAULT_LANG = "pt_BR"


class DownloadError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Kokoro: 54 voices in 9 languages, in a single weights file.
# Prefix: 1st letter = language, 2nd = gender (f/m).
# ---------------------------------------------------------------------------
KOKORO_LANGS = {
    "a": ("en_US", "American English"),
    "b": ("en_GB", "British English"),
    "e": ("es", "Spanish"),
    "f": ("fr_FR", "French"),
    "h": ("hi", "Hindi"),
    "i": ("it", "Italian"),
    "j": ("ja", "Japanese"),
    "p": ("pt_BR", "Brazilian Portuguese"),
    "z": ("zh", "Mandarin"),
}

KOKORO_VOICES: tuple[str, ...] = (
    "af_heart",
    "af_bella",
    "af_nicole",
    "af_sarah",
    "am_michael",
    "am_adam",
    "am_fenrir",
    "am_puck",
    "bf_emma",
    "bf_isabella",
    "bm_george",
    "bm_lewis",
    "ef_dora",
    "em_alex",
    "em_santa",
    "ff_siwis",
    "hf_alpha",
    "hf_beta",
    "hm_omega",
    "hm_psi",
    "if_sara",
    "im_nicola",
    "jf_alpha",
    "jf_gongitsune",
    "jm_kumo",
    "pf_dora",
    "pm_alex",
    "pm_santa",
    "zf_xiaobei",
    "zf_xiaoxiao",
    "zm_yunjian",
    "zm_yunxi",
)


@dataclass(slots=True)
class Asset:
    url: str
    dest: str
    size_bytes: int = 0
    md5: str = ""

    @property
    def size_mb(self) -> float:
        return self.size_bytes / 1_048_576 if self.size_bytes else 0.0


@dataclass(slots=True)
class Voice:
    id: str
    engine: str
    language: str
    language_name: str
    gender: str
    quality: str
    license: str
    commercial: bool
    notes: str = ""
    assets: list[Asset] = field(default_factory=list)
    voice_arg: str = ""


# ---------------------------------------------------------------------------
# Piper index
# ---------------------------------------------------------------------------
def _cache_path(root: Path) -> Path:
    return root / INDEX_CACHE


def fetch_piper_index(root: Path, refresh: bool = False) -> dict:
    """Downloads and caches voices.json. 7-day cache."""
    cache = _cache_path(root)
    fresh = cache.exists() and time.time() - cache.stat().st_mtime < INDEX_MAX_AGE_S
    if not refresh and fresh:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Index cache corrupted; re-downloading.")

    log.info("Fetching Piper voice index...")
    try:
        req = urllib.request.Request(PIPER_INDEX_URL, headers={"User-Agent": "hermes-voice"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        if cache.exists():
            log.warning("Index unreachable (%s); using old cache.", exc)
            return json.loads(cache.read_text(encoding="utf-8"))
        raise DownloadError(
            f"Could not fetch voice index ({exc}). "
            "Check your connection; no account is required."
        ) from exc

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(raw, encoding="utf-8")
    return json.loads(raw)


def _piper_voice_from_entry(key: str, entry: dict) -> Voice | None:
    lang = entry.get("language") or {}
    code = lang.get("code") or ""
    if not code:
        return None
    assets: list[Asset] = []
    for path, meta in (entry.get("files") or {}).items():
        if not (path.endswith(".onnx") or path.endswith(".onnx.json")):
            continue
        assets.append(
            Asset(
                url=f"{PIPER_REPO}/{path}",
                dest=f"voices/{Path(path).name}",
                size_bytes=int((meta or {}).get("size_bytes") or 0),
                md5=str((meta or {}).get("md5_digest") or ""),
            )
        )
    if not any(a.dest.endswith(".onnx") for a in assets):
        return None

    speakers = int(entry.get("num_speakers") or 1)
    return Voice(
        id=key,
        engine="piper",
        language=code,
        language_name=lang.get("name_english") or lang.get("name_native") or code,
        gender="multi" if speakers > 1 else "-",
        quality=str(entry.get("quality") or "medium"),
        license="MIT",
        commercial=True,
        notes=f"{speakers} speakers" if speakers > 1 else "",
        assets=assets,
    )


def piper_catalog(root: Path, refresh: bool = False) -> dict[str, Voice]:
    index = fetch_piper_index(root, refresh)
    out: dict[str, Voice] = {}
    for key, entry in index.items():
        if not isinstance(entry, dict):
            continue
        voice = _piper_voice_from_entry(key, entry)
        if voice is not None:
            out[voice.id] = voice
    return out


def kokoro_catalog() -> dict[str, Voice]:
    shared = [
        Asset(f"{KOKORO_BASE}/kokoro-v1.0.onnx", "models/kokoro-v1.0.onnx", 343_000_000),
        Asset(f"{KOKORO_BASE}/voices-v1.0.bin", "models/voices-v1.0.bin", 28_000_000),
    ]
    out: dict[str, Voice] = {}
    for vid in KOKORO_VOICES:
        code, name = KOKORO_LANGS.get(vid[0], ("?", "?"))
        out[vid] = Voice(
            id=vid,
            engine="kokoro",
            language=code,
            language_name=name,
            gender="female" if vid[1] == "f" else "male",
            quality="high",
            license="Apache-2.0",
            commercial=True,
            notes="shared weights across all Kokoro voices",
            assets=shared,
            voice_arg=vid,
        )
    return out


def full_catalog(root: Path, refresh: bool = False, include_piper: bool = True) -> dict[str, Voice]:
    """Kokoro always; Piper when the index is reachable."""
    catalog = kokoro_catalog()
    if include_piper:
        try:
            catalog.update(piper_catalog(root, refresh))
        except DownloadError as exc:
            log.warning("Piper catalog unavailable: %s", exc)
    return catalog


def search(
    catalog: dict[str, Voice], lang: str = "", gender: str = "", engine: str = "", quality: str = ""
) -> list[Voice]:
    """Filter by language (prefix: 'pt' matches pt_BR and pt_PT), gender, engine."""
    lang, gender, engine, quality = (s.lower() for s in (lang, gender, engine, quality))
    hits = []
    for v in catalog.values():
        if lang and not v.language.lower().startswith(lang):
            continue
        if gender and not v.gender.lower().startswith(gender):
            continue
        if engine and v.engine != engine:
            continue
        if quality and v.quality.lower() != quality:
            continue
        hits.append(v)
    return sorted(hits, key=lambda v: (v.language, v.engine, v.id))


def languages(catalog: dict[str, Voice]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for v in catalog.values():
        key = f"{v.language}  {v.language_name}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def _human(mb: float) -> str:
    return f"{mb:.0f} MB" if mb >= 1 else f"{mb * 1024:.0f} KB"


def piper_binary_asset() -> Asset | None:
    import platform

    key = f"{platform.system()}-{platform.machine()}".lower()
    table = {
        "windows-amd64": "piper_windows_amd64.zip",
        "windows-x86_64": "piper_windows_amd64.zip",
        "linux-x86_64": "piper_linux_x86_64.tar.gz",
        "linux-aarch64": "piper_linux_aarch64.tar.gz",
        "darwin-arm64": "piper_macos_aarch64.tar.gz",
        "darwin-x86_64": "piper_macos_x64.tar.gz",
    }
    name = table.get(key)
    if name is None:
        return None
    return Asset(f"{PIPER_RELEASE}/{name}", f"bin/{name}", 20_000_000)


def fetch(asset: Asset, root: Path, force: bool = False, progress: bool = True) -> Path:
    dest = root / asset.dest
    if dest.exists() and not force and _verify(dest, asset):
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    if progress:
        size = f" ({_human(asset.size_mb)})" if asset.size_bytes else ""
        print(f"  downloading {dest.name}{size}...", flush=True)
    try:
        req = urllib.request.Request(asset.url, headers={"User-Agent": "hermes-voice"})
        with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as fh:
            shutil.copyfileobj(r, fh, length=1 << 20)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        tmp.unlink(missing_ok=True)
        raise DownloadError(f"Failed to download {asset.url}: {exc}") from exc

    if asset.md5:
        digest = hashlib.md5(tmp.read_bytes(), usedforsecurity=False).hexdigest()
        if digest != asset.md5:
            tmp.unlink(missing_ok=True)
            raise DownloadError(
                f"MD5 mismatch for {dest.name}: index says {asset.md5[:12]}, "
                f"the downloaded file gave {digest[:12]}"
            )
    tmp.replace(dest)
    if dest.suffix in {".zip", ".gz"}:
        _extract(dest)
    return dest


def _verify(path: Path, asset: Asset) -> bool:
    """Size and MD5 when the index provides them. Without them, presence is enough."""
    if asset.size_bytes and path.stat().st_size != asset.size_bytes:
        log.warning("%s has unexpected size; re-downloading.", path.name)
        return False
    if asset.md5:
        digest = hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()
        if digest != asset.md5:
            log.warning("%s has mismatched MD5; re-downloading.", path.name)
            return False
    return True


def _extract(archive: Path) -> None:
    target = archive.parent
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            z.extractall(target)
    else:
        with tarfile.open(archive, "r:gz") as tf:
            try:
                tf.extractall(target, filter="data")  # avoids path traversal
            except TypeError:  # Python < 3.12
                _extract_safe(tf, target)
    archive.unlink(missing_ok=True)
    for exe in target.rglob("piper"):
        if exe.is_file():
            exe.chmod(0o755)


def _extract_safe(tf: tarfile.TarFile, target: Path) -> None:
    """Extract tar members safely, preventing path traversal on Python < 3.12."""
    resolved = target.resolve()
    for member in tf.getmembers():
        member_path = (target / member.name).resolve()
        if not str(member_path).startswith(str(resolved) + os.sep) and member_path != resolved:
            raise ValueError(f"tar member escapes target: {member.name}")
        if member.issym() or member.islnk():
            link_target = Path(member.linkname)
            if link_target.is_absolute() or ".." in str(link_target):
                raise ValueError(f"unsafe symlink/link in tar: {member.name} -> {member.linkname}")
        tf.extract(member, target)


def install_voice(voice: Voice, root: Path, force: bool = False) -> Voice:
    for asset in voice.assets:
        fetch(asset, root, force)
    if voice.engine == "piper":
        binary = piper_binary_asset()
        if binary is not None and not (root / "bin" / "piper").exists():
            fetch(binary, root, force)
    return voice


def install_support(root: Path, force: bool = False) -> None:
    fetch(Asset(SILERO_URL, "models/silero_vad.onnx", 2_300_000), root, force)


def is_installed(voice: Voice, root: Path) -> bool:
    return all((root / a.dest).exists() for a in voice.assets)


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
def describe(catalog: dict[str, Voice], root: Path, lang: str = "", limit: int = 40) -> str:
    hits = search(catalog, lang=lang)
    lines = [""]
    if lang:
        lines.append(f"Voices for '{lang}': {len(hits)} found.")
    else:
        lines.append(
            f"{len(catalog)} voices in {len(languages(catalog))} languages. Filter with --lang."
        )
    lines += [
        "",
        f"  {'ID':<30}{'LANG':<9}{'ENGINE':<9}{'GENDER':<11}{'LIC.':<12}INSTALLED",
        "  " + "-" * 84,
    ]
    for v in hits[:limit]:
        mark = "yes" if is_installed(v, root) else "no"
        default = "  <- default" if v.id == DEFAULT_VOICE else ""
        lines.append(
            f"  {v.id:<30}{v.language:<9}{v.engine:<9}{v.gender:<11}{v.license:<12}{mark}{default}"
        )
    if len(hits) > limit:
        lines.append(f"  ... and {len(hits) - limit} more. Filter with --lang.")
    lines += [
        "",
        "  Install:  hermes-voice voices --install <ID>",
        "  Languages: hermes-voice voices --languages",
        "  Use:       hermes-voice --voice <ID>",
        "",
        "  Piper is MIT, Kokoro is Apache-2.0: both allow commercial use.",
        "  About voice cloning and rights: docs/VOICE_LICENSING.md",
        "",
    ]
    return "\n".join(lines)


def describe_languages(catalog: dict[str, Voice]) -> str:
    counts = languages(catalog)
    lines = ["", f"{len(counts)} languages available:", ""]
    for name, n in counts.items():
        lines.append(f"  {name:<38}{n:>4} voice(s)")
    lines += ["", "  Filter with: hermes-voice voices --lang <code>", ""]
    return "\n".join(lines)
