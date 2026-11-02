"""Print everything needed to port one EventFlow handler (formula F1).

  python3 -m acnh_rip.re.evfl_show <Actor.EventFlowActionName> [--all]

Shows the registry params, factory/ctor/vtable and the Ghidra decompilation
(generated/re/decomp/<va>.c, from tools/ghidra_decompile.sh) of the ctor and of
each overridden slot. RTTI/destructor slots are skipped unless --all.
Ghidra names inside the C text are image-base addresses: FUN_00xxxxxx = VA + 0x100000.
"""
import json
import sys

from ..config import OUT

# action slots (from WaitFrame/SetSubflowResult): 0,1,14 RTTI; 2,3 dtor; 8 enter; 9 update; 10 exit
SKIP = {"actions": {0, 1, 2, 3, 14}, "queries": {0, 1, 2, 3, 15}}


def show(name, everything=False):
    vt = json.loads((OUT / "re/evfl_vtables.json").read_text())
    reg = json.loads((OUT / "eventflow/_registry.json").read_text())
    kind = "actions" if "Action" in name.split(".", 1)[1][:16] else "queries"
    rec, info = vt[kind]["entries"].get(name), reg[kind].get(name)
    print(f"# {name}  uses={info and info['uses']}  params={info and info['params']}")
    if not rec:
        print("(no factory/vtable)")
        return
    print(f"# factory={rec['factory']} size={rec['size']} ctor={rec['ctor']} vtable={rec['vtable']}")
    d = OUT / "re/decomp"
    parts = [("ctor", rec["ctor"])] + [(f"slot {s}", a) for s, a in rec["overridden"].items()
                                        if everything or int(s) not in SKIP[kind]]
    for label, a in parts:
        f = d / f"{a}.c"
        print(f"\n//// {label} @ {a}")
        print(f.read_text().strip() if f.exists() else "(not decompiled)")


if __name__ == "__main__":
    show(sys.argv[1], "--all" in sys.argv)
