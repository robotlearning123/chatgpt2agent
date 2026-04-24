# Ported from lanqian528/chat2api (MIT). See NOTICES.md.

from __future__ import annotations

import base64
import json
import random
import time
from typing import Any, Callable, Dict, List, Union


class OrderedMap:
    def __init__(self):
        self.keys: list = []
        self.values: dict = {}

    def add(self, key: str, value: Any):
        if key not in self.values:
            self.keys.append(key)
        self.values[key] = value

    def to_json(self):
        return json.dumps({k: self.values[k] for k in self.keys})


TurnTokenList = List[List[Any]]
FloatMap = Dict[float, Any]
StringMap = Dict[str, Any]
FuncType = Callable[..., Any]

_start_time = 0.0


def _get_turnstile_token(dx: str, p: str) -> Union[str, None]:
    try:
        decoded = base64.b64decode(dx)
        return _xor(decoded.decode(), p)
    except Exception:
        return None


def _xor(dx: str, p: str) -> str:
    p_len = len(p)
    if p_len == 0:
        return dx
    out = []
    for i, r in enumerate(dx):
        out.append(chr(ord(r) ^ ord(p[i % p_len])))
    return "".join(out)


def _is_slice(x: Any) -> bool:
    return isinstance(x, (list, tuple))


def _is_float(x: Any) -> bool:
    return isinstance(x, float)


def _is_string(x: Any) -> bool:
    return isinstance(x, str)


def _to_str(v: Any) -> str:
    if v is None:
        return "undefined"
    if _is_float(v):
        return str(v)
    if _is_string(v):
        special = {
            "window.Math": "[object Math]",
            "window.Reflect": "[object Reflect]",
            "window.performance": "[object Performance]",
            "window.localStorage": "[object Storage]",
            "window.Object": "function Object() { [native code] }",
            "window.Reflect.set": "function set() { [native code] }",
            "window.performance.now": "function () { [native code] }",
            "window.Object.create": "function create() { [native code] }",
            "window.Object.keys": "function keys() { [native code] }",
            "window.Math.random": "function random() { [native code] }",
        }
        return special.get(v, v)
    if isinstance(v, list) and all(isinstance(i, str) for i in v):
        return ",".join(v)
    return str(v)


def _build_func_map() -> FloatMap:
    pm: FloatMap = {}

    def f1(e, t):
        pm[e] = _xor(_to_str(pm[e]), _to_str(pm[t]))

    def f2(e, t):
        pm[e] = t

    def f5(e, t):
        n = pm[e]
        tres = pm[t]
        if _is_slice(n):
            pm[e] = n + [tres]
        else:
            if _is_string(n) or _is_string(tres):
                pm[e] = _to_str(n) + _to_str(tres)
            elif _is_float(n) and _is_float(tres):
                pm[e] = n + tres
            else:
                pm[e] = "NaN"

    def f6(e, t, n):
        tv = pm[t]
        nv = pm[n]
        if _is_string(tv) and _is_string(nv):
            res = f"{tv}.{nv}"
            pm[e] = "https://chatgpt.com/" if res == "window.document.location" else res

    def f24(e, t, n):
        tv = pm[t]
        nv = pm[n]
        if _is_string(tv) and _is_string(nv):
            pm[e] = f"{tv}.{nv}"

    def f7(e, *args):
        n = [pm[a] for a in args]
        ev = pm[e]
        if isinstance(ev, str):
            if ev == "window.Reflect.set":
                obj = n[0]
                obj.add(str(n[1]), n[2])
        elif callable(ev):
            ev(*n)

    def f17(e, t, *args):
        i = [pm[a] for a in args]
        tv = pm[t]
        res = None
        if isinstance(tv, str):
            if tv == "window.performance.now":
                now_ns = time.time_ns()
                elapsed = now_ns - int(_start_time * 1e9)
                res = (elapsed + random.random()) / 1e6
            elif tv == "window.Object.create":
                res = OrderedMap()
            elif tv == "window.Object.keys":
                if isinstance(i[0], str) and i[0] == "window.localStorage":
                    res = [
                        "STATSIG_LOCAL_STORAGE_INTERNAL_STORE_V4",
                        "STATSIG_LOCAL_STORAGE_STABLE_ID",
                        "client-correlated-secret",
                        "oai/apps/capExpiresAt",
                        "oai-did",
                        "STATSIG_LOCAL_STORAGE_LOGGING_REQUEST",
                        "UiState.isNavigationCollapsed.1",
                    ]
            elif tv == "window.Math.random":
                res = random.random()
        elif callable(tv):
            res = tv(*i)
        pm[e] = res

    def f8(e, t):
        pm[e] = pm[t]

    def f14(e, t):
        tv = pm[t]
        if _is_string(tv):
            pm[e] = json.loads(tv)

    def f15(e, t):
        pm[e] = json.dumps(pm[t])

    def f18(e):
        pm[e] = base64.b64decode(_to_str(pm[e])).decode()

    def f19(e):
        pm[e] = base64.b64encode(_to_str(pm[e]).encode()).decode()

    def f20(e, t, n, *args):
        o = [pm[a] for a in args]
        if pm[e] == pm[t]:
            nv = pm[n]
            if callable(nv):
                nv(*o)

    def f21(*args):
        pass

    def f23(e, t, *args):
        i = list(args)
        if pm[e] is not None and callable(pm[t]):
            pm[t](*i)

    pm.update(
        {
            1: f1,
            2: f2,
            5: f5,
            6: f6,
            24: f24,
            7: f7,
            17: f17,
            8: f8,
            10: "window",
            14: f14,
            15: f15,
            18: f18,
            19: f19,
            20: f20,
            21: f21,
            23: f23,
        }
    )
    return pm


def solve_turnstile(dx: str, p: str) -> Union[str, None]:
    global _start_time
    _start_time = time.time()
    tokens = _get_turnstile_token(dx, p)
    if tokens is None:
        return None
    try:
        token_list = json.loads(tokens)
    except Exception:
        return None

    res = ""
    pm = _build_func_map()

    def f3(e: str):
        nonlocal res
        res = base64.b64encode(e.encode()).decode()

    pm[3] = f3
    pm[9] = token_list
    pm[16] = p

    for token in token_list:
        try:
            e = token[0]
            t = token[1:]
            f = pm.get(e)
            if callable(f):
                f(*t)
        except Exception:
            continue

    return res or None
