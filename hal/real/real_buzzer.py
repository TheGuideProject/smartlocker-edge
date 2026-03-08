"""
Real Buzzer Driver - GPIO PWM Buzzer

Controls a passive buzzer connected to a PWM-capable GPIO pin
on the Raspberry Pi. Generates tones at specific frequencies
for audio feedback (confirmation beeps, warnings, errors).

Hardware setup:
  - Passive buzzer (NOT active buzzer) connected to GPIO 18 (default)
  - Active buzzers only make one tone; passive buzzers can play frequencies
  - Connect buzzer between GPIO pin and GND (through a transistor if needed)

Required library (pick one):
  Option A: RPi.GPIO (pre-installed on Raspberry Pi OS)
    import RPi.GPIO as GPIO

  Option B: gpiozero (higher-level, also pre-installed)
    from gpiozero import TonalBuzzer

This is a STUB driver. Methods log warnings and return safe defaults
when the hardware is not connected, so the system never crashes.
Flesh out the TODOs when your buzzer arrives.
"""

import logging
import threading
import time
from typing import Optional

from hal.interfaces import BuzzerDriverInterface, BuzzerPattern

logger = logging.getLogger("smartlocker.sensor")

# Frequency and timing definitions for each pattern
_PATTERN_DEFINITIONS = {
    BuzzerPattern.CONFIRM: [
        (1000, 0.15),            # Single short beep at 1kHz
    ],
    BuzzerPattern.WARNING: [
        (800, 0.15),             # Double beep
        (0, 0.10),               # Silence gap
        (800, 0.15),
    ],
    BuzzerPattern.ERROR: [
        (400, 1.0),              # Long low buzz
    ],
    BuzzerPattern.TARGET_REACHED: [
        (800, 0.1),              # Rising three-tone
        (1000, 0.1),
        (1200, 0.2),
    ],
    BuzzerPattern.TICK: [
        (1500, 0.05),            # Very short click
    ],
}


class RealBuzzerDriver(BuzzerDriverInterface):
    """
    Real GPIO PWM buzzer driver.

    Uses RPi.GPIO PWM to generate tones on a passive buzzer.
    Sound patterns are played in a background thread to avoid
    blocking the main polling loop.
    """

    def __init__(self):
        from config.settings import BUZZER_GPIO_PIN
        self._gpio_pin = BUZZER_GPIO_PIN
        self._pwm = None
        self._initialized = False
        self._play_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()

    def initialize(self) -> bool:
        """
        Set up GPIO pin for PWM output.
        Returns True if GPIO is configured, False on error.
        """
        try:
            # TODO: Uncomment when buzzer hardware is connected
            # -------------------------------------------------------
            # import RPi.GPIO as GPIO
            #
            # GPIO.setmode(GPIO.BCM)
            # GPIO.setup(self._gpio_pin, GPIO.OUT)
            #
            # # Create PWM instance (start with 1kHz, 0% duty = silent)
            # self._pwm = GPIO.PWM(self._gpio_pin, 1000)
            # self._pwm.start(0)  # 0% duty cycle = no sound
            #
            # logger.info(f"[REAL BUZZER] Initialized on GPIO {self._gpio_pin}")
            # -------------------------------------------------------

            logger.warning(
                "[REAL BUZZER] STUB: GPIO buzzer driver not yet implemented. "
                "Uncomment the initialization code when hardware is connected."
            )
            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"[REAL BUZZER] Failed to initialize GPIO: {e}")
            self._initialized = False
            return False

    def play(self, pattern: BuzzerPattern) -> None:
        """
        Play a predefined sound pattern in a background thread.
        Non-blocking: starts the sound and returns immediately.
        If another pattern is already playing, it is stopped first.
        """
        if not self._initialized:
            return

        # Stop any currently playing pattern
        self.stop()

        self._stop_flag.clear()

        # Play in background thread
        self._play_thread = threading.Thread(
            target=self._play_pattern,
            args=(pattern,),
            daemon=True,
        )
        self._play_thread.start()

    def _play_pattern(self, pattern: BuzzerPattern) -> None:
        """Background thread: play the tone sequence for a pattern."""
        tones = _PATTERN_DEFINITIONS.get(pattern, [(1000, 0.15)])

        for freq, duration in tones:
            if self._stop_flag.is_set():
                break

            try:
                # TODO: Uncomment when buzzer hardware is connected
                # -------------------------------------------------------
                # if freq == 0:
                #     # Silence: set duty cycle to 0
                #     self._pwm.ChangeDutyCycle(0)
                # else:
                #     # Play tone: change frequency and set 50% duty cycle
                #     self._pwm.ChangeFrequency(freq)
                #     self._pwm.ChangeDutyCycle(50)
                # -------------------------------------------------------

                logger.info(f"[REAL BUZZER] Tone: {freq}Hz for {duration}s")

            except Exception as e:
                logger.error(f"[REAL BUZZER] Play error: {e}")
                break

            # Wait for the tone duration (check stop flag periodically)
            end_time = time.time() + duration
            while time.time() < end_time:
                if self._stop_flag.is_set():
                    break
                time.sleep(0.01)

        # Silence after pattern completes
        try:
            # TODO: Uncomment when hardware is connected
            # self._pwm.ChangeDutyCycle(0)
            pass
        except Exception:
            pass

    def stop(self) -> None:
        """Stop any currently playing sound."""
        self._stop_flag.set()
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=1.0)

        try:
            # TODO: Uncomment when hardware is connected
            # if self._pwm:
            #     self._pwm.ChangeDutyCycle(0)
            pass
        except Exception:
            pass

    def shutdown(self) -> None:
        """Stop sound and release GPIO resources."""
        self.stop()

        try:
            # TODO: Uncomment when hardware is connected
            # if self._pwm:
            #     self._pwm.stop()
            # import RPi.GPIO as GPIO
            # GPIO.cleanup(self._gpio_pin)
            pass
        except Exception:
            pass

        self._pwm = None
        self._initialized = False
        logger.info("[REAL BUZZER] Shutdown")
