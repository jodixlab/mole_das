from __future__ import annotations

import struct
from typing import Any, Iterable, List


_ALIASES = {
    "u16": "uint16",
    "uint16": "uint16",
    "word": "uint16",
    "i16": "int16",
    "int16": "int16",
    "u32": "uint32_be",
    "uint32": "uint32_be",
    "uint32_be": "uint32_be",
    "dword": "uint32_be",
    "i32": "int32_be",
    "int32": "int32_be",
    "int32_be": "int32_be",
    "f32": "float32_be",
    "float32": "float32_be",
    "float32_be": "float32_be",
    "uint32_le": "uint32_le",
    "int32_le": "int32_le",
    "float32_le": "float32_le",
    "float32_badc": "float32_badc",
    "float32_dcba": "float32_dcba",
}


def normalize_dtype(dtype: Any) -> str:
    key = str(dtype or "uint16").strip().lower()
    return _ALIASES.get(key, key or "uint16")


def is_supported_dtype(dtype: Any) -> bool:
    return normalize_dtype(dtype) in {
        "uint16",
        "int16",
        "uint32_be",
        "int32_be",
        "float32_be",
        "uint32_le",
        "int32_le",
        "float32_le",
        "float32_badc",
        "float32_dcba",
    }


def dtype_register_count(dtype: Any) -> int:
    norm = normalize_dtype(dtype)
    if norm in ("uint16", "int16"):
        return 1
    if norm in (
        "uint32_be",
        "int32_be",
        "float32_be",
        "uint32_le",
        "int32_le",
        "float32_le",
        "float32_badc",
        "float32_dcba",
    ):
        return 2
    return 1


def _coerce_words(words: Iterable[Any]) -> List[int]:
    out: List[int] = []
    for word in words:
        try:
            value = int(word) & 0xFFFF
        except Exception as exc:
            raise ValueError(f"Invalid Modbus register word: {word!r}") from exc
        out.append(value)
    return out


def _words_to_be_bytes(words: List[int]) -> bytes:
    return b"".join(struct.pack(">H", w) for w in words)


def decode_words(words: Iterable[Any], dtype: Any) -> float | int:
    norm = normalize_dtype(dtype)
    coerced = _coerce_words(words)
    need = dtype_register_count(norm)
    if len(coerced) < need:
        raise ValueError(f"dtype {norm} requires {need} register(s); got {len(coerced)}")

    if norm == "uint16":
        return coerced[0]
    if norm == "int16":
        return struct.unpack(">h", struct.pack(">H", coerced[0]))[0]

    if need != 2:
        raise ValueError(f"Unsupported dtype: {norm}")

    hi = coerced[0]
    lo = coerced[1]
    base_be = _words_to_be_bytes([hi, lo])

    if norm == "uint32_be":
        return struct.unpack(">I", base_be)[0]
    if norm == "int32_be":
        return struct.unpack(">i", base_be)[0]
    if norm == "float32_be":
        return struct.unpack(">f", base_be)[0]

    if norm in ("uint32_le", "int32_le", "float32_le"):
        le_words = _words_to_be_bytes([lo, hi])
        if norm == "uint32_le":
            return struct.unpack(">I", le_words)[0]
        if norm == "int32_le":
            return struct.unpack(">i", le_words)[0]
        return struct.unpack(">f", le_words)[0]

    if norm == "float32_badc":
        # Register order preserved; swap bytes inside each 16-bit word: AB CD -> BA DC
        b = bytes([base_be[1], base_be[0], base_be[3], base_be[2]])
        return struct.unpack(">f", b)[0]

    if norm == "float32_dcba":
        # Full reverse: AB CD -> DC BA
        return struct.unpack(">f", base_be[::-1])[0]

    raise ValueError(f"Unsupported dtype: {norm}")
