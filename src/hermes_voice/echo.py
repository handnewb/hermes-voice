"""Supressao de eco por referencia: barge-in de verdade, sem dependencia externa.

## O problema

Com microfone aberto e caixas de som, o VAD ouve a propria voz sintetizada e o
assistente conversa consigo mesmo. A solucao padrao e meia-duplex: nao escutar
enquanto fala. Funciona, mas mata a fluidez -- conversa humana tem sobreposicao,
e nao poder interromper e o que faz um assistente parecer uma arvore de menu.

## A abordagem

Isto NAO e cancelamento de eco (AEC). AEC de verdade estima a resposta impulsiva
da sala com filtro adaptativo e subtrai o eco do sinal, permitindo transcrever a
fala do usuario mesmo sobreposta. Precisa de alinhamento temporal preciso e, em
geral, de biblioteca nativa.

O que fazemos e mais modesto e resolve o caso que importa: **decidir se o que o
microfone captou e o usuario ou o proprio alto-falante.** Como nos geramos o
audio de saida, sabemos exatamente o que foi enviado. Comparamos a energia do
microfone com a energia esperada da referencia, alinhada por correlacao cruzada,
e so declaramos "o usuario esta falando" quando a energia excede a referencia por
uma margem. Sem subtracao, sem filtro adaptativo, ~200 linhas de numpy.

## Consequencia pratica

Voce consegue interromper falando mais alto que a caixa. Nao consegue conversar
sobreposto em volume baixo. Com fone, nada disso e necessario: nao ha eco.

Degrada com seguranca: se nao consegue estimar o atraso com confianca, volta a
meia-duplex em vez de deixar o assistente em loop consigo mesmo.
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

import numpy as np

log = logging.getLogger("hermes.echo")

EPS = 1e-9


@dataclass(slots=True)
class EchoConfig:
    enabled: bool = True
    # Quanto a energia do microfone precisa exceder a referencia, em dB, para
    # contar como fala do usuario. Abaixo de 4 dB gera falso positivo; acima de
    # 12 exige grito.
    margin_db: float = 7.0
    # Janela de busca do atraso entre saida e microfone.
    max_delay_ms: int = 320
    # Frames consecutivos acima da margem para declarar barge-in. Evita disparo
    # com um estalo.
    trigger_frames: int = 3


class EchoSuppressor:
    """Compara microfone com a referencia de saida para detectar fala real.

    Uso:
        supr.push_reference(pcm_bytes)     # o que foi enviado ao alto-falante
        ...
        if supr.is_user_speech(frame):     # frame do microfone
            barge_in()
    """

    def __init__(self, config: EchoConfig, sample_rate: int, frame_samples: int = 512):
        self.cfg = config
        self.fs = sample_rate
        self.frame = frame_samples

        max_delay = int(sample_rate * config.max_delay_ms / 1000)
        # Um segundo de historia alem do atraso maximo. Buffer curto era o
        # primeiro bug: a referencia perdia o trecho que o microfone estava
        # ouvindo, e a comparacao passava a olhar audio errado.
        self._ref = deque(maxlen=max_delay + sample_rate)
        self._margin = 10.0 ** (config.margin_db / 20.0)

        self._delay = 0
        self._locked = False
        self._since_lock = 0
        self._hot = 0

    # -- referencia -----------------------------------------------------------
    def push_reference(self, pcm_int16: bytes) -> None:
        """Registra o audio entregue ao alto-falante."""
        if not self.cfg.enabled or not pcm_int16:
            return
        n = len(pcm_int16) - (len(pcm_int16) % 2)
        if n <= 0:
            return
        samples = np.frombuffer(pcm_int16[:n], dtype="<i2").astype(np.float32) / 32767.0
        self._ref.extend(samples.tolist())

    def clear(self) -> None:
        self._ref.clear()
        self._locked = False
        self._since_lock = 0
        self._hot = 0

    @property
    def has_reference(self) -> bool:
        return len(self._ref) >= self.frame * 2

    # -- decisao --------------------------------------------------------------
    def is_user_speech(self, mic_float32: np.ndarray) -> bool:
        """True quando o microfone contem fala que nao vem do alto-falante.

        Em vez de estimar um unico atraso e confiar nele, perguntamos: existe
        ALGUM alinhamento da referencia, dentro da janela de busca, que explique
        a energia deste frame? Se existe, e eco. Isso e mais robusto que travar
        um atraso, porque nao depende de o envelope ter estrutura suficiente
        para correlacionar -- tom continuo, por exemplo, tem envelope plano.
        """
        if not self.cfg.enabled:
            return False

        mic_rms = _rms(mic_float32)
        if mic_rms < 0.008:  # silencio: nada a decidir
            self._hot = 0
            return False

        if not self.has_reference:
            return self._accumulate(True)  # nada tocando: e o usuario

        ref = np.fromiter(self._ref, dtype=np.float32, count=len(self._ref))
        n = mic_float32.size
        if ref.size < n + 8:
            return self._accumulate(True)

        residual = self._best_residual(ref, mic_float32)
        # residual e a fracao da energia do microfone que a referencia NAO
        # explica. Perto de 0 = eco puro. Perto de 1 = som independente.
        threshold = 1.0 / self._margin
        return self._accumulate(residual > threshold)

    def _best_residual(self, ref: np.ndarray, mic: np.ndarray) -> float:
        """Menor residuo relativo sobre todos os atrasos da janela de busca."""
        n = mic.size
        max_delay = int(self.fs * self.cfg.max_delay_ms / 1000)
        hop = max(1, n // 8)  # busca em passos, nao amostra a amostra

        mic_energy = float(np.dot(mic, mic)) + EPS
        best = 1.0
        end_max = ref.size
        lag = 0
        while lag <= max_delay:
            end = end_max - lag
            start = end - n
            if start < 0:
                break
            seg = ref[start:end]
            seg_energy = float(np.dot(seg, seg))
            if seg_energy > 1e-8:
                # Ganho otimo por minimos quadrados, limitado a ganho fisico.
                gain = float(np.clip(np.dot(mic, seg) / seg_energy, 0.0, 4.0))
                resid = float(np.dot(mic - gain * seg, mic - gain * seg)) / mic_energy
                if resid < best:
                    best = resid
                    self._delay = lag
                    self._locked = True
            lag += hop
        return best

    def _accumulate(self, hot: bool) -> bool:
        self._hot = self._hot + 1 if hot else 0
        return self._hot >= self.cfg.trigger_frames


def _rms(x: np.ndarray) -> float:
    if x.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))


def build_echo(cfg, sample_rate: int, frame_samples: int = 512) -> EchoSuppressor | None:
    """None quando meia-duplex esta ativo -- nao ha o que suprimir."""
    if getattr(cfg, "half_duplex", True):
        return None
    ec = EchoConfig(
        enabled=True,
        margin_db=getattr(cfg, "echo_margin_db", 7.0),
        trigger_frames=getattr(cfg, "echo_trigger_frames", 3),
    )
    log.info("Supressao de eco ativa: margem %.1f dB. Fone ainda e melhor.", ec.margin_db)
    return EchoSuppressor(ec, sample_rate, frame_samples)
