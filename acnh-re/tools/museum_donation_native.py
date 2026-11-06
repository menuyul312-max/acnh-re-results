"""Native registration/dispatch check for DonationCheckItemType (0x3d9ab0).

The constructor and the empty-context branch of its virtual predicate run from
the original ExeFS main in tools/nso_sandbox.py.  Only the base-object setup
and registration helper are stubbed; the predicate itself runs in native code.
This deliberately does not claim to verify positive item-type eligibility.

Usage: PYTHONPATH=/workspace/acnh-re/.deps python3 tools/museum_donation_native.py
"""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nso_sandbox import Sandbox, DEFAULT_NSO, NSO_SHA256  # noqa: E402


CTOR = 0x3d9ab0
PREDICATE = 0x3d9b60
BASE_INIT = 0x455f90
REGISTER = 0x4624d0
HANDLER_NAME = b"DonationCheckItemType"
HANDLER_NAME_VA = 0x298d4ef


def verify():
    image_sha256 = hashlib.sha256(Path(DEFAULT_NSO).read_bytes()).hexdigest()
    if image_sha256 != NSO_SHA256:
        raise AssertionError(f"unexpected ExeFS main hash: {image_sha256}")

    sb = Sandbox()
    obj = sb.alloc(0x200)
    base_calls = []
    registrations = []

    # These are generic object lifecycle/registration helpers. The
    # DonationCheckItemType constructor body still executes from the NSO.
    sb.stub(BASE_INIT, lambda state: base_calls.append(state.reg("x0")) or 0)
    sb.stub(REGISTER, lambda state: registrations.append(state.reg("x0")) or 0)
    sb.call(CTOR, (obj,))

    vtable = sb.u64(obj)
    registered_name_ptr = sb.u64(obj + 0xc8)
    registered_name = sb.read(registered_name_ptr, len(HANDLER_NAME) + 1).split(b"\0", 1)[0]
    predicate = sb.u64(vtable + 0x30)
    callback_arg = registrations[0] if registrations else None

    assert len(base_calls) == 1 and base_calls[0] == obj
    assert registered_name_ptr == HANDLER_NAME_VA
    assert registered_name == HANDLER_NAME
    assert callback_arg == obj + 0xb8
    assert predicate == PREDICATE

    # Native method 0x3d9b60 returns false when the evaluation context at
    # object+8 is null. This exercises its first real branch without inventing
    # a fake save/selection context for the more involved item checks.
    no_context = sb.call(predicate, (obj,))
    assert no_context == 0

    return {
        "meta": {
            "source": f"ExeFS main sha256 {image_sha256}",
            "runner": "tools/museum_donation_native.py",
            "harness": "tools/nso_sandbox.py (Unicorn AArch64)",
            "controlled_calls": {
                hex(BASE_INIT): "base object initializer",
                hex(REGISTER): "registration callback; records its native argument",
            },
            "native_calls": [hex(CTOR), hex(PREDICATE)],
        },
        "cases": {
            "DonationCheckItemType constructor registration": {
                "pass": True,
                "object_name": registered_name.decode("ascii"),
                "name_pointer": hex(registered_name_ptr),
                "name_field_offset": "0xc8",
                "registration_argument": hex(callback_arg),
                "registration_argument_offset": "object+0xb8",
                "vtable": hex(vtable),
                "predicate_vtable_offset": "0x30",
                "predicate": hex(predicate),
            },
            "predicate with null evaluation context": {
                "pass": True,
                "context_field_offset": "0x8",
                "native_return": no_context,
                "meaning": "false; the native predicate exits before item checks",
            },
        },
        "limitations": [
            "Positive eligibility for individual ItemKind values is not exercised; it requires a non-null live selection context and several native item/save accessors.",
            "This check does not verify donation bit writers, fossil assessment, MuseumDonationNumCheck, museum construction, or FishStatusParam.OpenDonatedNum.",
        ],
    }


def main():
    result = verify()
    out = Path(os.environ.get("ACNH_RE_OUTPUT", ROOT / "output")) / "gameplay" / "museum_donation_followup" / "native.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(out)
    print(json.dumps(result["cases"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
