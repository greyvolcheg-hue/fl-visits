#!/usr/bin/env python3
"""Check as much of the Windows process layer as a Linux box can check.

    python3 check_windows.py

`backend/live/proc_windows.py` cannot run here and has never run anywhere. What
*can* be settled without Windows is everything that is a fact about C layout
and about names, which is where the expensive mistakes in ctypes code live:

  1. every `wintypes.X` and every `ctypes` name the module uses exists;
  2. every `Structure` it declares builds, and comes out the size and shape the
     Win32 documentation gives for a program of this bit width;
  3. every imported function has `argtypes` and `restype` set, because a
     missing `argtypes` truncates a 64-bit HANDLE to a C `int` and the call
     then fails against nothing;
  4. the page protection table covers all eight protections.

**`ctypes.wintypes` imports on Linux and lies about sizes**, which is the trap
this check exists to avoid falling into itself: `wintypes.DWORD` is
`c_ulong`, which is 4 bytes on Windows and **8 on 64-bit Linux**. Imported
as-is, `MEMORY_BASIC_INFORMATION` comes out 56 bytes here and 48 on the machine
that matters, and a check that accepted 56 would be reporting on a struct that
does not exist. So the Windows-sized types are put back first, and the sizes
asserted below are the documented Windows ones.

What this does **not** check is whether the Win32 calls do what the module
thinks they do. Only Windows can answer that, and `fl.py proc` is the command
that asks it.
"""

import ctypes
import os
import sys
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- put the Windows sizes back ------------------------------------------
wintypes.DWORD = ctypes.c_uint32
wintypes.BOOL = ctypes.c_int32
wintypes.LONG = ctypes.c_int32
wintypes.HANDLE = ctypes.c_void_p
wintypes.HMODULE = ctypes.c_void_p
wintypes.LPWSTR = ctypes.c_wchar_p
# **A two-byte stand-in for `WCHAR`, on purpose.** `ctypes.c_wchar` follows the
# host: two bytes on Windows, four on Linux, which would put 1040 bytes of
# `szExeFile` into a struct that holds 520 and move nothing else in a way worth
# reading. This check measures offsets and never reads the field, so the width
# is what matters and the text is not.
wintypes.WCHAR = ctypes.c_uint16


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD),
                ("dwHighDateTime", wintypes.DWORD)]


wintypes.FILETIME = FILETIME


class _Fn:
    """Stands in for a function `WinDLL` would have resolved."""

    def __init__(self, name):
        self.name, self.argtypes, self.restype = name, None, None

    def __call__(self, *args):
        raise RuntimeError(f"{self.name} cannot be called off Windows")


class _DLL:
    def __init__(self, name, **_kw):
        self.name, self.fns = name, {}

    def __getattr__(self, item):
        return self.fns.setdefault(item, _Fn(item))


def main():
    ctypes.WinDLL = _DLL  # must be in place before the module is imported
    from backend.live import proc_windows as w

    bits = ctypes.sizeof(ctypes.c_void_p) * 8
    # The documented sizes, per program bit width. This check is only as good
    # as the host's pointer size: run it on a 64-bit box and it settles the
    # 64-bit layout, which is the one nearly everybody will be running.
    want = {64: {"MEMORY_BASIC_INFORMATION": 48, "PROCESSENTRY32W": 568,
                 "MODULEINFO": 24},
            32: {"MEMORY_BASIC_INFORMATION": 28, "PROCESSENTRY32W": 556,
                 "MODULEINFO": 12}}[bits]
    # Where the fields the code reads have to land, 64-bit only, straight out
    # of the documentation including the two padding fields it names.
    offsets = {64: {"BaseAddress": 0, "AllocationBase": 8,
                    "AllocationProtect": 16, "RegionSize": 24, "State": 32,
                    "Protect": 36, "Type": 40}}.get(bits)

    bad = []
    print(f"checking a {bits}-bit layout\n")
    for name, size in sorted(want.items()):
        got = ctypes.sizeof(getattr(w, name))
        ok = got == size
        bad += [] if ok else [f"{name} is {got} bytes, should be {size}"]
        print(f"  {'ok  ' if ok else 'FAIL'} {name:<28} {got} bytes")

    if offsets:
        for field, at in offsets.items():
            got = getattr(w.MEMORY_BASIC_INFORMATION, field).offset
            ok = got == at
            bad += [] if ok else [f"MBI.{field} at {got}, should be {at}"]
            print(f"  {'ok  ' if ok else 'FAIL'} MBI.{field:<24} offset {got}")

    for dll in (w._k32, w._psapi):
        for name, fn in sorted(dll.fns.items()):
            ok = fn.argtypes is not None and fn.restype is not None
            bad += [] if ok else [f"{dll.name}.{name} has no argtypes/restype"]
            print(f"  {'ok  ' if ok else 'FAIL'} {dll.name}.{name}")

    missing = [p for p in (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80)
               if p not in w.PERMS]
    bad += [f"no perms for protection {p:#x}" for p in missing]
    print(f"  {'ok  ' if not missing else 'FAIL'} all eight page protections")

    print()
    if bad:
        sys.exit("\n".join(bad))
    print("layout and symbols check out. Whether the calls work is a question "
          "only Windows can answer: run `fl.py proc` there.")


if __name__ == "__main__":
    main()
