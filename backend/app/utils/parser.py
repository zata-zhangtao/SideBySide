from __future__ import annotations

import csv
import io
import json
from typing import Iterable, List, Dict


def sniff_and_parse(data: bytes, filename: str | None = None) -> List[Dict[str, str | None]]:
    name = (filename or "").lower()
    if name.endswith(".json"):
        return parse_json(data)
    return parse_csv(data)


def parse_json(data: bytes) -> List[Dict[str, str | None]]:
    items = json.loads(data.decode("utf-8"))
    out: List[Dict[str, str | None]] = []
    for it in items:
        term = it.get("term") or it.get("word")
        definition = it.get("definition") or it.get("meaning")
        example = it.get("example") or it.get("sentence")
        if term:
            out.append({"term": str(term), "definition": str(definition) if definition else None, "example": str(example) if example else None})
    return out


def parse_csv(data: bytes) -> List[Dict[str, str | None]]:
    text = data.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    out: List[Dict[str, str | None]] = []
    for row in reader:
        # Case-insensitive access
        keys = {k.lower(): v for k, v in row.items()}
        term = keys.get("term") or keys.get("word")
        definition = keys.get("definition") or keys.get("meaning")
        example = keys.get("example") or keys.get("sentence")
        if term:
            out.append({
                "term": term.strip(),
                "definition": definition.strip() if definition else None,
                "example": example.strip() if example else None,
            })
    return out

