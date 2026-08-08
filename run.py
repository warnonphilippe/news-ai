#!/usr/bin/env python3
"""Launcher partage : attend la sante du backend, declenche le run du jour,
ouvre le navigateur. Utilise uniquement la stdlib pour rester portable
(appelable par n'importe quel python3, hors venv).
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import webbrowser


def _get(url: str, timeout: float = 5.0):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post(url: str, timeout: float = 10.0):
    req = urllib.request.Request(url, data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def wait_for_health(base_url: str, retries: int, delay: float) -> bool:
    for i in range(retries):
        try:
            _get(f"{base_url}/api/health", timeout=3.0)
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(delay)
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--frontend-url", default="http://localhost:4200")
    parser.add_argument("--retries", type=int, default=60)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    print("[run.py] Attente du backend...", flush=True)
    if not wait_for_health(args.backend_url, args.retries, args.delay):
        print("[run.py] Backend indisponible apres attente. Abandon du run auto.",
              file=sys.stderr, flush=True)
        return 1
    print("[run.py] Backend pret.", flush=True)

    try:
        res = _post(f"{args.backend_url}/api/run")
        print(f"[run.py] Recherche du jour : {res.get('action')} "
              f"(status={res.get('status')})", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"[run.py] Echec du declenchement du run : {exc}",
              file=sys.stderr, flush=True)

    if not args.no_browser:
        print(f"[run.py] Ouverture de {args.frontend_url}", flush=True)
        try:
            webbrowser.open(args.frontend_url)
        except Exception:  # noqa: BLE001
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
