"""Read-only preflight by default. --watch monitors and stops ONLY the 411 stack."""
import argparse
import datetime
import json
import os
import signal
import subprocess
import time
import urllib.request
import shutil
from pathlib import Path

BASE = Path(os.environ.get('YOUZHIHUI_BASE', '/srv/youzhihui')) / 'acceptance411'
PROJECT = 'youzhihui-411'
SLICE = 'youzhihui411.slice'
STOP = False


def command(*args):
    return subprocess.check_output(args, text=True, timeout=15).strip()


def memory():
    return {k: int(v.split()[0]) * 1024 for k, v in
            (line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())}


def trial_probe():
    start = time.monotonic()
    try:
        with urllib.request.urlopen('http://127.0.0.1:18082/health/ready', timeout=2) as r:
            return r.status == 200, time.monotonic() - start
    except Exception:
        return False, time.monotonic() - start


def containers(project):
    ids = command('docker', 'ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project).split()
    return json.loads(command('docker', 'inspect', *ids)) if ids else []


def cpu_counters():
    counters = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))
    return sum(counters), counters[3] + counters[4]


def log(file, value):
    value['utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    line = json.dumps(value, ensure_ascii=False)
    print(line, flush=True)
    file.write(line + '\n')
    file.flush()


def preflight(require_slice=False):
    errors = []
    mem = memory()
    if mem['MemAvailable'] < 3584 * 1024**2:
        errors.append('MemAvailable below 3584 MiB')
    if shutil.disk_usage(BASE).free < 10 * 1024**3:
        errors.append('Disk available below 10 GiB')
    if Path('/proc/loadavg').read_text().split() and float(Path('/proc/loadavg').read_text().split()[0]) > 3:
        errors.append('Host load1 above 3')
    if command('docker', 'info', '--format', '{{.CgroupDriver}}/{{.CgroupVersion}}') != 'systemd/2':
        errors.append('Expected systemd cgroup v2')
    if require_slice:
        if command('systemctl', 'show', SLICE, '-p', 'LoadState', '--value') != 'loaded':
            errors.append('Resource slice has not been installed')
        for item in containers(PROJECT):
            cfg = item['HostConfig']
            if cfg.get('CgroupParent') != SLICE:
                errors.append(item['Name'] + ': wrong cgroup parent')
            if not cfg.get('Memory') or cfg.get('MemorySwap') != cfg['Memory']:
                errors.append(item['Name'] + ': missing memory/swap boundary')
        if not containers(PROJECT):
            errors.append('411 containers not created')
    probes = [trial_probe() for _ in range(3)]
    if not all(ok for ok, _ in probes):
        errors.append('Trial readiness failed at baseline')
    if max(t for _, t in probes) > 1:
        errors.append('Trial baseline readiness slower than 1 second')
    return errors, max(t for _, t in probes), mem


def stop_411():
    ids = command('docker', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT).split()
    if ids:
        subprocess.run(['docker', 'stop', '--time', '10', *ids], timeout=90, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--duration', type=int, default=1200)
    parser.add_argument('--log', default=str(BASE / 'logs/guard.jsonl'))
    args = parser.parse_args()
    errors, baseline, initial = preflight(require_slice=args.watch)
    print(json.dumps({'preflight_errors': errors, 'trial_baseline_s': baseline,
                      'available_mib': initial['MemAvailable'] // 1024**2}, ensure_ascii=False))
    if errors:
        raise SystemExit(2)
    if not args.watch:
        return
    path = Path(args.log)
    path.parent.mkdir(parents=True, exist_ok=True)
    swap0 = initial['SwapTotal'] - initial['SwapFree']
    strikes = {}
    previous = cpu_counters()
    deadline = time.monotonic() + args.duration
    reason = 'monitor_window_finished'
    try:
        with path.open('a', encoding='utf-8') as output:
            while time.monotonic() < deadline and not STOP:
                time.sleep(5)
                mem = memory()
                current = cpu_counters()
                total = current[0] - previous[0]
                cpu = 100 * (1 - (current[1] - previous[1]) / max(total, 1))
                previous = current
                ok, latency = trial_probe()
                oom = any(c['State'].get('OOMKilled') for c in containers(PROJECT))
                checks = {
                    'low_memory': mem['MemAvailable'] < 2048 * 1024**2,
                    'swap_growth': mem['SwapTotal'] - mem['SwapFree'] - swap0 > 128 * 1024**2,
                    'cpu_saturated': cpu > 90,
                    'trial_degraded': not ok or latency > max(1, 3 * baseline),
                    'disk_low': shutil.disk_usage(BASE).free < 10 * 1024**3,
                }
                for key, bad in checks.items():
                    strikes[key] = strikes.get(key, 0) + 1 if bad else 0
                failures = [k for k, count in strikes.items() if count >= 3]
                log(output, {'available_mib': mem['MemAvailable'] // 1024**2,
                             'cpu_percent': round(cpu, 2), 'trial_seconds': latency,
                             'trial_ready': ok, 'strikes': strikes, 'oom': oom})
                if failures or oom:
                    reason = ','.join(failures) if failures else '411_oom'
                    break
            if STOP:
                reason = 'interrupted'
            log(output, {'stop_reason': reason})
    finally:
        # Never stop the trial project or any unrelated process.
        stop_411()


def interrupted(*_):
    global STOP
    STOP = True


if __name__ == '__main__':
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    main()
