from dataclasses import dataclass
from typing import Generic, TypeVar

from dumbo.internal.fingerprints import Fingerprint

T = TypeVar("T")


# This is kept by online and persistent cache and might later include more debug info.
@dataclass(frozen=True)
class AnnotatedValue(Generic[T]):
    value: T
    fingerprint: Fingerprint


@dataclass
class ResultMetadata:
    result_size: int
    stored_size: int

    total_load_duration: float
    save_duration: float
    num_loads: int

    cache_hits: int
    overhead_duration: float

    call_duration: float
    subcall_duration: float

