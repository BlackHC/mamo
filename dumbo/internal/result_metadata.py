from dataclasses import dataclass


@dataclass
class ResultMetadata:
    result_size: int = 0
    #stored_size: int

    #total_load_duration: float = 0
    #save_duration: float = 0
    #num_loads: int = 0

    #cache_hits: int = 0
    #overhead_duration: float = 0

    #call_duration: float = 0
    #subcall_duration: float = 0

