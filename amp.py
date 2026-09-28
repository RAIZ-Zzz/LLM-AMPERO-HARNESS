"""Safe wrapper around ampero2 (jpfaria/hotone-ampero-2) for Windows.

Only exposes: patches, show, check, build. `build` refuses to write any patch that has models in it.
Usage:
  python amp.py patches
  python amp.py show A01-1
  python amp.py check chains/x.json          # offline: models/knobs exist and are in range
  python amp.py build A57-1 chains/x.json    # write chain into an EMPTY patch, save, read back
"""
import json
import subprocess
import sys
import time

if not sys.flags.utf8_mode:  # ampero2's Catalog.load() reads JSON with the locale codec (GBK here) and crashes
    sys.exit(subprocess.call([sys.executable, "-X", "utf8", *sys.argv]))

import mido
from ampero2.catalog import Catalog
from ampero2.device import Ampero
from ampero2.patch import decode_reply, decompress_patch, parse_image, patch_names
from ampero2.protocol import (SLOTS, msg_clear_slot, msg_get_patch, msg_load_patch, msg_query_inventory,
                              msg_save_patch, msg_scene, msg_scene_powers, msg_set_model, msg_set_param,
                              patch_index, patch_label)

PORT_PREFIX = "Ampero II Stage MIDI"
GAP_S = 0.15  # ponytail: fixed pause between writes, the pedal sends no ack; raise if writes get lost


def connect() -> Ampero:
    # Windows names in/out ports separately (often with an index suffix); Ampero() assumes one shared name.
    def pick(names):
        hits = [n for n in names if n.startswith(PORT_PREFIX)]
        if not hits:
            sys.exit(f"no MIDI port starting with {PORT_PREFIX!r}: {names}. Close the Ampero II editor and replug.")
        return hits[0]
    dev = Ampero.__new__(Ampero)
    dev._in = mido.open_input(pick(mido.get_input_names()))
    dev._out = mido.open_output(pick(mido.get_output_names()))
    return dev


def read_patch(dev, label):
    return parse_image(decompress_patch(dev.request_dump(msg_get_patch(patch_index(label)))))


def is_empty(img) -> bool:
    return all(c is None for c in img.slot_codes)


def resolve(chain, cat):
    """chain JSON -> [(slot, model, {param_index: value})]; raises ValueError on anything not in the catalog."""
    out, used = [], set()
    for b in chain["blocks"]:
        slot = b["slot"]
        if not 0 <= slot < SLOTS or slot in used:
            raise ValueError(f"bad or duplicate slot {slot}")
        used.add(slot)
        m = cat.find(b["cat"], b["model"])  # raises if the model does not exist
        by_name = {p.name.lower(): p for p in m.params}
        vals = {}
        for name, v in b.get("params", {}).items():
            p = by_name.get(name.lower())
            if p is None:
                raise ValueError(f"{m.name} has no knob {name!r}; knobs: {[p.name for p in m.params]}")
            if not float(p.min) <= v <= float(p.max):
                raise ValueError(f"{m.name} {p.name}={v} outside [{p.min}, {p.max}]")
            vals[p.index] = float(v)
        out.append((slot, m, vals))
    if len(chain["name"]) > 16 or not chain["name"].isascii():
        raise ValueError("patch name must be ASCII, max 16 chars")
    return out


def show(img, cat):
    print(f"{patch_label(img.header.index)} {img.header.name!r}")
    for s, code in enumerate(img.slot_codes):
        if code is not None:
            m = cat.by_code(code)
            vals = " ".join(f"{p.name}={img.param(0, s, p.index):g}" for p in m.params)
            print(f"  slot {s:2d} {m.category:7s} {m.name:20s} on={img.powers[0][s]}  {vals}")


def build(dev, label, chain, cat):
    blocks = resolve(chain, cat)
    # Reading the *current* patch returns its edit buffer, not flash: switch away first so the check sees flash.
    other = "A1-1" if patch_index(label) else "A1-2"
    dev.send(msg_load_patch(patch_index(other))); time.sleep(GAP_S * 3)
    before = read_patch(dev, label)
    if not is_empty(before):
        show(before, cat)
        sys.exit(f"REFUSED: {label} is not empty. Pick an empty patch or get explicit permission.")
    for msg in [msg_load_patch(patch_index(label)), msg_scene(0)]:
        dev.send(msg); time.sleep(GAP_S * 3)
    used = {s for s, _, _ in blocks}
    for s in range(SLOTS):
        if s not in used:
            dev.send(msg_clear_slot(s)); time.sleep(GAP_S)
    for s, m, vals in blocks:
        dev.send(msg_set_model(s, m.category_index, m.code)); time.sleep(GAP_S * 2)
        for i, v in vals.items():
            dev.send(msg_set_param(s, i, v)); time.sleep(GAP_S)
    dev.send(msg_scene_powers(0, [int(s in used) for s in range(SLOTS)])); time.sleep(GAP_S)
    dev.send(msg_save_patch(patch_index(label), chain["name"])); time.sleep(GAP_S * 5)
    # re-read from flash: load another patch first, otherwise load is a no-op
    dev.send(msg_load_patch(patch_index(other))); time.sleep(GAP_S * 3)
    dev.send(msg_load_patch(patch_index(label))); time.sleep(GAP_S * 3)
    after = read_patch(dev, label)
    show(after, cat)
    bad = [f"slot {s}: {m.name}" for s, m, vals in blocks
           if after.slot_codes[s] != m.code or any(abs(after.param(0, s, i) - v) > 0.51 for i, v in vals.items())]
    print("VERIFY OK" if not bad and after.header.name == chain["name"] else f"VERIFY FAILED: {bad or 'name'}")


def main(argv):
    cmd, args = argv[1], argv[2:]
    cat = Catalog.load()
    if cmd == "check":
        for s, m, vals in resolve(json.load(open(args[0], encoding="utf-8")), cat):
            names = {p.index: p.name for p in m.params}  # list order != param ID (e.g. Fast Gate)
            print(s, m.category, m.name, {names[i]: v for i, v in vals.items()})
        return print("OK")
    dev = connect()
    try:
        if cmd == "patches":
            for i, name in enumerate(patch_names(decode_reply(dev.request_dump(msg_query_inventory("patches"))))):
                print(f"{patch_label(i):7s} {name}")
        elif cmd == "show":
            show(read_patch(dev, args[0]), cat)
        elif cmd == "build":
            build(dev, args[0], json.load(open(args[1], encoding="utf-8")), cat)
        else:
            sys.exit(__doc__)
    finally:
        dev.close()


if __name__ == "__main__":
    main(sys.argv) if len(sys.argv) > 1 else sys.exit(__doc__)
