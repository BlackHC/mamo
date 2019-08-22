"""Naming things is important.

This module is about figuring out consistent names for things.
"""
from dataclasses import dataclass
import hashlib
from dumbo.internal.qualified_name import get_qualified_name


@dataclass
class FunctionIdentity:
    qualified_name: str
    hashed_code: int


def get_func_qualified_name(func):
    return get_qualified_name(func)


def get_func_hash(func):
    return hashlib.md5(func.__code__.co_code)


def identify_function(func):
    return FunctionIdentity(get_func_qualified_name(func), get_func_hash(func))
