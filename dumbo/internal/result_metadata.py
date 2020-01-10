from dataclasses import dataclass


@dataclass
class ResultMetadata:
    result_size: int
    stored_size: int

    save_duration: float = 0
    total_load_durations: float = 0
    num_loads: int = 0

    #cache_hits: int = 0
    #overhead_duration: float = 0

    #call_duration: float = 0
    #subcall_duration: float = 0

