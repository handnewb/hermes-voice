"""Ponto de entrada do CLI."""

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
        description="Interface de voz conversacional em pt-BR para o Hermes Agent.",
        epilog="Comece por: hermes-voice --doctor",
    )
    p.add_argument("--version", action="version", version=f"hermes-voice {__version__}")
    p.add_argument(
        "--doctor", action="store_true", help="diagnostica ambiente, dispositivos, modelos e chaves"
    )
    p.add_argument(
        "--probe",
        action="store_true",
        help="com --doctor, tenta alcancar o endpoint do Hermes de verdade",
    )
    p.add_argument("--devices", action="store_true", help="lista dispositivos de audio")
    p.add_argument("--voice", metavar="ID", help="voz do catalogo (ver: hermes-voice voices)")
    p.add_argument("--text", action="store_true", help="entrada por teclado, sem microfone")
    p.add_argument("--no-tts", action="store_true", help="nao sintetiza voz")
    p.add_argument(
        "--trigger",
        choices=["wake", "console", "ptt"],
        default="wake",
        help="wake = microfone aberto com palavra de ativacao (default); "
        "console = ENTER, sem hook de teclado; "
        "ptt = segure uma tecla, instala hook global",
    )
    p.add_argument(
        "--dsp", metavar="PRESET", help="sobrepoe DSP_PRESET: off, room, close, hall, intercom"
    )
    p.add_argument(
        "--tts",
        metavar="BACKEND",
        help="sobrepoe TTS_BACKEND: kokoro, piper-python, piper-binary, none",
    )
    p.add_argument("--verbose", "-v", action="store_true")

    sub = p.add_subparsers(dest="command")
    v = sub.add_parser("voices", help="lista, instala e remove vozes")
    v.add_argument("--install", metavar="ID", help="baixa uma voz do catalogo")
    v.add_argument("--lang", metavar="CODIGO", help="filtra por idioma: pt, en, es, zh...")
    v.add_argument("--languages", action="store_true", help="lista os idiomas")
    v.add_argument("--refresh", action="store_true", help="rebusca o indice do Piper")
    v.add_argument("--force", action="store_true", help="rebaixa mesmo se existir")
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
                "Seguindo sem voz. Rode 'hermes-voice --doctor' para ver o motivo."
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
        print(describe(catalog, root, lang=args.lang or ""))
        return 0

    voice = catalog.get(args.install)
    if voice is None:
        print(f"\nVoz '{args.install}' nao existe no catalogo.")
        print(describe(catalog, root, lang=args.lang or ""))
        return 1

    print(f"\nInstalando {voice.id} ({voice.engine}, {voice.language}, {voice.license}) em {root}")
    try:
        install_support(root, args.force)
        install_voice(voice, root, args.force)
    except DownloadError as exc:
        print(f"\nFalhou: {exc}")
        print("Verifique a conexao. Nenhuma conta ou chave e necessaria.")
        return 1
    print(f"\nPronto. Use com: hermes-voice --voice {voice.id}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
