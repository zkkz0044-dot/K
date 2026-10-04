#!/usr/bin/env python3
import hashlib
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time

BRIDGE = pathlib.Path('/root/.local/lib/kk-f-bridge/bridge.py')
PIDFILE = pathlib.Path('/root/.local/lib/kk-f-bridge/bridge.pid')
LOGFILE = pathlib.Path('/root/.local/lib/kk-f-bridge/bridge.log')
MARKER = '# KK_F_BOOTSTRAP_HOST_PROBE_V02'

HOST_PROBE_CODE = r'''
# KK_F_BOOTSTRAP_HOST_PROBE_V02
HOST_CMD_OUTPUT = 32768
HOST_PROBES = {
    "systemd": [
        ["/usr/bin/systemctl", "--version"],
        ["/usr/bin/systemctl", "is-system-running"],
    ],
    "services": [["/usr/bin/systemctl", "list-units", "--type=service", "--all", "--no-pager"]],
    "timers": [["/usr/bin/systemctl", "list-timers", "--all", "--no-pager"]],
    "ports": [["/usr/bin/ss", "-lntup"]],
    "processes": [["/usr/bin/ps", "-eo", "pid,ppid,user,stat,etimes,comm", "--sort=pid"]],
    "time": [
        ["/usr/bin/date", "-Is"],
        ["/usr/bin/date", "-u", "-Is"],
        ["/usr/bin/timedatectl"],
    ],
    "network": [
        ["/usr/bin/hostname", "-I"],
        ["/usr/sbin/ip", "-brief", "address"],
        ["/usr/sbin/ip", "route"],
        ["/usr/sbin/ip", "route", "get", "1.1.1.1"],
        ["/usr/bin/getent", "hosts", "exampleprovider.com"],
    ],
    "mounts": [
        ["/usr/bin/findmnt"],
        ["/usr/bin/mount"],
    ],
    "journald": [
        ["/usr/bin/systemctl", "status", "systemd-journald", "--no-pager"],
        ["/usr/bin/journalctl", "--disk-usage"],
    ],
    "cgroups": [
        ["/usr/bin/cat", "/proc/self/cgroup"],
        ["/usr/bin/findmnt", "-t", "cgroup,cgroup2"],
        ["/usr/bin/lsns"],
    ],
    "capabilities": [
        ["/usr/sbin/capsh", "--print"],
    ],
    "reboot": [
        ["/usr/bin/who", "-b"],
        ["/usr/bin/last", "-x", "reboot", "-n", "20"],
        ["/usr/bin/uptime"],
    ],
    "disk": [
        ["/usr/bin/df", "-hT"],
        ["/usr/bin/df", "-i"],
        ["/usr/bin/lsblk", "-f"],
    ],
    "security": [
        ["/usr/sbin/sysctl", "kernel.unprivileged_userns_clone", "fs.protected_hardlinks", "fs.protected_symlinks", "kernel.yama.ptrace_scope"],
    ],
    "firewall": [
        ["/usr/sbin/nft", "list", "ruleset"],
        ["/usr/sbin/ufw", "status", "verbose"],
    ],
}

def _host_command(argv):
    exe = pathlib.Path(argv[0])
    if not exe.is_absolute():
        raise ValueError("host probe executable must be absolute")
    if not exe.exists():
        return {"argv": argv, "missing": True, "exit_code": None, "stdout": "", "stderr": ""}
    started = time.monotonic()
    try:
        cp = subprocess.run(
            argv,
            cwd="/",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            timeout=20,
            env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
        return {
            "argv": argv,
            "missing": False,
            "exit_code": cp.returncode,
            "stdout": redact(cp.stdout[-HOST_CMD_OUTPUT:]),
            "stderr": redact(cp.stderr[-HOST_CMD_OUTPUT:]),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except subprocess.TimeoutExpired as e:
        return {
            "argv": argv,
            "missing": False,
            "timed_out": True,
            "exit_code": None,
            "stdout": redact((e.stdout or "")[-HOST_CMD_OUTPUT:]),
            "stderr": redact((e.stderr or "")[-HOST_CMD_OUTPUT:]),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

def action_host_probe(payload):
    probe = payload.get("probe")
    if not isinstance(probe, str) or probe not in HOST_PROBES:
        raise ValueError("unknown host probe")
    results = [_host_command(argv) for argv in HOST_PROBES[probe]]
    extra = {}
    if probe == "capabilities":
        try:
            lines = pathlib.Path("/proc/self/status").read_text(errors="replace").splitlines()
            extra["bridge_proc_status"] = [line for line in lines if line.startswith(("CapInh:","CapPrm:","CapEff:","CapBnd:","CapAmb:","NoNewPrivs:","Seccomp:"))]
        except Exception as e:
            extra["bridge_proc_status_error"] = f"{type(e).__name__}: {e}"
    return {"probe": probe, "results": results, **extra}

'''

def fsync_dir(p: pathlib.Path):
    fd = os.open(str(p), os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)

def main():
    src = BRIDGE.read_text(encoding='utf-8')
    if '"X-KK-F-Token": TOKEN,' not in src:
        raise SystemExit('REFUSE: expected v2 auth header not found')

    old_hash = hashlib.sha256(src.encode()).hexdigest()
    changed = False
    if MARKER not in src:
        marker = 'ACTIONS = {\n'
        if marker not in src:
            raise SystemExit('REFUSE: ACTIONS marker not found')
        src = src.replace(marker, HOST_PROBE_CODE + marker, 1)
        dict_target = '    "stat": action_stat,\n}'
        if dict_target not in src:
            raise SystemExit('REFUSE: ACTIONS stat target not found')
        src = src.replace(dict_target, '    "stat": action_stat,\n    "host_probe": action_host_probe,\n}', 1)
        changed = True

    compile(src, str(BRIDGE), 'exec')
    new_hash = hashlib.sha256(src.encode()).hexdigest()

    if changed:
        backup = BRIDGE.with_name(f'bridge.py.bak.{int(time.time())}.{old_hash[:12]}')
        backup.write_bytes(BRIDGE.read_bytes())
        os.chmod(backup, 0o600)
        fd, tmp = tempfile.mkstemp(prefix='.bridge-v02-', dir=str(BRIDGE.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(src)
                f.flush()
                os.fsync(f.fileno())
            os.chmod(tmp, 0o700)
            os.replace(tmp, BRIDGE)
            fsync_dir(BRIDGE.parent)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        print(f'PATCHED old_sha256={old_hash} new_sha256={new_hash} backup={backup}')
    else:
        print(f'ALREADY_PATCHED sha256={new_hash}')

    old_pid = None
    try:
        old_pid = int(PIDFILE.read_text().strip())
    except Exception:
        pass
    if old_pid:
        try:
            os.kill(old_pid, signal.SIGTERM)
            deadline = time.time() + 5
            while time.time() < deadline:
                try:
                    os.kill(old_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
            else:
                os.kill(old_pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    with open(LOGFILE, 'ab', buffering=0) as log, open(os.devnull, 'rb') as devnull:
        proc = subprocess.Popen([sys.executable, str(BRIDGE)], stdin=devnull, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, cwd='/root/K/F')
    tmp_pid = PIDFILE.with_suffix('.pid.tmp')
    tmp_pid.write_text(str(proc.pid) + '\n')
    os.chmod(tmp_pid, 0o600)
    os.replace(tmp_pid, PIDFILE)
    fsync_dir(PIDFILE.parent)
    time.sleep(4)
    if proc.poll() is not None:
        raise SystemExit(f'RESTART_FAILED exit={proc.returncode}; inspect {LOGFILE}')
    print(f'BRIDGE_V02_RUNNING pid={proc.pid} sha256={new_hash}')

if __name__ == '__main__':
    main()
