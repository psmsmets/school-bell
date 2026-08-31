"""Controllable local audio playback for bell signals."""

import subprocess
from logging import Logger
from threading import Event
from typing import List


class AudioPlayback:
    """Own one audio process and allow another thread to cancel it."""

    def __init__(self, command: List[str], logger: Logger = None):
        self.command = list(command)
        self.logger = logger
        self.process = None

    def start(self):
        if self.logger is not None:
            self.logger.debug(' '.join(self.command))
        self.process = subprocess.Popen(
            self.command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return self

    def wait(self, cancel_event: Event = None, poll_interval: float = .05):
        if self.process is None:
            raise RuntimeError('Playback has not been started!')

        cancelled = False
        while self.process.poll() is None:
            if cancel_event is not None and cancel_event.wait(poll_interval):
                cancelled = True
                self.stop()
                break
            if cancel_event is None:
                self.process.wait()
                break

        output, error = self.process.communicate()
        if output and self.logger is not None:
            self.logger.debug(output.decode('utf-8', errors='replace'))
        if self.process.returncode != 0 and not cancelled:
            if error and self.logger is not None:
                self.logger.error(error.decode('utf-8', errors='replace'))
            return False, False
        return True, cancelled

    def stop(self):
        if self.process is None or self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()


def playback_command(
    wav: str,
    player: List[str],
    test_player: List[str],
    test: bool = False,
    alsa: bool = False,
    device: str = None,
) -> List[str]:
    """Build the platform-specific player command."""
    command = list(test_player if test else player)
    if alsa and device:
        return command + ['-D', device, wav]
    return command + [wav]
