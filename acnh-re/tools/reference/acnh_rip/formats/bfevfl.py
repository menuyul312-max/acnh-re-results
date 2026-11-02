"""BFEVFL (EventFlow, version 3) reader.

File header: 0x20 u16 flowchart count, 0x22 u16 timeline count,
             0x28 flowchart pointer array.  Pointers are file-relative.
Flowchart "EVFL": 0x10 u16 actors, u16 actions, u16 queries, u16 events,
             0x18 u16 entry points; 0x20 name, 0x28 actors (0x38 each),
             0x30 events (0x28 each), 0x38 entry point dict, 0x40 entry points
Actor (0x38): name, secondary name, argument name, actions[], queries[],
             params, u16 n_actions, u16 n_queries, u16 entry point idx, u8 cut
Event (0x28): name, u8 type @+8 (0 action, 1 switch, 2 fork, 3 join, 4 subflow);
             switch cases are 8 bytes (u32 value, u16 event)
Strings are u16-length-prefixed (like BFRES).  Layouts were mapped from the
game's files (see tools/README.md) and validated by index range checks.
"""
import struct

from .bfres import Reader

EVENT_TYPES = ["action", "switch", "fork", "join", "subflow"]
NONE16 = 0xFFFF


def _container(r, p, depth=0):
    """Parameter container (type @+0: 0 arg, 1 container, 2 int, 3 bool, 4 float,
    5 string, 6 wstring, 7 int[], 8 bool[], 9 float[], 10 string[], 11 wstring[], 12 actor id)."""
    if p == 0 or depth > 8:
        return None
    t, n, dic = r.u8(p), r.u16(p + 2), r.u64(p + 8)
    v = p + 0x10
    if t == 1:
        keys = r.dict_keys(dic)
        return {keys[i] if i < len(keys) else f"#{i}": _container(r, r.u64(v + i * 8), depth + 1)
                for i in range(n)}
    if t in (0, 5):
        s = r.str_at(v)
        return {"$arg": s} if t == 0 else s
    if t == 2:
        return r.s32(v)
    if t == 3:
        return r.u32(v) != 0
    if t == 4:
        return r.f32(v)
    if t == 7:
        return [r.s32(v + i * 4) for i in range(n)]
    if t == 8:
        return [r.u32(v + i * 4) != 0 for i in range(n)]
    if t == 9:
        return [r.f32(v + i * 4) for i in range(n)]
    if t == 10:
        return [r.str_at(v + i * 8) for i in range(n)]
    if t == 12:
        return {"$actor": r.str_at(v), "$sub": r.str_at(v + 8)}
    return {"$type": t, "$raw": r.b[p:p + 0x20].hex()}


def _flowchart(r, fc):
    if r.b[fc:fc + 4] != b"EVFL":
        raise ValueError("EVFL expected")
    n_act, _, _, n_ev, n_ep = struct.unpack_from("<5H", r.b, fc + 0x10)
    out = {"name": r.str_at(fc + 0x20), "actors": [], "events": [], "entry_points": {}}
    for i in range(n_act):
        a = r.u64(fc + 0x28) + i * 0x38
        na, nq, epi = r.u16(a + 0x30), r.u16(a + 0x32), r.u16(a + 0x34)
        out["actors"].append({
            "name": r.str_at(a), "secondary": r.str_at(a + 8), "argument": r.str_at(a + 0x10),
            "actions": [r.str_at(r.u64(a + 0x18) + k * 8) for k in range(na)],
            "queries": [r.str_at(r.u64(a + 0x20) + k * 8) for k in range(nq)],
            "params": _container(r, r.u64(a + 0x28)),
            "entry_point": None if epi == NONE16 else epi,
        })
    for i in range(n_ev):
        e = r.u64(fc + 0x30) + i * 0x28
        t = r.u8(e + 8)
        ev = {"name": r.str_at(e), "type": EVENT_TYPES[t] if t < 5 else t}
        if t == 0:
            ev.update(next=r.u16(e + 0x0A), actor=r.u16(e + 0x0C), action=r.u16(e + 0x0E),
                      params=_container(r, r.u64(e + 0x10)))
        elif t == 1:
            nc = r.u16(e + 0x0A)
            ev.update(actor=r.u16(e + 0x0C), query=r.u16(e + 0x0E), params=_container(r, r.u64(e + 0x10)),
                      # case = (u32 value, u16 event, u16 pad): 8 bytes
                      cases=[{"value": r.u32(r.u64(e + 0x18) + k * 8),
                              "event": r.u16(r.u64(e + 0x18) + k * 8 + 4)} for k in range(nc)])
        elif t == 2:
            nf = r.u16(e + 0x0A)
            ev.update(join=r.u16(e + 0x0C), forks=[r.u16(r.u64(e + 0x10) + k * 2) for k in range(nf)])
        elif t == 3:
            ev.update(next=r.u16(e + 0x0A))
        elif t == 4:
            ev.update(next=r.u16(e + 0x0A), params=_container(r, r.u64(e + 0x10)),
                      flowchart=r.str_at(e + 0x18), entry_point=r.str_at(e + 0x20))
        for k in ("next", "join"):
            if ev.get(k) == NONE16:
                ev[k] = None
        out["events"].append(ev)
    names = r.dict_keys(r.u64(fc + 0x38))
    for i in range(n_ep):
        p = r.u64(fc + 0x40) + i * 0x20
        nsub, nvar, main = r.u16(p + 0x18), r.u16(p + 0x1A), r.u16(p + 0x1C)
        out["entry_points"][names[i] if i < len(names) else f"#{i}"] = {
            "main_event": None if main == NONE16 else main,
            "sub_flow_events": [r.u16(r.u64(p) + k * 2) for k in range(nsub)],
            "variable_count": nvar,
        }
    return out


def read_bfevfl(data: bytes):
    if data[:6] != b"BFEVFL":
        raise ValueError("not BFEVFL")
    r = Reader(data)
    n_fc = r.u16(0x20)
    return {"flowcharts": [_flowchart(r, r.u64(r.u64(0x28) + i * 8)) for i in range(n_fc)],
            "timeline_count": r.u16(0x22)}


def validate(doc):
    """Return a list of problems (index out of range etc.)."""
    errs = []
    for fc in doc["flowcharts"]:
        ne, na = len(fc["events"]), len(fc["actors"])
        for i, ev in enumerate(fc["events"]):
            for k in ("next", "join"):
                if ev.get(k) is not None and ev[k] >= ne:
                    errs.append(f"{fc['name']}#{i} {k}={ev[k]}")
            if "actor" in ev:
                if ev["actor"] >= na:
                    errs.append(f"{fc['name']}#{i} actor={ev['actor']}")
                else:
                    a = fc["actors"][ev["actor"]]
                    if ev["type"] == "action" and ev["action"] >= len(a["actions"]):
                        errs.append(f"{fc['name']}#{i} action idx")
                    if ev["type"] == "switch" and ev["query"] >= len(a["queries"]):
                        errs.append(f"{fc['name']}#{i} query idx")
            for c in ev.get("cases", []):
                if c["event"] >= ne:
                    errs.append(f"{fc['name']}#{i} case->{c['event']}")
            for f in ev.get("forks", []):
                if f >= ne:
                    errs.append(f"{fc['name']}#{i} fork->{f}")
        for n, ep in fc["entry_points"].items():
            if ep["main_event"] is not None and ep["main_event"] >= ne:
                errs.append(f"{fc['name']} entry {n}")
    return errs
