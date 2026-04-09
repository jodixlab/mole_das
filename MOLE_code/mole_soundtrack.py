"""mole_soundtrack.py

MOLE-DAS Optional 8-bit Soundtrack Player.

Design goals
- Optional dependency: if audio libs or an audio device are unavailable, it fails safely.
- Low CPU usage: playback handled by backend; no busy loops.
- Windows runtime-ready: includes stdlib winsound fallback (no pip installs).

Backend order (default backend="auto")
1) pygame       smooth looping + live volume
2) simpleaudio  loops with possible gaps; volume requires restart
3) winsound     stdlib Windows fallback; loops a WAV file; volume requires restart

Usage
    from mole_soundtrack import SoundtrackPlayer

    player = SoundtrackPlayer("mole_assets/audio/mole_8bit_theme.wav", volume=0.2)
    player.start()
    ...
    player.set_volume(0.05)
    ...
    player.stop()

Notes on volume
- pygame: live change
- simpleaudio / winsound: we regenerate a scaled WAV and restart playback
"""

from __future__ import annotations

import atexit
import os
import tempfile
import threading
import time
import wave
import audioop
from dataclasses import dataclass
from typing import Optional


@dataclass
class SoundtrackStatus:
    started: bool
    backend: str
    message: str = ""


class SoundtrackPlayer:
    def __init__(
        self,
        wav_path: str,
        volume: float = 0.25,
        loop: bool = True,
        backend: str = "auto",   # auto | pygame | simpleaudio | winsound
        quiet: bool = True,
    ):
        self.wav_path = wav_path
        self.volume = max(0.0, min(float(volume), 1.0))
        self.loop = bool(loop)
        self.backend = (backend or "auto").lower().strip()
        self.quiet = bool(quiet)

        self._started = False
        self._status = SoundtrackStatus(False, "none", "not started")

        # pygame state
        self._pygame = None

        # simpleaudio state
        self._sa = None
        self._sa_thread: Optional[threading.Thread] = None
        self._sa_stop = threading.Event()

        # winsound state
        self._winsound = None
        self._ws_play_path: Optional[str] = None
        self._ws_scaled_tmp: Optional[str] = None

        atexit.register(self.stop)

    @property
    def status(self) -> SoundtrackStatus:
        return self._status

    def start(self) -> bool:
        if self._started:
            return True

        wav_path = self._resolve_wav_path()
        if not wav_path:
            return False

        choice = (self.backend or "auto").lower().strip()
        if choice not in ("auto", "pygame", "simpleaudio", "winsound"):
            choice = "auto"

        # Try pygame first (best UX)
        if choice in ("auto", "pygame"):
            ok = self._start_pygame(wav_path)
            if ok:
                return True

        # Try simpleaudio next
        if choice in ("auto", "simpleaudio"):
            ok = self._start_simpleaudio(wav_path)
            if ok:
                return True

        # Windows stdlib fallback
        if choice in ("auto", "winsound"):
            ok = self._start_winsound(wav_path)
            if ok:
                return True

        self._status = SoundtrackStatus(False, "none", "no audio backend available")
        return False

    def stop(self) -> None:
        # pygame
        try:
            if self._pygame is not None:
                try:
                    self._pygame.mixer.music.stop()
                except Exception:
                    pass
                try:
                    self._pygame.mixer.quit()
                except Exception:
                    pass
                self._pygame = None
        except Exception:
            pass

        # simpleaudio
        try:
            self._sa_stop.set()
            if self._sa_thread is not None and self._sa_thread.is_alive():
                self._sa_thread.join(timeout=0.75)
            self._sa_thread = None
        except Exception:
            pass

        # winsound
        try:
            if self._winsound is not None:
                try:
                    self._winsound.PlaySound(None, self._winsound.SND_PURGE)
                except Exception:
                    pass
        except Exception:
            pass

        # cleanup any generated scaled wav
        try:
            self._cleanup_scaled_wav()
        except Exception:
            pass

        self._started = False
        # keep backend name for diagnostics
        try:
            b = self._status.backend
        except Exception:
            b = "none"
        self._status = SoundtrackStatus(False, b, "stopped")

    def set_volume(self, volume: float) -> None:
        """Set volume (0..1).

        pygame: applies live.
        simpleaudio/winsound: restarts playback so scaled frames take effect.
        """
        try:
            v = float(volume)
        except Exception:
            return
        if v < 0.0:
            v = 0.0
        if v > 1.0:
            v = 1.0
        self.volume = v

        # not started => just store preference
        if not self._started:
            try:
                self._status = SoundtrackStatus(False, self._status.backend, f"volume set {v:.2f}")
            except Exception:
                pass
            return

        # live update for pygame
        if self._pygame is not None:
            try:
                self._pygame.mixer.music.set_volume(v)
                self._status = SoundtrackStatus(True, "pygame", f"playing (vol {v:.2f})")
                return
            except Exception:
                # fall through to restart
                pass

        # simpleaudio/winsound require restart
        try:
            backend_now = (self._status.backend or "auto").lower()
            self.backend = backend_now if backend_now in ("pygame", "simpleaudio", "winsound") else "auto"
        except Exception:
            pass

        try:
            self.stop()
        except Exception:
            pass
        try:
            self.start()
        except Exception:
            pass

    # -----------------
    # Helpers
    # -----------------
    def _resolve_wav_path(self) -> Optional[str]:
        if not self.wav_path:
            self._status = SoundtrackStatus(False, "none", "no wav_path provided")
            return None
        wav_path = os.path.abspath(self.wav_path)
        if not os.path.exists(wav_path):
            self._status = SoundtrackStatus(False, "none", f"missing file: {wav_path}")
            return None
        return wav_path

    def _cleanup_scaled_wav(self) -> None:
        # Only delete after stop to avoid file-in-use issues
        for fp in (self._ws_scaled_tmp,):
            if fp and os.path.exists(fp):
                try:
                    os.remove(fp)
                except Exception:
                    pass
        self._ws_scaled_tmp = None
        self._ws_play_path = None

    def _make_scaled_wav(self, src_path: str, volume: float) -> str:
        """Create a temporary scaled WAV (PCM) for winsound/simpleaudio restarts."""
        # If volume is basically 1.0, we can use original
        if volume >= 0.999:
            return src_path

        # read source wav
        with wave.open(src_path, "rb") as wf:
            params = wf.getparams()
            frames = wf.readframes(wf.getnframes())

        # scale frames
        if params.sampwidth in (1, 2, 3, 4):
            frames = audioop.mul(frames, params.sampwidth, max(0.0, min(volume, 1.0)))

        # write temp
        fd, tmp_path = tempfile.mkstemp(prefix="mole_soundtrack_scaled_", suffix=".wav")
        os.close(fd)
        with wave.open(tmp_path, "wb") as out:
            out.setparams(params)
            out.writeframes(frames)

        return tmp_path

    # -----------------
    # Backend: pygame
    # -----------------
    def _start_pygame(self, wav_path: str) -> bool:
        try:
            import pygame  # type: ignore
        except Exception as e:
            self._log(f"pygame import failed: {e}")
            return False

        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.music.load(wav_path)
            pygame.mixer.music.set_volume(self.volume)
            loops = -1 if self.loop else 0
            pygame.mixer.music.play(loops=loops)

            self._pygame = pygame
            self._started = True
            self._status = SoundtrackStatus(True, "pygame", "playing")
            self._log(f"started (pygame): {wav_path}")
            return True
        except Exception as e:
            try:
                pygame.mixer.quit()
            except Exception:
                pass
            self._log(f"pygame start failed: {e}")
            return False

    # ---------------------
    # Backend: simpleaudio
    # ---------------------
    def _start_simpleaudio(self, wav_path: str) -> bool:
        try:
            import simpleaudio as sa  # type: ignore
        except Exception as e:
            self._log(f"simpleaudio import failed: {e}")
            return False

        try:
            # scale frames in-memory (like before)
            with wave.open(wav_path, "rb") as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())

            if self.volume != 1.0:
                frames = audioop.mul(frames, sampwidth, self.volume)

            wave_obj = sa.WaveObject(frames, channels, sampwidth, framerate)

            self._sa = sa
            self._sa_stop.clear()
            self._sa_thread = threading.Thread(
                target=self._simpleaudio_loop,
                args=(wave_obj,),
                daemon=True,
            )
            self._sa_thread.start()

            self._started = True
            self._status = SoundtrackStatus(True, "simpleaudio", "playing")
            self._log(f"started (simpleaudio): {wav_path}")
            return True
        except Exception as e:
            self._log(f"simpleaudio start failed: {e}")
            return False

    def _simpleaudio_loop(self, wave_obj) -> None:
        while not self._sa_stop.is_set():
            try:
                play_obj = wave_obj.play()
                play_obj.wait_done()
            except Exception:
                break
            if not self.loop:
                break
            time.sleep(0.01)

    # ------------------
    # Backend: winsound
    # ------------------
    def _start_winsound(self, wav_path: str) -> bool:
        try:
            import winsound  # type: ignore
        except Exception as e:
            self._log(f"winsound import failed: {e}")
            return False

        try:
            # cleanup any previous temp
            self._cleanup_scaled_wav()

            play_path = wav_path
            if self.volume < 0.999:
                play_path = self._make_scaled_wav(wav_path, self.volume)
                self._ws_scaled_tmp = play_path

            flags = winsound.SND_FILENAME | winsound.SND_ASYNC
            if self.loop:
                flags |= winsound.SND_LOOP

            winsound.PlaySound(play_path, flags)

            self._winsound = winsound
            self._ws_play_path = play_path
            self._started = True
            self._status = SoundtrackStatus(True, "winsound", "playing")
            self._log(f"started (winsound): {play_path}")
            return True
        except Exception as e:
            self._log(f"winsound start failed: {e}")
            return False

    def _log(self, msg: str) -> None:
        if not self.quiet:
            print(f"[soundtrack] {msg}")
