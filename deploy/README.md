# VM Bootstrap

`bootstrap_oracle_vm.sh` prepares an Ubuntu 20.04 VM for the current RRTard processing stack and the planned backend runtime.

What it does:

- installs apt packages needed by the current scripts
- creates an app user and runtime directories
- syncs the repo into `/opt/rrtard/app`
- persists `config/`, `data/`, and `schemas/` under `/var/lib/rrtard`
- creates a Python venv and installs `deploy/requirements.vm.txt`
- writes `/etc/rrtard/rrtard.env` with a shared API key and runtime paths
- optionally installs `systemd` services if start commands are supplied

Basic usage:

```bash
sudo ./deploy/bootstrap_oracle_vm.sh --api-key "$(openssl rand -hex 32)"
```

Recommended when you want the VM to sync from the canonical GitHub repo instead
of whichever local copy the script is run from:

```bash
sudo ./deploy/bootstrap_oracle_vm.sh \
  --api-key "$(openssl rand -hex 32)" \
  --repo-url "https://github.com/plasmabiscuit/RRTAR.git" \
  --repo-ref "main"
```

If you later add a backend entrypoint:

```bash
sudo ./deploy/bootstrap_oracle_vm.sh \
  --api-key "replace-me" \
  --repo-url "https://github.com/plasmabiscuit/RRTAR.git" \
  --repo-ref "main" \
  --backend-cmd "/opt/rrtard/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8081" \
  --worker-cmd "/opt/rrtard/.venv/bin/python -m backend.worker"
```

Reference data behavior:

- by default, `config/`, `data/`, and `schemas/` are copied only if missing on the VM
- use `--refresh-reference-data` to overwrite the persistent copies from the repo
- when `--repo-url` is supplied, both app sync and reference-data sync come from that cloned repo snapshot
