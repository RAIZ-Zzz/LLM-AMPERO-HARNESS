"""Offline check (no pedal): python -X utf8 -m pytest -q  or  python -X utf8 test_amp.py"""
from types import SimpleNamespace

from ampero2.catalog import Catalog

from amp import is_empty, resolve

cat = Catalog.load()
ok = {"name": "T", "blocks": [{"slot": 0, "cat": "DRV", "model": "Green Drive", "params": {"Gain": 60}}]}


def bad(**b):
    return {"name": "T", "blocks": [{"slot": 0, "cat": "DRV", "model": "Green Drive", **b}]}


def test_guard_and_validation():
    assert is_empty(SimpleNamespace(slot_codes=[None] * 12))
    assert not is_empty(SimpleNamespace(slot_codes=[None] * 11 + [5]))
    assert resolve(ok, cat)[0][2] == {0: 60.0}
    for chain in (bad(params={"Drive": 5}), bad(params={"Tone": 150}), bad(model="Super Klon")):
        try:
            resolve(chain, cat)
        except (ValueError, KeyError, LookupError):
            continue
        raise AssertionError(f"accepted {chain}")


if __name__ == "__main__":
    test_guard_and_validation(); print("ok")
