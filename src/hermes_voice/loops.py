"""The three interaction loops: wake word, console, and push-to-talk.

All converge on process_utterance(), so there is no behavioral divergence
between trigger modes.
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

SILENCE_PEAK = 0.012  # below this, treat as muted microphone


# ---------------------------------------------------------------------------
# Turn: STT -> Hermes -> TTS, with sentence-level pipeline
# ---------------------------------------------------------------------------
def _for_speech(piece: str, cfg: Config | None) -> str:
    """Clean markdown and normalize numbers before synthesizing."""
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
            speaker.say("I could not reach the service, sir.")
            speaker.end_turn()
        return ""
    finally:
        if not printed:
            print(f"{DIM}(empty response){RESET}", end="")
        print()

    if speaker:
        speaker.end_turn()
    if first_audio is not None:
        log.info("First audio in %.0f ms.", first_audio)
    return "ok"


# ---------------------------------------------------------------------------
# Text mode (useful for validating Hermes + TTS without a microphone)
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
    print(f"\n{BOLD}Text mode.{RESET} Ctrl+C to exit.\n")
    try:
        while True:
            try:
                text = input(f"{BOLD}You:{RESET} ").strip()
            except EOFError:
                return
            if not text:
                continue
            if text.lower() in {"/sair", "/quit", "/exit"}:
                return
            if text.lower() == "/reset":
                client.reset()
                print(f"{DIM}History cleared.{RESET}")
                continue
            handle_turn(text, client, speaker, cfg)
            if speaker:
                speaker.wait_until_idle(timeout=90)
    except KeyboardInterrupt:
        print()
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Voice mode (push-to-talk)
# ---------------------------------------------------------------------------
def parse_key(name: str):
    from pynput import keyboard

    name = (name or "").strip().lower()
    special = getattr(keyboard.Key, name, None)
    if special is not None:
        return special
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    raise ValueError(f"Unknown key: '{name}'")


def process_utterance(pcm, peak, stt, client, cfg: Config, speaker, strip=None) -> None:
    """STT + turn, shared by the three trigger modes."""
    secs = pcm.size / stt.sample_rate
    if secs < 0.25:
        print(f"{DIM}(too short){RESET}")
        return
    if peak < SILENCE_PEAK:
        print(f"{DIM}(no signal on microphone -- peak {peak:.4f}){RESET}")
        return

    t0 = time.perf_counter()
    text = stt.transcribe(pcm)
    log.info("STT: %.1f s of audio in %.0f ms.", secs, (time.perf_counter() - t0) * 1000)
    if strip is not None:
        text = strip(text)
    if not text:
        print(f"{DIM}(didn't catch that){RESET}")
        return

    print(f"{BOLD}You:{RESET} {text}")
    if cfg.log_transcripts:
        _append_transcript(text)
    handle_turn(text, client, speaker)


def _build_stack(cfg: Config):
    from .stt import Transcriber

    print(f"{DIM}Loading Whisper '{cfg.whisper_model}'...{RESET}")
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
# Console trigger: no global keyboard hook.
#
# Why it exists: a global hook (SetWindowsHookEx) has the classic signature of
# a keylogger. Combined with microphone capture and network egress, it forms the
# exact behavioral triad of a spyware implant -- which is what behavioral EDR
# engines exist to detect. This mode requires console focus and installs no
# hook, eliminating the highest-risk component.
# ---------------------------------------------------------------------------
def run_console_mode(cfg: Config, speaker, no_tts: bool) -> None:
    from .audio import Recorder

    stt, client = _build_stack(cfg)
    spk = None if no_tts else speaker

    with Recorder(stt.sample_rate, cfg.input_device, cfg.max_record_seconds) as recorder:
        print(
            f"\n{BOLD}Hermes ready{RESET} (console mode, no keyboard hook)\n"
            f"  ENTER starts recording, ENTER again sends.\n"
            f"  /reset clears history, /sair exits.\n"
        )
        try:
            while True:
                cmd = input(f"{BOLD}[ENTER] speak >{RESET} ").strip().lower()
                if cmd in {"/sair", "/quit", "/exit"}:
                    return
                if cmd == "/reset":
                    client.reset()
                    print(f"{DIM}History cleared.{RESET}")
                    continue
                if spk and spk.speaking:
                    spk.interrupt()

                recorder.start()
                input(f"{BOLD}>> recording... [ENTER] sends{RESET}")
                pcm, peak = recorder.stop()
                process_utterance(pcm, peak, stt, client, cfg, spk)
                if spk:
                    spk.wait_until_idle(timeout=90)
        except (KeyboardInterrupt, EOFError):
            print()
        finally:
            client.close()
    print("Done.")


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
                spk.interrupt()  # barge-in: new speech cuts the previous one
                print(f"\n{DIM}[interrupted]{RESET}")
            recorder.start()
            print(f"\r{BOLD}>> recording...{RESET}  ", end="", flush=True)

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
            f"\n{BOLD}Hermes listening.{RESET}\n"
            f"  Hold {BOLD}{cfg.ptt_key.upper()}{RESET} to speak, release to send.\n"
            f"  {cfg.ptt_key.upper()} during response interrupts.\n"
            f"  {cfg.quit_key.upper()} to exit.\n"
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
    print("\nDone.")


def _append_transcript(text: str) -> None:
    from pathlib import Path

    path = Path.cwd() / "transcripts.log"
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}] {text}\n")


# ---------------------------------------------------------------------------
# Wake word mode: open mic, continuous conversation.
#
# The word "Jarvis" opens a session. Inside it you speak normally, without
# repeating the word. The session closes on its own after FOLLOW_UP_SECONDS
# of silence.
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
            "No wake word detector. Install with "
            "pip install 'hermes-voice[wake]', or use --trigger console."
        )
        return

    wake = FrameAdapter(backend)
    vad = build_vad(cfg)
    stt, client = _build_stack(cfg)
    spk = None if no_tts else speaker

    frame_ms = int(FRAME * 1000 / stt.sample_rate)  # 512 @ 16 kHz = 32 ms

    # With adaptive endpointing the gate closes at the SHORT threshold; who
    # decides whether speech is really finished is the Endpointer, looking at
    # the transcript syntax.
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
            f"\n{BOLD}Hermes in continuous listening.{RESET}\n"
            f'  Say {BOLD}"Jarvis"{RESET} and then speak.\n'
            f"  After the response the session stays open {cfg.follow_up_seconds:.0f}s: "
            f"you can speak without repeating the word.\n"
            f"  {cfg.silence_ms} ms of silence ends your speech. "
            f"Ctrl+C to exit.\n"
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

                # ---- DORMANT: only the detector runs. Nothing is transcribed. --------
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

                # ---- SPEAKING: wait for audio to finish ---------------------
                if st == State.SPEAKING:
                    if not cfg.half_duplex:
                        # Barge-in: wake word, or speech that echo suppression
                        # confirms is not the speaker itself.
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
                            print(f"\n{DIM}[interrupted]{RESET}")
                            show()
                            continue
                    if spk is None or not spk.speaking:
                        sess.to(State.FOLLOW_UP)
                        gate.reset()
                        show()
                    continue

                # ---- THINKING: discard audio ------------------------------
                if st == State.THINKING:
                    if turn_done.is_set():
                        mic.drain()
                        sess.to(State.SPEAKING if spk and spk.speaking else State.FOLLOW_UP)
                        gate.reset()
                        show()
                    continue

                # ---- FOLLOW_UP: speech reopens without wake word --------
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

                # ---- LISTENING: accumulate until end of speech -------------------
                sess.append(frame)
                event = gate.update(vad.prob(frame))

                # Extended wait granted by the Endpointer: the phrase seemed
                # dangling, so we ignore this "end" and keep listening.
                if event == "end" and hold_frames > 0:
                    hold_frames -= 1
                    gate.reset()
                    continue

                # Probe: transcribe what we have and ask if the phrase is done.
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
                log.debug("%d frames dropped due to full queue.", mic.dropped)
    print("Done.")


def _to_int16(frame_float32) -> np.ndarray:
    return (np.clip(frame_float32, -1.0, 1.0) * 32767.0).astype(np.int16)
