---
type: research
project: computer-geek
status: done
created: 2026-10-06
---

# Windows: one codebase, the Windows half unproven

Asked for on 2026-09-12; the owner's test plan: write it and mark it. **There is
no Windows fork and must never be one.** Three things differ, each picked at
import from `sys.platform`:

| What | Linux | Windows |
|---|---|---|
| where the game is | the Wine prefix under `~/Games` | `AppPath` from the registry, `Program Files (x86)` as fallback |
| where the saves are | every Wine prefix beside the game | the `Personal` shell folder, because OneDrive moves Documents |
| process memory | `/proc/<pid>/{maps,mem}` | `ReadProcessMemory` and friends |

The rest (save decoder, BINI reader, PE string tables, DPS model, jump graph, job
boards, the page) is plain Python on `os.path`.

**`backend/live/proc.py` is the only code that touches another process.** It
replaced 22 direct `/proc/<pid>/mem` openings across `speed.py`, `inject.py`,
`tradelane.py` and `thrusters.py` with six functions: `find_pid`, `mappings`,
`regions`, `read`, `write`, `chunks`. `mappings` yields `(lo, hi, perms, name)`
with `perms` spelled `rwxp` on both platforms. Proved on the running game: every
`fl.py` live command gave byte-identical output before and after, and each write
path was run with the value already there (`fl.py speed 300`, a thruster set to
its own speed, a POST to `api/allhacks`).

Never run. Three traps return wrong answers instead of errors, so the code is
built around them:

- **Toolhelp cannot list a 32-bit process's modules from 64-bit Python**
  (`TH32CS_SNAPMODULE32` fails with `ERROR_PARTIAL_COPY` across WOW64). Modules
  come from `EnumProcessModulesEx` with `LIST_MODULES_ALL`; Toolhelp still lists
  processes.
- **`MEMORY_BASIC_INFORMATION` is laid out for the caller**: pointer fields
  `c_void_p`, `RegionSize` `c_size_t`.
- **Every function gets `argtypes`**, or ctypes passes a `HANDLE` as a C `int` and
  truncates it on 64-bit.

Windows `write` needs `VirtualProtectEx`: lift protection, write, restore, flush
the instruction cache (or the CPU runs the old byte for a while). This does not
change `find_scratch`: the game's own write into a read-only page still faults.

`check_windows.py` puts Windows-sized types into `ctypes.wintypes`, fakes
`WinDLL`, imports `proc_windows.py` and measures every name, struct size and
offset against the documented numbers, and that every function has `argtypes`
and `restype`. On Linux `wintypes.DWORD` is 8 bytes (4 on Windows) and `c_wchar`
4 (2), so imported as-is `MEMORY_BASIC_INFORMATION` measures 56 bytes instead of
48; `WCHAR` is measured with a two-byte stand-in. It caught `pcPriClassBase` declared `c_long`: `PROCESSENTRY32W` came out 1096
bytes instead of 568. Whether the calls work only Windows can say: `fl.py proc`
asks (pid, modules, sixteen bytes of `common.dll`, nothing written).
