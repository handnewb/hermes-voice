"""CLI entry point."""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__
from .config import Config
from .ui import DIM, RESET


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hermes-voice",
        description="Conversational voice interface in Brazilian Portuguese for Hermes Agent.",
        epilog="Start with: hermes-voice --doctor",
    )
    p.add_argument("--version", action="version", version=f"hermes-voice {__version__}")
    p.add_argument(
        "--doctor", action="store_true", help="diagnose environment, devices, models and keys"
    )
    p.add_argument(
        "--probe",
        action="store_true",
        help="with --doctor, try reaching the Hermes endpoint for real",
    )
    p.add_argument("--devices", action="store_true", help="list audio devices")
    p.add_argument("--voice", metavar="ID", help="catalog voice (see: hermes-voice voices)")
    p.add_argument("--text", action="store_true", help="keyboard input, no microphone")
    p.add_argument("--no-tts", action="store_true", help="do not synthesize voice")
    p.add_argument(
        "--trigger",
        choices=["wake", "console", "ptt"],
        default="wake",
        help="wake = open mic with wake word (default); "
        "console = ENTER, no keyboard hook; "
        "ptt = hold a key, installs global hook",
    )
    p.add_argument(
        "--dsp", metavar="PRESET", help="override DSP_PRESET: off, room, close, hall, intercom"
    )
    p.add_argument(
        "--tts",
        metavar="BACKEND",
        help="override TTS_BACKEND: kokoro, piper-python, piper-binary, none",
    )
    p.add_argument("--verbose", "-v", action="store_true")

    sub = p.add_subparsers(dest="command")
    v = sub.add_parser("voices", help="list, install and remove voices")
    v.add_argument("--install", metavar="ID", help="download a voice from the catalog")
    v.add_argument("--lang", metavar="CODE", help="filter by language: pt, en, es, zh...")
    v.add_argument("--languages", action="store_true", help="list the languages")
    v.add_argument("--refresh", action="store_true", help="re-fetch the Piper index")
    v.add_argument("--force", action="store_true", help="re-download even if it exists")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format=f"{DIM}%(levelname)s %(name)s: %(message)s{RESET}",
    )

    cfg = Config.from_env()
    if args.voice:
        cfg.voice = args.voice
        cfg.tts_backend = "auto"
        cfg.resolve_paths()
    if args.dsp:
        cfg.dsp_preset = args.dsp.lower()
    if args.tts:
        cfg.tts_backend = args.tts.lower()

    if getattr(args, "command", None) == "voices":
        return _voices(cfg, args)

    if args.doctor:
        from .doctor import run

        return run(cfg, probe=args.probe)

    if args.devices:
        from .audio import list_devices

        print(list_devices())
        return 0

    speaker = None
    if not args.no_tts:
        from .tts import build_speaker

        speaker = build_speaker(cfg)
        if speaker is None:
            logging.getLogger("hermes").warning(
                "Proceeding without voice. Run 'hermes-voice --doctor' to see why."
            )

    from .loops import run_console_mode, run_text_mode, run_voice_mode, run_wake_mode

    try:
        if args.text:
            run_text_mode(cfg, speaker)
        elif args.trigger == "console":
            run_console_mode(cfg, speaker, args.no_tts)
        elif args.trigger == "ptt":
            run_voice_mode(cfg, speaker, args.no_tts)
        else:
            run_wake_mode(cfg, speaker, args.no_tts)
    except KeyboardInterrupt:
        print()
    finally:
        if speaker:
            speaker.close()
    return 0


def _voices(cfg: Config, args) -> int:
    from pathlib import Path

    from .voices import (
        DownloadError,
        describe,
        describe_languages,
        full_catalog,
        install_support,
        install_voice,
    )

    root = Path(cfg.data_dir)
    try:
        catalog = full_catalog(root, refresh=args.refresh)
    except DownloadError as exc:
        print(f"\n{exc}\n")
        return 1

    if args.languages:
        print(describe_languages(catalog))
        return 0

    if not args.install:
        print(
            describe(catalog, root, lang=args.lang or "")
        )  # lgtm[py/clear-text-logging-sensitive-data]
        return 0

    voice = catalog.get(args.install)
    if voice is None:
        print(f"\nVoice '{args.install}' doesn't exist in the catalog.")
        print(
            describe(catalog, root, lang=args.lang or "")
        )  # lgtm[py/clear-text-logging-sensitive-data]
        return 1

    print(f"\nInstalling {voice.id} ({voice.engine}, {voice.language}, {voice.license}) to {root}")
    try:
        install_support(root, args.force)
        install_voice(voice, root, args.force)
    except DownloadError as exc:
        print(f"\nFailed: {exc}")
        print("Check your connection. No account or key is required.")
        return 1
    print(f"\nReady. Use with: hermes-voice --voice {voice.id}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
