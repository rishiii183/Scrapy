"""
Humanized Outreach Pacing & Daily Send Cap Controller (Milestone 4 - Agent 4).

Features:
- Randomized delay calculation strictly within 45.0 to 180.0 seconds
- Non-deterministic jitter distribution to protect sender domain reputation
- Configurable test-mode / sub-second simulated clock for instant automated testing
- Daily send cap enforcement (default 25 leads per day)
- Stateful pacing tracker maintaining dispatch volume and simulated elapsed time
"""

import time
import random
import logging
from typing import Any, List, Optional
from src.config import MIN_DELAY_SECONDS, MAX_DELAY_SECONDS, DAILY_SEND_CAP

logger = logging.getLogger(__name__)


def compute_random_delay(
    min_s: float = MIN_DELAY_SECONDS,
    max_s: float = MAX_DELAY_SECONDS,
) -> float:
    """
    Generate randomized jitter delay strictly within [min_s, max_s] seconds.
    Default: 45.0 to 180.0 seconds.
    """
    if min_s > max_s:
        min_s, max_s = max_s, min_s
    return random.uniform(float(min_s), float(max_s))


def is_valid_pacing_delay(
    delay: float,
    min_s: float = MIN_DELAY_SECONDS,
    max_s: float = MAX_DELAY_SECONDS,
) -> bool:
    """
    Validate that a given delay falls within the required pacing boundaries.
    """
    return float(min_s) <= float(delay) <= float(max_s)


def apply_daily_cap(items: List[Any], cap: int = DAILY_SEND_CAP) -> List[Any]:
    """
    Enforce daily outreach volume cap.
    Returns sliced batch up to cap elements. If cap <= 0, returns empty list.
    """
    if cap <= 0:
        return []
    return items[:cap]


class PacingController:
    """
    Stateful pacing and send cap controller for outreach dispatch.
    """

    def __init__(
        self,
        min_delay: float = MIN_DELAY_SECONDS,
        max_delay: float = MAX_DELAY_SECONDS,
        daily_cap: int = DAILY_SEND_CAP,
        test_mode: bool = False,
        test_delay: float = 0.0,
    ) -> None:
        self.min_delay = float(min_delay)
        self.max_delay = float(max_delay)
        self.daily_cap = int(daily_cap)
        self.test_mode = test_mode
        self.test_delay = float(test_delay)

        self.sent_count = 0
        self.simulated_elapsed = 0.0
        self.delays_history: List[float] = []

    def can_dispatch(self) -> bool:
        """Check if daily send cap allows further dispatches."""
        return self.sent_count < self.daily_cap

    def get_remaining_cap(self) -> int:
        """Return number of dispatches remaining before reaching daily cap."""
        return max(0, self.daily_cap - self.sent_count)

    def wait(self, custom_delay: Optional[float] = None) -> float:
        """
        Execute or simulate pacing delay between dispatches.

        In test_mode:
            Increments simulated_elapsed clock instantly without real blocking.
        In live production:
            Calls time.sleep(delay) to enforce real humanized intervals.

        Returns:
            float: Delay in seconds that was applied or simulated.
        """
        if custom_delay is not None:
            delay = float(custom_delay)
        elif self.test_mode:
            delay = self.test_delay if self.test_delay > 0.0 else compute_random_delay(self.min_delay, self.max_delay)
        else:
            delay = compute_random_delay(self.min_delay, self.max_delay)

        self.simulated_elapsed += delay
        self.delays_history.append(delay)

        if not self.test_mode and delay > 0.0:
            logger.info("Humanized pacing: sleeping for %.2f seconds...", delay)
            time.sleep(delay)

        return delay

    def record_dispatch(self) -> int:
        """
        Increment sent counter and return updated total.
        """
        self.sent_count += 1
        return self.sent_count

    def reset(self) -> None:
        """Reset sent counter, elapsed time, and delay history."""
        self.sent_count = 0
        self.simulated_elapsed = 0.0
        self.delays_history.clear()
