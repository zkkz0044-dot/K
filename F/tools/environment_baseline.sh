#!/usr/bin/env bash
set -u
ROOT="/root/K/F"
OUT="$ROOT/evidence/environment-baseline"
mkdir -p "$OUT"
run() { local name="$1"; shift; { echo "# UTC $(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "# CMD: $*"; "$@"; rc=$?; echo; echo "# EXIT_CODE=$rc"; } >"$OUT/${name}.txt" 2>&1; }
run_sh() { local name="$1"; shift; local cmd="$*"; { echo "# UTC $(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "# CMD: $cmd"; bash -lc "$cmd"; rc=$?; echo; echo "# EXIT_CODE=$rc"; } >"$OUT/${name}.txt" 2>&1; }
run 01_hostname hostname
run_sh 02_hostnamectl 'hostnamectl 2>&1 || true'
run_sh 03_os_kernel_arch 'cat /etc/os-release; echo; uname -a; echo; uname -m'
run_sh 04_cpu 'lscpu; echo; nproc --all'
run_sh 05_memory_swap 'free -h; echo; cat /proc/meminfo; echo; swapon --show || true'
run_sh 06_disk_filesystems 'df -hT; echo; df -i; echo; lsblk -f; echo; findmnt'
run_sh 07_systemd 'systemctl --version; echo; systemctl is-system-running || true'
run_sh 08_runtimes 'python3 --version 2>&1; node --version 2>&1; npm --version 2>&1; git --version 2>&1; codex --version 2>&1'
run_sh 09_identity 'id; echo; whoami; echo; getent passwd; echo; getent group'
run_sh 10_cgroups_namespaces 'mount | grep -E "cgroup|cgroup2" || true; echo; cat /proc/self/cgroup; echo; lsns 2>&1 || true; echo; sysctl user.max_user_namespaces 2>&1 || true'
run_sh 11_capabilities 'command -v capsh && capsh --print || true; echo; grep -E "^(Cap(Inh|Prm|Eff|Bnd|Amb)|NoNewPrivs|Seccomp):" /proc/self/status || true'
run_sh 12_journald 'systemctl status systemd-journald --no-pager 2>&1 || true; echo; journalctl --disk-usage 2>&1 || true'
run_sh 13_listening_ports 'ss -lntup 2>&1 || netstat -lntup 2>&1 || true'
run_sh 14_services 'systemctl list-units --type=service --all --no-pager 2>&1 || true'
run_sh 15_timers_cron 'systemctl list-timers --all --no-pager 2>&1 || true; echo "--- /etc/crontab ---"; cat /etc/crontab 2>&1 || true; echo "--- cron dirs ---"; find /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/cron.weekly /etc/cron.monthly -maxdepth 2 -type f -print 2>/dev/null || true; echo "--- root crontab ---"; crontab -l 2>&1 || true'
run_sh 16_processes 'ps auxww'
run_sh 17_time_ntp 'date -Is; date -u -Is; echo; timedatectl 2>&1 || true'
run_sh 18_boot_history 'who -b 2>&1 || true; echo; last -x reboot -n 20 2>&1 || true; echo; uptime'
run_sh 19_network 'hostname -I 2>&1 || true; echo; ip -brief address 2>&1 || true; echo; ip route 2>&1 || true; echo; ip route get 1.1.1.1 2>&1 || true; echo; getent hosts exampleprovider.com 2>&1 || true'
run_sh 20_legacy_components 'find /root /opt /usr/local /etc/systemd -maxdepth 6 \( -iname "*kk*" -o -iname "*jarvis*" -o -iname "*m0*" -o -iname "*legacyweb*" -o -iname "*watchdog*" -o -iname "*supervisor*" -o -iname "*agent*" -o -iname "*worker*" \) -print 2>/dev/null | sort -u'
run_sh 21_watchdog_conflicts 'ps auxww | grep -Ei "jarvis|m0|legacyweb|watchdog|supervisor|agent|worker|kk-f" | grep -v grep || true; echo; systemctl list-unit-files --no-pager 2>&1 | grep -Ei "jarvis|m0|legacyweb|watchdog|supervisor|agent|worker|kk" || true'
run_sh 22_workspace 'pwd; echo; find /root/K/F -maxdepth 4 -printf "%M %u %g %s %TY-%Tm-%TdT%TH:%TM:%TS %p\n" 2>/dev/null | sort'
run_sh 23_security_sysctls 'sysctl kernel.unprivileged_userns_clone 2>&1 || true; sysctl fs.protected_hardlinks 2>&1 || true; sysctl fs.protected_symlinks 2>&1 || true; sysctl kernel.yama.ptrace_scope 2>&1 || true'
run_sh 24_relevant_mount_options 'findmnt -no TARGET,SOURCE,FSTYPE,OPTIONS / /root /tmp 2>&1 || true'
{
 echo "ENVIRONMENT_BASELINE_CAPTURE_VERSION=1"
 echo "CAPTURED_AT_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
 echo "HOSTNAME=$(hostname)"
 echo "ROOT=$ROOT"
 echo "NOTE=Raw evidence only; not an acceptance decision."
} > "$OUT/00_CAPTURE_META.txt"
find "$OUT" -maxdepth 1 -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > "$OUT/SHA256SUMS"
sha256sum "$ROOT/tools/environment_baseline.sh" > "$OUT/CAPTURE_SCRIPT_SHA256"
echo "ENV_BASELINE_CAPTURE_COMPLETE"
