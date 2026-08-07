"""Os tres loops de interacao: wake word, console e push-to-talk.

Todos convergem em process_utterance(), para que nao exista divergencia de
comportamento entre modos de gatilho.
"""

from __future__ import annotations

import logging
import time

import numpy as np

from .config import Config
from .llm import HermesClient, SentenceChunker, clean_for_speech
from .normalize import normalize

log = logging.getLogger("hermes.loop")

from .ui import BOLD, DIM, RESET  # noqa: E402

SILENCE_PEAK = 0.012  # abaixo disso, tratamos como microfone mudo


# ---------------------------------------------------------------------------
# Turno: STT -> Hermes -> TTS, com pipeline por sentenca
# ---------------------------------------------------------------------------
def _for_speech(piece: str, cfg: Config | None) -> str:
    """Limpa markdown e normaliza numeros antes de sintetizar."""
    spoken = clean_for_speech(piece)
    if cfg is None or cfg.normalize_text:
        spoken = normalize(spoken)
    return spoken


def handle_turn(text: str, client: HermesClient, speaker=None, cfg: Config | None = None) -> str:
    chunker = SentenceChunker()
    t0 = time.perf_counter()
    first_audio: float | None = None
    printed = False

    if speaker:
        speaker.begin_turn()

    print(f"{BOLD}Hermes:{RESET} ", end="", flush=True)
    try:
        for delta in client.stream(text):
            print(delta, end="", flush=True)
            printed = True
            for piece in chunker.feed(delta):
                spoken = _for_speech(piece, cfg)
                if spoken and speaker:
                    if first_audio is None:
                        first_audio = (time.perf_counter() - t0) * 1000
                    speaker.say(spoken)
        for piece in chunker.flush():
            spoken = _for_speech(piece, cfg)
            if spoken and speaker:
                if first_audio is None:
                    first_audio = (time.perf_counter() - t0) * 1000
                speaker.say(spoken)
    except RuntimeError as exc:
        print()
        log.error("%s", exc)
        if speaker:
            speaker.say("Nao consegui alcancar o servico, senhor.")
            speaker.end_turn()
        return ""
    finally:
        if not printed:
            print(f"{DIM}(resposta vazia){RESET}", end="")
        print()

    if speaker:
        speaker.end_turn()
    if first_audio is not None:
        log.info("Primeiro audio em %.0f ms.", first_audio)
    return "ok"


# ---------------------------------------------------------------------------
# Modo texto (util para validar Hermes + TTS sem microfone)
# ---------------------------------------------------------------------------
def run_text_mode(cfg: Config, speaker) -> None:
    client = HermesClient(
        cfg.hermes_url,
        cfg.hermes_model,
        cfg.hermes_api_key,
        cfg.hermes_timeout,
        cfg.persona(),
        cfg.history_turns,
    )
    print(f"\n{BOLD}Modo texto.{RESET} Ctrl+C para sair.\n")
    try:
        while True:
            try:
                text = input(f"{BOLD}Voce:{RESET} ").strip()
            except EOFError:
                return
            if not text:
                continue
            if text.lower() in {"/sair", "/quit", "/exit"}:
                return
            if text.lower() == "/reset":
                client.reset()
                print(f"{DIM}Historico limpo.{RESET}")
                continue
            handle_turn(text, client, speaker, cfg)
            if speaker:
                speaker.wait_until_idle(timeout=90)
    except KeyboardInterrupt:
        print()
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Modo voz (push-to-talk)
# ---------------------------------------------------------------------------
def parse_key(name: str):
    from pynput import keyboard

    name = (name or "").strip().lower()
    special = getattr(keyboard.Key, name, None)
    if special is not None:
        return special
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    raise ValueError(f"Tecla desconhecida: '{name}'")


def process_utterance(pcm, peak, stt, client, cfg: Config, speaker, strip=None) -> None:
    """STT + turno, compartilhado pelos tres modos de gatilho."""
    secs = pcm.size / stt.sample_rate
    if secs < 0.25:
        print(f"{DIM}(muito curto){RESET}")
        return
    if peak < SILENCE_PEAK:
        print(f"{DIM}(sem sinal no microfone -- pico {peak:.4f}){RESET}")
        return

    t0 = time.perf_counter()
    text = stt.transcribe(pcm)
    log.info("STT: %.1f s de audio em %.0f ms.", secs, (time.perf_counter() - t0) * 1000)
    if strip is not None:
        text = strip(text)
    if not text:
        print(f"{DIM}(nao entendi){RESET}")
        return

    print(f"{BOLD}Voce:{RESET} {text}")
    if cfg.log_transcripts:
        _append_transcript(text)
    handle_turn(text, client, speaker)


def _build_stack(cfg: Config):
    from .stt import Transcriber

    print(f"{DIM}Carregando Whisper '{cfg.whisper_model}'...{RESET}")
    stt = Transcriber(
        cfg.whisper_model,
        cfg.whisper_device,
        cfg.whisper_compute,
        cfg.whisper_language,
        cfg.whisper_hint,
    )
    stt.warmup()
    client = HermesClient(
        cfg.hermes_url,
        cfg.hermes_model,
        cfg.hermes_api_key,
        cfg.hermes_timeout,
        cfg.persona(),
        cfg.history_turns,
    )
    return stt, client


# ---------------------------------------------------------------------------
# Gatilho por console: sem hook global de teclado.
#
# Por que existe: um hook global (SetWindowsHookEx) e a assinatura classica de
# keylogger. Combinado com captura de microfone e egress de rede, forma a triade
# comportamental exata de um implante de spyware -- o que a engine de
# engine de EDR comportamental existe para detectar. Este modo exige foco no
# console e nao instala hook nenhum, eliminando o componente de maior risco.
# ---------------------------------------------------------------------------
def run_console_mode(cfg: Config, speaker, no_tts: bool) -> None:
    from .audio import Recorder

    stt, client = _build_stack(cfg)
    spk = None if no_tts else speaker

    with Recorder(stt.sample_rate, cfg.input_device, cfg.max_record_seconds) as recorder:
        print(
            f"\n{BOLD}Hermes pronto{RESET} (modo console, sem hook de teclado)\n"
            f"  ENTER inicia a gravacao, ENTER novamente envia.\n"
            f"  /reset limpa o historico, /sair encerra.\n"
        )
        try:
            while True:
                cmd = input(f"{BOLD}[ENTER] falar >{RESET} ").strip().lower()
                if cmd in {"/sair", "/quit", "/exit"}:
                    return
                if cmd == "/reset":
                    client.reset()
                    print(f"{DIM}Historico limpo.{RESET}")
                    continue
                if spk and spk.speaking:
                    spk.interrupt()

                recorder.start()
                input(f"{BOLD}>> gravando... [ENTER] envia{RESET}")
                pcm, peak = recorder.stop()
                process_utterance(pcm, peak, stt, client, cfg, spk)
                if spk:
                    spk.wait_until_idle(timeout=90)
        except (KeyboardInterrupt, EOFError):
            print()
        finally:
            client.close()
    print("Encerrado.")


def run_voice_mode(cfg: Config, speaker, no_tts: bool) -> None:
    from pynput import keyboard

    from .audio import Recorder

    ptt = parse_key(cfg.ptt_key)
    quit_key = parse_key(cfg.quit_key)
    stt, client = _build_stack(cfg)
    spk = None if no_tts else speaker
    state = {"running": True}

    def on_press(key) -> None:
        if key == ptt and not recorder.recording:
            if spk and spk.speaking:
                spk.interrupt()  # barge-in: nova fala corta a anterior
                print(f"\n{DIM}[interrompido]{RESET}")
            recorder.start()
            print(f"\r{BOLD}>> gravando...{RESET}  ", end="", flush=True)

    def on_release(key) -> None:
        if key == quit_key:
            state["running"] = False
            return False
        if key != ptt or not recorder.recording:
            return None
        pcm, peak = recorder.stop()
        print(f"\r{' ' * 40}\r", end="")
        process_utterance(pcm, peak, stt, client, cfg, spk)
        return None

    with Recorder(stt.sample_rate, cfg.input_device, cfg.max_record_seconds) as recorder:
        print(
            f"\n{BOLD}Hermes em escuta.{RESET}\n"
            f"  Segure {BOLD}{cfg.ptt_key.upper()}{RESET} para falar, solte para enviar.\n"
            f"  {cfg.ptt_key.upper()} durante a resposta interrompe.\n"
            f"  {cfg.quit_key.upper()} para encerrar.\n"
        )
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        try:
            while state["running"] and listener.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            listener.stop()
            client.close()
    print("\nEncerrado.")


def _append_transcript(text: str) -> None:
    from pathlib import Path

    path = Path.cwd() / "transcripts.log"
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {text}\n")


# ---------------------------------------------------------------------------
# Modo wake word: microfone aberto, conversa contínua.
#
# A palavra "Jarvis" abre uma sessao. Dentro dela voce fala normalmente, sem
# repetir a palavra. A sessao fecha sozinha depois de FOLLOW_UP_SECONDS sem fala.
# ---------------------------------------------------------------------------
def run_wake_mode(cfg: Config, speaker, no_tts: bool) -> None:
    import threading

    from .audio import FrameSource
    from .echo import build_echo
    from .endpoint import Completeness, EndpointConfig, Endpointer
    from .session import Session, State, strip_wake_word
    from .vad import FRAME, SpeechGate, build_vad
    from .wake import FrameAdapter, build_wake

    backend = build_wake(cfg)
    if backend is None:
        log.error(
            "Sem detector de palavra de ativacao. Instale com "
            "pip install 'hermes-voice[wake]', ou use --trigger console."
        )
        return

    wake = FrameAdapter(backend)
    vad = build_vad(cfg)
    stt, client = _build_stack(cfg)
    spk = None if no_tts else speaker

    frame_ms = int(FRAME * 1000 / stt.sample_rate)  # 512 @ 16 kHz = 32 ms

    # Com endpointing adaptativo o gate encerra no limiar CURTO; quem decide se
    # a fala realmente acabou e o Endpointer, olhando a sintaxe do transcrito.
    gate_silence = cfg.endpoint_short_ms if cfg.adaptive_endpoint else cfg.silence_ms
    gate = SpeechGate(cfg.vad_threshold, gate_silence, cfg.min_speech_ms, frame_ms)
    sess = Session(stt.sample_rate, frame_ms, cfg.follow_up_seconds, cfg.max_utterance_seconds)

    endpointer = (
        Endpointer(
            EndpointConfig(
                short_ms=cfg.endpoint_short_ms,
                normal_ms=cfg.silence_ms,
                long_ms=cfg.endpoint_long_ms,
                max_probes=cfg.endpoint_max_probes,
            )
        )
        if cfg.adaptive_endpoint
        else None
    )
    echo = build_echo(cfg, stt.sample_rate, FRAME)
    if echo is not None and spk is not None:
        spk.set_echo(echo)
    hold_frames = 0

    turn_done = threading.Event()
    turn_done.set()

    def run_turn(pcm, peak) -> None:
        try:
            process_utterance(pcm, peak, stt, client, cfg, spk, strip=strip_wake_word)
        finally:
            turn_done.set()

    def show(extra: str = "") -> None:
        print(f"\r{' ' * 60}\r{DIM}[{sess.banner()}]{RESET} {extra}", end="", flush=True)

    with FrameSource(stt.sample_rate, cfg.input_device, FRAME) as mic:
        print(
            f"\n{BOLD}Hermes em escuta contínua.{RESET}\n"
            f'  Diga {BOLD}"Jarvis"{RESET} e fale em seguida.\n'
            f"  Depois da resposta a sessao fica aberta {cfg.follow_up_seconds:.0f}s: "
            f"pode falar sem repetir a palavra.\n"
            f"  Silencio de {cfg.silence_ms} ms encerra sua fala. "
            f"Ctrl+C para sair.\n"
        )
        show()
        try:
            while True:
                frame = mic.read(timeout=0.3)
                if frame is None:
                    if sess.follow_up_expired:
                        sess.to(State.DORMANT)
                        gate.reset()
                        show()
                    continue

                st = sess.state

                # ---- DORMANT: so o detector roda. Nada e transcrito. --------
                if st == State.DORMANT:
                    sess.keep_preroll(frame)
                    if wake.feed(_to_int16(frame)):
                        print(f"\r{' ' * 60}\r{BOLD}>> Jarvis{RESET}")
                        gate.reset()
                        vad.reset()
                        sess.begin_utterance(include_preroll=True)
                        sess.to(State.LISTENING)
                        show()
                    continue

                # ---- SPEAKING: aguarda o audio terminar ---------------------
                if st == State.SPEAKING:
                    if not cfg.half_duplex:
                        # Barge-in: palavra de ativacao, ou fala que a supressao
                        # de eco confirma nao ser o proprio alto-falante.
                        by_wake = wake.feed(_to_int16(frame))
                        by_voice = echo is not None and echo.is_user_speech(frame)
                        if by_wake or by_voice:
                            if spk:
                                spk.interrupt()
                            if echo is not None:
                                echo.clear()
                            gate.reset()
                            vad.reset()
                            sess.begin_utterance(include_preroll=False)
                            sess.to(State.LISTENING)
                            print(f"\n{DIM}[interrompido]{RESET}")
                            show()
                            continue
                    if spk is None or not spk.speaking:
                        sess.to(State.FOLLOW_UP)
                        gate.reset()
                        show()
                    continue

                # ---- THINKING: descarta audio ------------------------------
                if st == State.THINKING:
                    if turn_done.is_set():
                        mic.drain()
                        sess.to(State.SPEAKING if spk and spk.speaking else State.FOLLOW_UP)
                        gate.reset()
                        show()
                    continue

                # ---- FOLLOW_UP: fala reabre sem palavra de ativacao --------
                if st == State.FOLLOW_UP:
                    sess.keep_preroll(frame)
                    if gate.update(vad.prob(frame)) == "start":
                        sess.begin_utterance(include_preroll=True)
                        sess.to(State.LISTENING)
                        show()
                    elif sess.follow_up_expired:
                        sess.to(State.DORMANT)
                        gate.reset()
                        show()
                    continue

                # ---- LISTENING: acumula até o fim da fala -------------------
                sess.append(frame)
                event = gate.update(vad.prob(frame))

                # Espera estendida concedida pelo Endpointer: a frase parecia
                # pendurada, entao ignoramos este "end" e seguimos escutando.
                if event == "end" and hold_frames > 0:
                    hold_frames -= 1
                    gate.reset()
                    continue

                # Sondagem: transcreve o que ha e pergunta se a frase terminou.
                if event == "end" and endpointer is not None and endpointer.should_probe():
                    pcm_probe, _ = sess.peek()
                    parcial = stt.transcribe(pcm_probe)
                    if endpointer.decide(parcial) is not Completeness.COMPLETE:
                        hold_frames = max(1, endpointer.extra_ms // frame_ms)
                        gate.reset()
                        show(f"{DIM}(continue...){RESET}")
                        continue

                if event == "end" or sess.overlong:
                    pcm, peak = sess.take()
                    print(f"\r{' ' * 60}\r", end="")
                    sess.to(State.THINKING)
                    if endpointer is not None:
                        endpointer.reset()
                    hold_frames = 0
                    turn_done.clear()
                    threading.Thread(target=run_turn, args=(pcm, peak), daemon=True).start()
                    show()

        except KeyboardInterrupt:
            print()
        finally:
            sess.discard()
            wake.close()
            client.close()
            if mic.dropped:
                log.debug("%d frames descartados por fila cheia.", mic.dropped)
    print("Encerrado.")


def _to_int16(frame_float32) -> np.ndarray:
    return (np.clip(frame_float32, -1.0, 1.0) * 32767.0).astype(np.int16)
