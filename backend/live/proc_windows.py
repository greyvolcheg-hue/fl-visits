"""`ReadProcessMemory` and friends. See `proc.py` for the interface.

**Not one line of this has ever run.** It was written against the Win32
documentation on a machine with no Windows on it, in one pass, in September
2026. Treat every function here as a hypothesis. `fl.py proc` exists to test
them: it prints the pid, the modules and sixteen bytes of `common.dll`, writes
nothing, and fails with a sentence rather than a traceback. Run that first.

Three traps are designed around rather than discovered, because each one is the
kind that returns a wrong answer instead of an error:

**1. Modules come from `EnumProcessModulesEx`, not from Toolhelp.**
`CreateToolhelp32Snapshot(TH32CS_SNAPMODULE32)` fails with `ERROR_PARTIAL_COPY`
when a 64-bit process asks about a 32-bit one, and Freelancer is 32-bit while
the Python most people install is 64-bit. `EnumProcessModulesEx` with
`LIST_MODULES_ALL` is the call that works across that boundary. Toolhelp is
still used for the process list, where it has no such problem.

**2. `MEMORY_BASIC_INFORMATION` is laid out for the caller, not the target.**
Its pointer fields are `c_void_p` and its `RegionSize` is `c_size_t`, so the
64-bit build gets the 64-bit layout including the padding the documentation
calls `__alignment1`. Declaring them as `c_uint32` would appear to work on a
32-bit Python and silently read garbage on a 64-bit one.

**3. Every function gets `argtypes`.** Without them ctypes passes a handle as a
C `int`, which truncates a 64-bit `HANDLE` to 32 bits. The call then fails, or
worse, succeeds against nothing.

**Writing needs `VirtualProtectEx` and Linux does not.** `/proc/<pid>/mem`
writes straight through page protection; `WriteProcessMemory` does not, and the
targets here are in `.text` and `.rdata`. So `write` opens the page, writes,
puts the protection back, and flushes the instruction cache. That last step is
not decoration: a patched instruction that is still in the CPU's instruction
cache is the game running the old byte for a while. This is the same dance
flhack does, and the reason `inject.py` says it cannot change protection is
that on Linux it does not have to.

**`find_scratch` is unaffected by any of that and must not be "simplified".**
It exists because the game's own `mov` into a read-only page faults, which is
the game's problem and not ours. Being able to lift the protection from outside
does not make `.text` padding a safe place for the game to write.
"""

import ctypes
from ctypes import wintypes

from .proc import NotRunning, PROCESS

FLAVOUR = "windows ReadProcessMemory"

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_psapi = ctypes.WinDLL("psapi", use_last_error=True)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
WANTED = (PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION
          | PROCESS_VM_READ | PROCESS_VM_WRITE)

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE = ctypes.c_void_p(-1).value
LIST_MODULES_ALL = 0x03

MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
PAGE_GUARD = 0x100
PAGE_EXECUTE_READWRITE = 0x40
# The eight real protections, as the four letters `/proc/<pid>/maps` would use.
# The modifier bits (guard, no-cache, write-combine) are masked off first.
PERMS = {
    0x01: "---",  # NOACCESS
    0x02: "r--",  # READONLY
    0x04: "rw-",  # READWRITE
    0x08: "rw-",  # WRITECOPY, private and writable once written to
    0x10: "--x",  # EXECUTE
    0x20: "r-x",  # EXECUTE_READ
    0x40: "rwx",  # EXECUTE_READWRITE
    0x80: "rwx",  # EXECUTE_WRITECOPY
}

MAX_PATH = 260
# Where to stop walking. Freelancer is a 32-bit program, so its user address
# space ends here whatever the Python looking at it was built as.
TOP = 0x1_0000_0000


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                # `wintypes.LONG`, not `ctypes.c_long`: they are the same
                # four bytes on Windows and are not the same anywhere else,
                # which puts every field after this one in the wrong place
                # when `check_windows.py` measures the struct.
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * MAX_PATH)]


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    """Pointer fields as pointers. See trap 2 in the module docstring."""
    _fields_ = [("BaseAddress", ctypes.c_void_p),
                ("AllocationBase", ctypes.c_void_p),
                ("AllocationProtect", wintypes.DWORD),
                ("RegionSize", ctypes.c_size_t),
                ("State", wintypes.DWORD),
                ("Protect", wintypes.DWORD),
                ("Type", wintypes.DWORD)]


class MODULEINFO(ctypes.Structure):
    _fields_ = [("lpBaseOfDll", ctypes.c_void_p),
                ("SizeOfImage", wintypes.DWORD),
                ("EntryPoint", ctypes.c_void_p)]


_k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_k32.OpenProcess.restype = wintypes.HANDLE
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.CloseHandle.restype = wintypes.BOOL
_k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
_k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
_k32.Process32FirstW.argtypes = [wintypes.HANDLE,
                                 ctypes.POINTER(PROCESSENTRY32W)]
_k32.Process32FirstW.restype = wintypes.BOOL
_k32.Process32NextW.argtypes = [wintypes.HANDLE,
                                ctypes.POINTER(PROCESSENTRY32W)]
_k32.Process32NextW.restype = wintypes.BOOL
_k32.GetProcessTimes.argtypes = [wintypes.HANDLE,
                                 ctypes.POINTER(wintypes.FILETIME),
                                 ctypes.POINTER(wintypes.FILETIME),
                                 ctypes.POINTER(wintypes.FILETIME),
                                 ctypes.POINTER(wintypes.FILETIME)]
_k32.GetProcessTimes.restype = wintypes.BOOL
_k32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                ctypes.POINTER(MEMORY_BASIC_INFORMATION),
                                ctypes.c_size_t]
_k32.VirtualQueryEx.restype = ctypes.c_size_t
_k32.VirtualProtectEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                  ctypes.c_size_t, wintypes.DWORD,
                                  ctypes.POINTER(wintypes.DWORD)]
_k32.VirtualProtectEx.restype = wintypes.BOOL
_k32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                   ctypes.c_void_p, ctypes.c_size_t,
                                   ctypes.POINTER(ctypes.c_size_t)]
_k32.ReadProcessMemory.restype = wintypes.BOOL
_k32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                    ctypes.c_void_p, ctypes.c_size_t,
                                    ctypes.POINTER(ctypes.c_size_t)]
_k32.WriteProcessMemory.restype = wintypes.BOOL
_k32.FlushInstructionCache.argtypes = [wintypes.HANDLE, ctypes.c_void_p,
                                       ctypes.c_size_t]
_k32.FlushInstructionCache.restype = wintypes.BOOL

_psapi.EnumProcessModulesEx.argtypes = [wintypes.HANDLE,
                                        ctypes.POINTER(wintypes.HMODULE),
                                        wintypes.DWORD,
                                        ctypes.POINTER(wintypes.DWORD),
                                        wintypes.DWORD]
_psapi.EnumProcessModulesEx.restype = wintypes.BOOL
_psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE,
                                        wintypes.LPWSTR, wintypes.DWORD]
_psapi.GetModuleFileNameExW.restype = wintypes.DWORD
_psapi.GetModuleInformation.argtypes = [wintypes.HANDLE, wintypes.HMODULE,
                                        ctypes.POINTER(MODULEINFO),
                                        wintypes.DWORD]
_psapi.GetModuleInformation.restype = wintypes.BOOL


# One handle, kept for as long as the pid does not change. A region scan makes
# hundreds of reads and opening the process for each of them would be the whole
# cost of the scan. Replaced rather than accumulated: a second pid closes the
# first handle.
_open = {"pid": None, "handle": None}


def _handle(pid):
    """An open handle to `pid`, with the rights every call here needs."""
    if _open["pid"] == pid and _open["handle"]:
        return _open["handle"]
    handle = _k32.OpenProcess(WANTED, False, pid)
    if not handle:
        err = ctypes.get_last_error()
        extra = (" The game is probably running as administrator, and this "
                 "has to run the same way to reach it." if err == 5 else "")
        raise NotRunning(f"cannot open process {pid}: error {err}.{extra}")
    if _open["handle"]:
        _k32.CloseHandle(_open["handle"])
    _open.update(pid=pid, handle=handle)
    return handle


def _created(pid):
    """When a process started, as a FILETIME, or None if it will not say."""
    try:
        handle = _handle(pid)
    except NotRunning:
        return None
    made = wintypes.FILETIME()
    gone, kernel, user = (wintypes.FILETIME() for _ in range(3))
    if not _k32.GetProcessTimes(handle, ctypes.byref(made), ctypes.byref(gone),
                                ctypes.byref(kernel), ctypes.byref(user)):
        return None
    return (made.dwHighDateTime << 32) | made.dwLowDateTime


def find_pid():
    """PID of the running game, or raise. The newest wins if several match.

    "Newest" is the creation time, not the highest pid: Windows reuses pids and
    does not hand them out in order, so the Linux rule of `max()` would be a
    coin toss here. A process that will not report its times loses to one that
    will, which is the right way round: it is one we cannot open anyway.
    """
    snap = _k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snap == INVALID_HANDLE:
        raise NotRunning("cannot list processes: "
                         f"error {ctypes.get_last_error()}")
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    found = []
    try:
        ok = _k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            if entry.szExeFile.lower() == PROCESS.lower():
                found.append(entry.th32ProcessID)
            ok = _k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        _k32.CloseHandle(snap)
    if not found:
        raise NotRunning("Freelancer is not running")
    return max(found, key=lambda pid: (_created(pid) or 0, pid))


def _modules(pid):
    """{base address: full path} for every module loaded in the process."""
    handle = _handle(pid)
    count = 256
    while True:
        block = (wintypes.HMODULE * count)()
        needed = wintypes.DWORD()
        if not _psapi.EnumProcessModulesEx(handle, block, ctypes.sizeof(block),
                                           ctypes.byref(needed),
                                           LIST_MODULES_ALL):
            raise NotRunning("cannot list the modules: "
                            f"error {ctypes.get_last_error()}")
        got = needed.value // ctypes.sizeof(wintypes.HMODULE)
        if got <= count:
            break
        count = got  # the list grew between the two calls; ask again
    out = {}
    for mod in block[:got]:
        name = ctypes.create_unicode_buffer(MAX_PATH * 2)
        if not _psapi.GetModuleFileNameExW(handle, mod, name, len(name)):
            continue
        info = MODULEINFO()
        if not _psapi.GetModuleInformation(handle, mod, ctypes.byref(info),
                                           ctypes.sizeof(info)):
            continue
        out[info.lpBaseOfDll or 0] = name.value
    return out


def mappings(pid):
    """[(lo, hi, perms, name)], the same shape `/proc/<pid>/maps` gives.

    Only committed pages are listed, because free and reserved ones have no
    contents to read and `/proc` does not list them either. Guard pages are
    left out too: touching one raises an exception **in the game**, which is
    not a cost this tool gets to impose on somebody's flight.
    """
    handle = _handle(pid)
    known = _modules(pid)
    out, addr = [], 0
    info = MEMORY_BASIC_INFORMATION()
    while addr < TOP:
        if not _k32.VirtualQueryEx(handle, ctypes.c_void_p(addr),
                                   ctypes.byref(info), ctypes.sizeof(info)):
            break
        size = info.RegionSize
        if not size:
            break  # nothing more to walk, and without this the loop is forever
        guard = info.Protect & PAGE_GUARD
        if info.State == MEM_COMMIT and not guard:
            perms = PERMS.get(info.Protect & 0xFF, "---")
            # The fourth letter is private-or-shared. Nothing here reads it;
            # it is there so a printed mapping looks like the Linux one.
            perms += "p" if info.Type == MEM_PRIVATE else "s"
            out.append((addr, addr + size, perms,
                        known.get(info.AllocationBase or 0, "")))
        addr += size
    return out


def read(pid, addr, count):
    """`count` bytes at `addr`, or fewer. Raises `OSError` when unreadable.

    A read that crosses into an unmapped page comes back as
    `ERROR_PARTIAL_COPY` with the bytes it did manage, which is exactly the
    short read the Linux side produces, so it is passed on the same way. Only a
    read that got nothing at all is an error.
    """
    if count <= 0:
        return b""  # `create_string_buffer(0)` raises, and `/proc` gives b""
    buf = ctypes.create_string_buffer(count)
    got = ctypes.c_size_t(0)
    ok = _k32.ReadProcessMemory(_handle(pid), ctypes.c_void_p(addr), buf,
                                count, ctypes.byref(got))
    if not ok and not got.value:
        raise OSError(ctypes.get_last_error(),
                      f"cannot read {count} bytes at {addr:#x}")
    return buf.raw[:got.value]


def write(pid, addr, data):
    """Write, putting the page's protection back exactly as it was.

    Unlike `/proc/<pid>/mem`, `WriteProcessMemory` respects page protection and
    every target here is in a read-only section, so the protection comes off
    and goes back on around the write. The instruction cache flush matters for
    the ones in `.text`: without it the game can go on running the byte that
    was there.

    Says nothing about whether the write took. Every caller reads back and
    compares, which is the check that actually means something.
    """
    size = len(data)
    handle = _handle(pid)
    old = wintypes.DWORD(0)
    lifted = _k32.VirtualProtectEx(handle, ctypes.c_void_p(addr), size,
                                   PAGE_EXECUTE_READWRITE, ctypes.byref(old))
    try:
        put = ctypes.c_size_t(0)
        if not _k32.WriteProcessMemory(handle, ctypes.c_void_p(addr), data,
                                       size, ctypes.byref(put)):
            raise OSError(ctypes.get_last_error(),
                          f"cannot write {size} bytes at {addr:#x}")
    finally:
        if lifted:
            back = wintypes.DWORD(0)
            _k32.VirtualProtectEx(handle, ctypes.c_void_p(addr), size,
                                  old.value, ctypes.byref(back))
    _k32.FlushInstructionCache(handle, ctypes.c_void_p(addr), size)


def chunks(pid, lo, hi, overlap=0, span=1 << 20):
    """Walk a mapping a megabyte at a time, overlapping so runs are not split.

    The same walk the Linux side does, over `read` instead of over one open
    file: there is no file here, and a handle is already being held.
    """
    pos = lo
    while pos < hi:
        end = min(pos + span, hi)
        try:
            buf = read(pid, pos, end - pos)
        except OSError:
            return
        if not buf:
            return
        yield pos, buf
        pos = end - overlap if end < hi else end
