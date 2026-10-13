from dataclasses import dataclass, asdict, field

MONITORING_SCHEMA_VERSION = "module7_stage2_monitoring_v1"

@dataclass(frozen=True)
class MonitoringWindow:
    window_id: str
    start_step: int
    end_step: int
    purpose: str
    selection_rationale: str
    created_at_utc: str = ""
    source_versions: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.window_id or not self.purpose or not self.selection_rationale:
            raise ValueError("window_id, purpose and selection_rationale are required")
        if not isinstance(self.start_step, int) or not isinstance(self.end_step, int):
            raise TypeError("window bounds must be integers")
        if self.start_step > self.end_step:
            raise ValueError("window start_step must be <= end_step")

    def to_dict(self):
        return asdict(self)

def validate_windows(windows, allowed_start=378, allowed_end=743):
    windows = list(windows)
    ordered = sorted(windows, key=lambda w: (w.start_step, w.end_step, w.window_id))
    seen = set()
    previous_end = None
    for window in ordered:
        if window.window_id in seen:
            raise ValueError(f"duplicate window_id: {window.window_id}")
        seen.add(window.window_id)
        if window.start_step < allowed_start or window.end_step > allowed_end:
            raise ValueError("monitoring window is outside the source step range")
        if previous_end is not None and window.start_step <= previous_end:
            raise ValueError("monitoring windows must be non-overlapping")
        previous_end = window.end_step
    return ordered
