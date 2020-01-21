from dataclasses import dataclass


@dataclass
class ResultMetadata:
    result_size: int
    stored_size: int
    save_duration: float

    total_load_durations: float = 0
    num_loads: int = 0

    num_cache_hits: int = 0
    total_durations: float = 0

    call_duration: float = 0
    subcall_duration: float = 0

    estimated_nomamo_call_duration: float = 0

    @property
    def avg_total_duration(self):
        return self.total_durations / self.num_calls

    @property
    def avg_overhead_duration(self):
        return (self.total_durations - self.total_load_durations - self.call_duration) / self.num_calls

    @property
    def avg_load_duration(self):
        return self.total_load_durations / self.num_loads

    @property
    def estimated_saved_time(self):
        return (self.estimated_nomamo_call_duration - self.avg_total_duration) * self.num_calls

    @property
    def num_calls(self):
        return self.num_cache_hits + 1
