# ampero-harness

Let Claude build patches on a Hotone Ampero II Stage (Windows), on top of
[jpfaria/hotone-ampero-2](https://github.com/jpfaria/hotone-ampero-2) (pinned commit `740c8a1`, SysEx protocol for firmware V1.7.0).

## Install (once)

```bash
py -3.11 -m venv .venv   # python-rtmidi has no Windows wheel for 3.14 (needs a C++ compiler)
.venv/Scripts/python -m pip install --only-binary python-rtmidi mido python-rtmidi lzokay
.venv/Scripts/python -m pip install --no-deps "git+https://github.com/jpfaria/hotone-ampero-2@740c8a19aa0e7d0b6d098d8fdc599f89e9304a59"
```
`--no-deps` skips `tone-analyzer` (not needed here).

## Use

Close the official Ampero II editor first (Windows MIDI ports are exclusive).

```bash
.venv/Scripts/python amp.py patches                    # list 300 patches (read-only)
.venv/Scripts/python amp.py show A01-1                 # read one patch (read-only)
.venv/Scripts/python amp.py check chains/x.json        # offline validation against the catalog
.venv/Scripts/python amp.py build A57-1 chains/x.json  # write into an EMPTY patch, save, verify
.venv/Scripts/python test_amp.py                       # offline self-check
```

## Workflow

1. User states the target tone, guitar, and monitoring (e.g. headphones).
2. Claude proposes 2-3 chains + guitar knob settings, using only catalog models: sourced record-gear blocks, plus playability blocks for the user's monitoring (gate, delay, reverb for headphones) clearly labelled as unsourced taste.
3. User picks one and adds tweaks.
4. Claude writes `chains/<name>.json`, runs `check`, then `build` into an empty patch.

## Safety rules (enforced in `amp.py`)

- `build` switches to another patch first (reading the current patch returns its edit buffer, not flash), then refuses any target that contains models.
- No Global Settings, uploads, or input-source writes are exposed.
- Every knob/model is validated against the catalog before anything is sent.
- `build` loads another patch first: unsaved edits on the pedal's current patch are discarded.

## Chain file

```json
{"name": "STAIRWAY-B",
 "blocks": [{"slot": 0, "cat": "DYN", "model": "Treble Ranger", "params": {"Gain": 50}},
            {"slot": 4, "cat": "AMP", "model": "Marshell SLP", "params": {"Volume": 65}}]}
```
Slots 0-5 = chain line 1, 6-11 = line 2 (0-based). Unlisted params keep the model defaults.
