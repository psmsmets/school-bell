"""GPIO input adapter for a single physical manual bell button."""

from threading import Event, Lock, Thread

from gpiozero import Button


class ManualBellInput:
    """Translate debounced button events into bell trigger requests."""

    MODES = ('once', 'hold')
    PULLS = {'up': True, 'down': False, 'floating': None}

    def __init__(self, config: dict, trigger, logger, output_pins=None):
        self.config = self.validate(config, output_pins or [])
        self._trigger = trigger
        self._logger = logger
        self._cancel_event = Event()
        self._worker_lock = Lock()
        self._worker = None
        self.button = Button(
            self.config['gpio'],
            pull_up=self.PULLS[self.config['pull']],
            bounce_time=self.config['bounce_time'],
        )
        self.button.when_pressed = self._pressed
        if self.config['mode'] == 'hold':
            self.button.when_released = self._released

    @classmethod
    def validate(cls, config: dict, output_pins):
        if not isinstance(config, dict):
            raise TypeError('manual_bell should be a dictionary!')
        gpio = config.get('gpio')
        if not isinstance(gpio, int) or isinstance(gpio, bool):
            raise TypeError('manual_bell.gpio should be an integer!')
        if gpio in output_pins:
            raise ValueError(
                'manual_bell.gpio should not also be a buzz_gpio output!'
            )
        mode = str(config.get('mode', 'once')).lower()
        if mode not in cls.MODES:
            raise ValueError('manual_bell.mode should be once or hold!')
        pull = str(config.get('pull', 'up')).lower()
        if pull not in cls.PULLS:
            raise ValueError(
                'manual_bell.pull should be up, down or floating!'
            )
        wav_key = config.get('wav_key')
        if wav_key is None:
            raise ValueError('manual_bell.wav_key is required!')
        try:
            bounce_time = float(config.get('bounce_time', .05))
        except (TypeError, ValueError):
            raise TypeError('manual_bell.bounce_time should be a number!')
        if bounce_time < 0:
            raise ValueError('manual_bell.bounce_time should not be negative!')
        return {
            'gpio': gpio,
            'wav_key': str(wav_key),
            'mode': mode,
            'pull': pull,
            'bounce_time': bounce_time,
        }

    def _pressed(self):
        with self._worker_lock:
            if self._worker is not None and self._worker.is_alive():
                # Submit the extra press as well so the central coordinator
                # can emit a structured bell_trigger_ignored event.
                Thread(
                    target=self._run,
                    name='school-bell-manual-button-ignored',
                    daemon=True,
                ).start()
                return
            self._cancel_event = Event()
            self._worker = Thread(
                target=self._run,
                name='school-bell-manual-button',
                daemon=True,
            )
            self._worker.start()

    def _released(self):
        self._cancel_event.set()

    def _run(self):
        try:
            self._trigger(
                self.config['wav_key'],
                source='manual_gpio',
                mode=self.config['mode'],
                cancel_event=self._cancel_event,
                respect_calendar=False,
                include_remote=False,
                source_gpio=self.config['gpio'],
            )
        except Exception as err:
            self._logger.error('Manual bell trigger failed: %s', err)

    def close(self):
        self._cancel_event.set()
        self.button.close()
        worker = self._worker
        if worker is not None and worker.is_alive():
            worker.join(timeout=2)
