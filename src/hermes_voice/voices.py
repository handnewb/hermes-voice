"""Catalogo de vozes: indice publico do Piper (35 idiomas) e Kokoro (9 idiomas).

Duas fontes, duas naturezas:

  Piper   -- catalogo comunitario com centenas de vozes em 35 idiomas. Nao
             fixamos uma lista aqui: consultamos o voices.json publicado no
             Hugging Face em tempo de execucao, com verificacao de MD5 vinda do
             proprio indice. Voz nova no upstream aparece sem release nosso.

  Kokoro  -- um unico arquivo de pesos com 54 vozes embutidas, 9 idiomas. Lista
             estatica porque nao ha o que descobrir: ou o arquivo esta ali, ou
             nao esta.

Nada aqui exige conta, chave de API ou aceitar termos. Todo download e de fonte
publica, com licenca declarada.
"""

from __future__ import annotations

import hashlib
import json
import logging
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
# Kokoro: 54 vozes em 9 idiomas, num unico arquivo de pesos.
# Prefixo: 1a letra = idioma, 2a = genero (f/m).
# ---------------------------------------------------------------------------
KOKORO_LANGS = {
    "a": ("en_US", "Ingles americano"),
    "b": ("en_GB", "Ingles britanico"),
    "e": ("es", "Espanhol"),
    "f": ("fr_FR", "Frances"),
    "h": ("hi", "Hindi"),
    "i": ("it", "Italiano"),
    "j": ("ja", "Japones"),
    "p": ("pt_BR", "Portugues do Brasil"),
    "z": ("zh", "Mandarim"),
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
# Indice do Piper
# ---------------------------------------------------------------------------
def _cache_path(root: Path) -> Path:
    return root / INDEX_CACHE


def fetch_piper_index(root: Path, refresh: bool = False) -> dict:
    """Baixa e cacheia o voices.json. Cache de 7 dias."""
    cache = _cache_path(root)
    fresco = cache.exists() and time.time() - cache.stat().st_mtime < INDEX_MAX_AGE_S
    if not refresh and fresco:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            log.warning("Cache do indice corrompido; rebaixando.")

    log.info("Buscando indice de vozes do Piper...")
    try:
        req = urllib.request.Request(PIPER_INDEX_URL, headers={"User-Agent": "hermes-voice"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        if cache.exists():
            log.warning("Indice inacessivel (%s); usando cache antigo.", exc)
            return json.loads(cache.read_text(encoding="utf-8"))
        raise DownloadError(
            f"Nao consegui buscar o indice de vozes ({exc}). "
            "Verifique a conexao; nenhuma conta e necessaria."
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
        notes=f"{speakers} locutores" if speakers > 1 else "",
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
            gender="feminina" if vid[1] == "f" else "masculina",
            quality="alta",
            license="Apache-2.0",
            commercial=True,
            notes="pesos compartilhados entre todas as vozes Kokoro",
            assets=shared,
            voice_arg=vid,
        )
    return out


def full_catalog(root: Path, refresh: bool = False, include_piper: bool = True) -> dict[str, Voice]:
    """Kokoro sempre; Piper quando o indice estiver acessivel."""
    catalog = kokoro_catalog()
    if include_piper:
        try:
            catalog.update(piper_catalog(root, refresh))
        except DownloadError as exc:
            log.warning("Catalogo do Piper indisponivel: %s", exc)
    return catalog


def search(
    catalog: dict[str, Voice], lang: str = "", gender: str = "", engine: str = "", quality: str = ""
) -> list[Voice]:
    """Filtra por idioma (prefixo: 'pt' pega pt_BR e pt_PT), genero, engine."""
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
        chave = f"{v.language}  {v.language_name}"
        counts[chave] = counts.get(chave, 0) + 1
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
        print(f"  baixando {dest.name}{size}...", flush=True)
    try:
        req = urllib.request.Request(asset.url, headers={"User-Agent": "hermes-voice"})
        with urllib.request.urlopen(req, timeout=120) as r, tmp.open("wb") as fh:
            shutil.copyfileobj(r, fh, length=1 << 20)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        tmp.unlink(missing_ok=True)
        raise DownloadError(f"Falha ao baixar {asset.url}: {exc}") from exc

    if asset.md5:
        digest = hashlib.md5(tmp.read_bytes(), usedforsecurity=False).hexdigest()
        if digest != asset.md5:
            tmp.unlink(missing_ok=True)
            raise DownloadError(
                f"MD5 divergente em {dest.name}: indice diz {asset.md5[:12]}, "
                f"o arquivo baixado da {digest[:12]}"
            )
    tmp.replace(dest)
    if dest.suffix in {".zip", ".gz"}:
        _extract(dest)
    return dest


def _verify(path: Path, asset: Asset) -> bool:
    """Tamanho e MD5 quando o indice fornece. Sem eles, presenca basta."""
    if asset.size_bytes and path.stat().st_size != asset.size_bytes:
        log.warning("%s com tamanho inesperado; rebaixando.", path.name)
        return False
    if asset.md5:
        digest = hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()
        if digest != asset.md5:
            log.warning("%s com MD5 divergente; rebaixando.", path.name)
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
                tf.extractall(target, filter="data")  # evita path traversal
            except TypeError:  # Python < 3.12
                tf.extractall(target)
    archive.unlink(missing_ok=True)
    for exe in target.rglob("piper"):
        if exe.is_file():
            exe.chmod(0o755)


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
# Apresentacao
# ---------------------------------------------------------------------------
def describe(catalog: dict[str, Voice], root: Path, lang: str = "", limit: int = 40) -> str:
    hits = search(catalog, lang=lang)
    linhas = [""]
    if lang:
        linhas.append(f"Vozes para '{lang}': {len(hits)} encontradas.")
    else:
        linhas.append(
            f"{len(catalog)} vozes em {len(languages(catalog))} idiomas. Filtre com --lang."
        )
    linhas += [
        "",
        f"  {'ID':<30}{'IDIOMA':<9}{'ENGINE':<9}{'GENERO':<11}{'LIC.':<12}INSTALADA",
        "  " + "-" * 84,
    ]
    for v in hits[:limit]:
        marca = "sim" if is_installed(v, root) else "nao"
        padrao = "  <- padrao" if v.id == DEFAULT_VOICE else ""
        linhas.append(
            f"  {v.id:<30}{v.language:<9}{v.engine:<9}{v.gender:<11}{v.license:<12}{marca}{padrao}"
        )
    if len(hits) > limit:
        linhas.append(f"  ... e {len(hits) - limit} outras. Filtre com --lang.")
    linhas += [
        "",
        "  Instalar:  hermes-voice voices --install <ID>",
        "  Idiomas:   hermes-voice voices --languages",
        "  Usar:      hermes-voice --voice <ID>",
        "",
        "  Piper e MIT, Kokoro e Apache-2.0: as duas permitem uso comercial.",
        "  Sobre clonagem de voz e direitos: docs/VOICE_LICENSING.md",
        "",
    ]
    return "\n".join(linhas)


def describe_languages(catalog: dict[str, Voice]) -> str:
    counts = languages(catalog)
    linhas = ["", f"{len(counts)} idiomas disponiveis:", ""]
    for nome, n in counts.items():
        linhas.append(f"  {nome:<38}{n:>4} voz(es)")
    linhas += ["", "  Filtre com: hermes-voice voices --lang <codigo>", ""]
    return "\n".join(linhas)
