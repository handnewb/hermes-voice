"""Configuracao do loop de voz. Carrega .env sem depender de python-dotenv."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PKG = Path(__file__).resolve().parent
PACKAGED_PERSONA = PKG / "data" / "persona.md"


def _data_root() -> Path:
    """Onde vozes e modelos vivem.

    Num checkout do repositorio, a raiz do projeto. Instalado por pip, um
    diretorio no home do usuario -- escrever dentro de site-packages e errado.
    """
    for parent in (PKG.parent.parent, PKG.parent):
        if (parent / "pyproject.toml").exists():
            return parent
    env = os.environ.get("HERMES_VOICE_HOME", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".hermes-voice"


ROOT = _data_root()


def load_dotenv(path: Path | None = None) -> None:
    """Le um .env simples (KEY=VALUE) e popula os.environ sem sobrescrever."""
    path = path or (ROOT / ".env")
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def _env(key: str, default: str) -> str:
    value = os.environ.get(key, "").strip()
    return value or default


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


def _env_opt_float(key: str) -> float | None:
    """None quando nao definido, para distinguir de zero explicito."""
    raw = os.environ.get(key, "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _env_bool(key: str, default: bool) -> bool:
    return _env(key, "1" if default else "0").lower() in {"1", "true", "yes", "sim", "on"}


@dataclass(slots=True)
class Config:
    # --- Hermes (LLM) ---
    hermes_url: str = "http://127.0.0.1:8080/v1/chat/completions"
    hermes_model: str = "hermes"
    hermes_api_key: str = ""
    hermes_timeout: float = 60.0
    history_turns: int = 8

    # --- STT ---
    whisper_model: str = "large-v3-turbo"
    whisper_device: str = "cuda"
    whisper_compute: str = "int8_float16"
    whisper_language: str = "pt"
    whisper_hint: str = ""

    # --- TTS: somente engines locais, sem chave nem cadastro ---
    tts_backend: str = "auto"  # auto | kokoro | piper-python | piper-binary | none
    voice: str = ""  # id do catalogo; vazio = padrao da engine
    data_dir: str = ""  # onde vozes e modelos vivem

    piper_model: str = ""
    piper_binary: str = ""
    kokoro_model: str = ""
    kokoro_voices: str = ""
    kokoro_voice: str = "pm_alex"
    kokoro_speed: float = 0.95

    # --- DSP de presenca ---
    dsp_preset: str = "off"  # off | room | close | hall | intercom
    dsp_reverb_mix: float | None = None
    dsp_presence_gain_db: float | None = None
    dsp_comp_ratio: float | None = None
    dsp_output_gain_db: float | None = None

    # --- Audio ---
    input_device: str = ""
    output_device: str = ""
    sample_rate: int = 16000  # exigido pelo Whisper
    max_record_seconds: float = 45.0

    # --- Wake word: openWakeWord, sem conta ---
    wake_backend: str = "auto"  # auto | open | none
    wake_model: str = "hey_jarvis"
    wake_model_path: str = ""
    wake_threshold: float = 0.5
    wake_auto_download: bool = True
    # Modo keyword: palavra arbitraria via transcricao. Ver SECURITY.md.
    wake_words: str = "jarvis"
    wake_keyword_model: str = "tiny"
    wake_keyword_device: str = "cpu"
    wake_tolerance: int = -1  # -1 = automatico por tamanho da palavra

    # --- VAD / fim de fala ---
    vad_backend: str = "auto"  # auto | silero | energy
    vad_model: str = ""
    vad_threshold: float = 0.5
    vad_energy_threshold: float = 0.02
    silence_ms: int = 700
    min_speech_ms: int = 200
    follow_up_seconds: float = 20.0
    max_utterance_seconds: float = 30.0
    half_duplex: bool = True

    # --- Fluidez ---
    adaptive_endpoint: bool = True
    endpoint_short_ms: int = 380
    endpoint_long_ms: int = 1250
    endpoint_max_probes: int = 2
    normalize_text: bool = True
    echo_margin_db: float = 7.0
    echo_trigger_frames: int = 3

    # --- Interacao ---
    ptt_key: str = "f9"
    quit_key: str = "esc"
    persona_file: str = str(PACKAGED_PERSONA)
    log_transcripts: bool = False

    extra: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> Config:
        load_dotenv()
        d = cls()
        d.hermes_url = _env("HERMES_URL", d.hermes_url)
        d.hermes_model = _env("HERMES_MODEL", d.hermes_model)
        d.hermes_api_key = _env("HERMES_API_KEY", d.hermes_api_key)
        d.hermes_timeout = _env_float("HERMES_TIMEOUT", d.hermes_timeout)
        d.history_turns = _env_int("HISTORY_TURNS", d.history_turns)

        d.whisper_model = _env("WHISPER_MODEL", d.whisper_model)
        d.whisper_device = _env("WHISPER_DEVICE", d.whisper_device)
        d.whisper_compute = _env("WHISPER_COMPUTE", d.whisper_compute)
        d.whisper_language = _env("WHISPER_LANGUAGE", d.whisper_language)
        d.whisper_hint = _env("WHISPER_HINT", d.whisper_hint)

        d.tts_backend = _env("TTS_BACKEND", d.tts_backend).lower()
        d.voice = _env("VOICE", d.voice)
        d.data_dir = _env("DATA_DIR", d.data_dir)
        d.piper_model = _env("PIPER_MODEL", d.piper_model)
        d.piper_binary = _env("PIPER_BINARY", d.piper_binary)
        d.kokoro_model = _env("KOKORO_MODEL", d.kokoro_model)
        d.kokoro_voices = _env("KOKORO_VOICES", d.kokoro_voices)
        d.kokoro_voice = _env("KOKORO_VOICE", d.kokoro_voice)
        d.kokoro_speed = _env_float("KOKORO_SPEED", d.kokoro_speed)

        d.dsp_preset = _env("DSP_PRESET", d.dsp_preset).lower()
        d.dsp_reverb_mix = _env_opt_float("DSP_REVERB_MIX")
        d.dsp_presence_gain_db = _env_opt_float("DSP_PRESENCE_GAIN_DB")
        d.dsp_comp_ratio = _env_opt_float("DSP_COMP_RATIO")
        d.dsp_output_gain_db = _env_opt_float("DSP_OUTPUT_GAIN_DB")

        d.input_device = _env("INPUT_DEVICE", d.input_device)
        d.output_device = _env("OUTPUT_DEVICE", d.output_device)
        d.max_record_seconds = _env_float("MAX_RECORD_SECONDS", d.max_record_seconds)

        d.wake_backend = _env("WAKE_BACKEND", d.wake_backend).lower()
        d.wake_model = _env("WAKE_MODEL", d.wake_model)
        d.wake_model_path = _env("WAKE_MODEL_PATH", d.wake_model_path)
        d.wake_threshold = _env_float("WAKE_THRESHOLD", d.wake_threshold)
        d.wake_auto_download = _env_bool("WAKE_AUTO_DOWNLOAD", d.wake_auto_download)
        d.wake_words = _env("WAKE_WORDS", d.wake_words)
        d.wake_keyword_model = _env("WAKE_KEYWORD_MODEL", d.wake_keyword_model)
        d.wake_keyword_device = _env("WAKE_KEYWORD_DEVICE", d.wake_keyword_device)
        d.wake_tolerance = _env_int("WAKE_TOLERANCE", d.wake_tolerance)

        d.vad_backend = _env("VAD_BACKEND", d.vad_backend).lower()
        d.vad_model = _env("VAD_MODEL", d.vad_model)
        d.vad_threshold = _env_float("VAD_THRESHOLD", d.vad_threshold)
        d.vad_energy_threshold = _env_float("VAD_ENERGY_THRESHOLD", d.vad_energy_threshold)
        d.silence_ms = _env_int("SILENCE_MS", d.silence_ms)
        d.min_speech_ms = _env_int("MIN_SPEECH_MS", d.min_speech_ms)
        d.follow_up_seconds = _env_float("FOLLOW_UP_SECONDS", d.follow_up_seconds)
        d.max_utterance_seconds = _env_float("MAX_UTTERANCE_SECONDS", d.max_utterance_seconds)
        d.half_duplex = _env_bool("HALF_DUPLEX", d.half_duplex)

        d.adaptive_endpoint = _env_bool("ADAPTIVE_ENDPOINT", d.adaptive_endpoint)
        d.endpoint_short_ms = _env_int("ENDPOINT_SHORT_MS", d.endpoint_short_ms)
        d.endpoint_long_ms = _env_int("ENDPOINT_LONG_MS", d.endpoint_long_ms)
        d.endpoint_max_probes = _env_int("ENDPOINT_MAX_PROBES", d.endpoint_max_probes)
        d.normalize_text = _env_bool("NORMALIZE_TEXT", d.normalize_text)
        d.echo_margin_db = _env_float("ECHO_MARGIN_DB", d.echo_margin_db)
        d.echo_trigger_frames = _env_int("ECHO_TRIGGER_FRAMES", d.echo_trigger_frames)

        d.ptt_key = _env("PTT_KEY", d.ptt_key).lower()
        d.quit_key = _env("QUIT_KEY", d.quit_key).lower()
        d.persona_file = _env("PERSONA_FILE", d.persona_file)
        d.log_transcripts = _env_bool("LOG_TRANSCRIPTS", d.log_transcripts)
        d.resolve_paths()
        return d

    # Unico segredo que resta no projeto: nao ha chave de TTS nem de wake word,
    # porque todas as engines rodam locais.
    SECRET_FIELDS = ("hermes_api_key",)

    def redacted(self) -> dict:
        """Config segura para log, --doctor e relatorio de bug."""
        out = {}
        for name in self.__slots__:
            if name == "extra":
                continue
            value = getattr(self, name)
            if name in self.SECRET_FIELDS:
                value = f"<definida: {len(value)} chars>" if value else "<vazia>"
            out[name] = value
        return out

    def resolve_paths(self) -> None:
        """Preenche caminhos de modelo a partir do id da voz e do data_dir.

        Deixa o .env enxuto: normalmente basta VOICE=<id>.
        """
        from .voices import DEFAULT_VOICE, KOKORO_LANGS

        root = Path(self.data_dir) if self.data_dir else ROOT
        self.data_dir = str(root)

        voice_id = self.voice or DEFAULT_VOICE
        self.voice = voice_id

        # Vozes do Kokoro tem prefixo de idioma+genero e nao contem hifen.
        is_kokoro = (
            len(voice_id) > 3
            and voice_id[0] in KOKORO_LANGS
            and voice_id[1] in "fm"
            and voice_id[2] == "_"
        )
        if is_kokoro:
            self.kokoro_voice = voice_id
            if self.tts_backend == "auto":
                self.tts_backend = "kokoro"
        elif not self.piper_model:
            self.piper_model = str(root / "voices" / f"{voice_id}.onnx")

        if not self.piper_model:
            self.piper_model = str(root / "voices" / f"{DEFAULT_VOICE}.onnx")
        if not self.piper_binary:
            exe = "piper.exe" if os.name == "nt" else "piper"
            self.piper_binary = str(root / "bin" / "piper" / exe)
        if not self.kokoro_model:
            self.kokoro_model = str(root / "models" / "kokoro-v1.0.onnx")
        if not self.kokoro_voices:
            self.kokoro_voices = str(root / "models" / "voices-v1.0.bin")
        if not self.vad_model:
            candidate = root / "models" / "silero_vad.onnx"
            if candidate.exists():
                self.vad_model = str(candidate)

    def persona(self) -> str:
        path = Path(self.persona_file)
        if not path.exists() and PACKAGED_PERSONA.exists():
            path = PACKAGED_PERSONA
        if not path.exists():
            return (
                "Voce e o Hermes, assistente pessoal por voz. Trate o usuario como "
                "'senhor'. Responda em no maximo 2 frases, sem listas nem markdown."
            )
        text = path.read_text(encoding="utf-8")
        # Remove o cabecalho de documentacao, mantendo apenas as diretrizes.
        # rsplit e nao split: o cabecalho pode citar o marcador ao se explicar.
        marker = "<!-- PROMPT-BEGIN -->"
        if marker in text:
            text = text.rsplit(marker, 1)[1]
        return text.strip()
