"""Naming things is important.

This module is about figuring out consistent names for things.
"""
from dataclasses import dataclass
import hashlib


@dataclass
class FunctionIdentity:
    qualified_name: str
    hashed_code: int


def get_func_qualified_name(func):
    # TODO: handle Jupyter notebooks?
    # In notebooks, __module__ will be "__main__".
    return f"{func.__module__}.{func.__qualname__}"


def get_func_hash(func):
    return hashlib.md5(func.__code__.co_code)


