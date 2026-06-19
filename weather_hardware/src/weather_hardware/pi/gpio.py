import lgpio

class GPIO:
    NONE  = 0
    IN    = 1
    OUT   = 2
    INOUT = 3

    ACTIVE_LOW  = lgpio.SET_ACTIVE_LOW
    OPEN_DRAIN  = lgpio.SET_OPEN_DRAIN
    OPEN_SOURCE = lgpio.SET_OPEN_SOURCE
    PULL_UP     = lgpio.SET_PULL_UP
    PULL_DOWN   = lgpio.SET_PULL_DOWN
    PULL_NONE   = lgpio.SET_PULL_NONE

    def __init__(self, pin, mode=1, modifiers=0):
        self.pin = pin

        self._gpio = lgpio.gpiochip_open(0)
        self.modifiers = modifiers
        self._cb_handle = None        

        # Register callbacks lazily to avoid callback storm on
        # unused pins
        self._on_rising = None
        self._on_falling = None

        if mode & GPIO.IN:
            lgpio.gpio_claim_input(self._gpio, pin, self.modifiers)
        if mode & GPIO.OUT:
            lgpio.gpio_claim_output(self._gpio, pin, self.modifiers)

        self.on_error = None

    def _callback(self, chip, pin, level, timestamp):
        cb = self._on_rising if level == 1 else self._on_falling

        if cb is not None:
            cb(timestamp, level, source=self)

    @property
    def on_rising(self):
        return self._on_rising

    @on_rising.setter
    def on_rising(self, cb):
        # Register GPIO callback if not already present
        # Only one callback can be registered, so it needs to be
        # both for rising and falling edge
        if cb and not self._cb_handle:
            lgpio.gpio_claim_alert(self._gpio, self.pin, lgpio.BOTH_EDGES, self.modifiers)

            self._cb_handle = lgpio.callback(
                self._gpio,
                self.pin,
                lgpio.BOTH_EDGES,
                self._callback,
            )

        # Deregister GPIO callback if this was the last callback
        # and it is being unset
        elif not cb and self._cb_handle and not self._on_falling:
            lgpio.gpio_free(self._gpio, self.pin)
            self._cb_handle.cancel()
            self._cb_handle = None

        self._on_rising = cb

    @property
    def on_falling(self):
        return self._on_falling

    @on_falling.setter
    def on_falling(self, cb):
        # Register GPIO callback if not already present
        # Only one callback can be registered, so it needs to be
        # both for rising and falling edge
        if cb and not self._cb_handle:
            self._cb_handle = lgpio.callback(
                self._gpio,
                self.pin,
                lgpio.BOTH_EDGES,
                self._callback,
            )

        # Deregister GPIO callback if this was the last callback
        # and it is being unset
        elif not cb and self._cb_handle and not self._on_rising:
            self._cb_handle.cancel()
            self._cb_handle = None

        self._on_falling = cb

    def write(self, value: int):
        lgpio.gpio_write(self._gpio, self.pin, value)

    def read(self) -> int:
        return lgpio.gpio_read(self._gpio, self.pin)

    def close(self):
        if self._cb_handle:
            self._cb_handle.cancel()
            self._cb_handle = None

            lgpio.gpio_free(self._gpio, self.pin)

        lgpio.gpiochip_close(self._gpio)
