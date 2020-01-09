from dataclasses import dataclass
from typing import Generic, TypeVar

from dumbo.internal.fingerprints import Fingerprint

T = TypeVar("T")


# This is kept by online and persistent cache and might later include more debug info.
@dataclass(frozen=True)
class AnnotatedValue(Generic[T]):
    value: T
    fingerprint: Fingerprint
