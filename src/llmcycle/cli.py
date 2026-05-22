"""
LLMCycle CLI — command-line interface for the LLM router.

Commands
--------
  llmcycle help                   Show all commands with examples
  llmcycle version                Show installed version
  llmcycle list                   List all loaded providers + key health
  llmcycle providers              Alias for 'list'
  llmcycle ping [provider]        Test connectivity to one or all providers
  llmcycle keys add               Add / append API key(s) to .env
  llmcycle keys list              Show all keys in .env (masked)
  llmcycle keys remove            Remove a provider's keys from .env
  llmcycle config                 Show active configuration
  llmcycle cache show             Show model-info cache stats + location
  llmcycle cache clear            Clear the disk + memory cache
  llmcycle cache set-dir <path>   Override the cache directory
  llmcycle ui                     Start the web dashboard
"""
from __future__ import annotations
import os
import sys
import argparse
from pathlib import Path


# ─── .env loader ─────────────────────────────────────────────────────────────

def _safe_load_env(dotenv_path: str = ".env") -> None:
    """Load .env handling UTF-8 BOM, UTF-16 (Windows Notepad), and plain ASCII."""
    path = Path(dotenv_path)
    if not path.exists():
        return
    for enc in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
        try:
            content = path.read_text(encoding=enc)
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
            return
        except (UnicodeDecodeError, UnicodeError):
            continue


# ─── .env writer helpers ──────────────────────────────────────────────────────

def _read_env_file(path: Path) -> list[str]:
    """Return raw lines from .env, or [] if file doesn't exist."""
    if not path.exists():
        return []
    for enc in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
        try:
            return path.read_text(encoding=enc).splitlines()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return []


def _write_env_file(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _set_env_key(env_path: Path, env_key: str, value: str) -> None:
    """Set or replace a key in the .env file."""
    lines = _read_env_file(env_path)
    new_lines = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{env_key}=") or stripped.startswith(f"{env_key} ="):
            new_lines.append(f"{env_key}={value}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        new_lines.append(f"{env_key}={value}")
    _write_env_file(env_path, new_lines)


def _remove_env_key(env_path: Path, env_key: str) -> bool:
    """Remove a key from .env. Returns True if the key was found."""
    lines = _read_env_file(env_path)
    new_lines = [
        l for l in lines
        if not l.strip().startswith(f"{env_key}=")
        and not l.strip().startswith(f"{env_key} =")
    ]
    removed = len(new_lines) < len(lines)
    if removed:
        _write_env_file(env_path, new_lines)
    return removed


def _mask(key: str) -> str:
    """Mask an API key for display: show first 6 + last 4 chars."""
    if len(key) <= 10:
        return key[:2] + "***"
    return key[:6] + "..." + key[-4:]


# ─── Colour helpers ───────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

def _c(text: str, *codes: str) -> str:
    """Colourize text if stdout supports ANSI (skipped on Windows without VT)."""
    if sys.stdout.isatty():
        return "".join(codes) + text + RESET
    return text


# ─── Command handlers ─────────────────────────────────────────────────────────

def cmd_help(_args) -> None:
    print(f"""
{_c('LLMCycle', BOLD, CYAN)} — Universal LLM Router  {_c('♻️', BOLD)}
{_c('https://github.com/Bishwajitgarai/llmcycle', DIM)}

{_c('USAGE', BOLD)}
  llmcycle <command> [options]

{_c('COMMANDS', BOLD)}
  {_c('help', CYAN)}                        Show this help message
  {_c('version', CYAN)}                     Show installed version
  {_c('list', CYAN)}                        List loaded providers + key health
  {_c('providers', CYAN)}                   Alias for 'list'
  {_c('ping', CYAN)} [provider]             Test connectivity to one or all providers
  {_c('keys add', CYAN)} <provider> <keys>  Add / append API keys to .env
  {_c('keys list', CYAN)}                   Show all keys in .env (masked)
  {_c('keys remove', CYAN)} <provider>      Remove a provider's keys from .env
  {_c('config', CYAN)}                      Show active LLMCycle configuration
  {_c('cache show', CYAN)}                  Show model-info cache stats + file location
  {_c('cache clear', CYAN)}                 Wipe the model-info cache (LRU + disk)
  {_c('cache set-dir', CYAN)} <path>        Override the cache directory (writes to .env)
  {_c('ui', CYAN)} [--port N] [--host H]   Start the web dashboard

{_c('EXAMPLES', BOLD)}
  # Add OpenAI keys (comma-separated for multiple)
  llmcycle keys add openai sk-key1,sk-key2

  # Add a single Groq key
  llmcycle keys add groq gsk-abc123

  # List all configured providers
  llmcycle list

  # Ping a specific provider
  llmcycle ping openai

  # Ping all providers at once
  llmcycle ping

  # Show cache info
  llmcycle cache show

  # Override the model-info cache directory
  llmcycle cache set-dir /data/llmcycle/cache

  # Start dashboard on custom port
  llmcycle ui --port 9000

  # Start dashboard exposed to network
  llmcycle ui --host 0.0.0.0 --port 9000

  # Show active config
  llmcycle config

{_c('ENVIRONMENT', BOLD)}
  {_c('*_API_KEYS', YELLOW)}              Comma-separated keys per provider (e.g. OPENAI_API_KEYS)
  {_c('*_BASE_URL', YELLOW)}              Override base URL per provider   (e.g. OLLAMA_BASE_URL)
  {_c('LLMCYCLE_CACHE_DIR', YELLOW)}      Model-info cache directory       (default: ./llmcycle/storage/model_info)
  {_c('LLMCYCLE_UI_HOST', YELLOW)}        Dashboard host  (default: 127.0.0.1)
  {_c('LLMCYCLE_UI_PORT', YELLOW)}        Dashboard port  (default: 8000)
""")


def cmd_version(_args) -> None:
    try:
        from llmcycle import __version__
        print(f"llmcycle {_c(__version__, BOLD, GREEN)}")
    except ImportError:
        print("llmcycle (version unknown)")


def cmd_list(_args) -> None:
    from llmcycle import LLMCycle
    client = LLMCycle()
    providers = client.get_providers()
    if not providers:
        print(_c("  No providers loaded.", YELLOW))
        print(_c("  Add keys with:  llmcycle keys add <provider> <key>", DIM))
        return

    print(f"\n{_c(f'Loaded providers ({len(providers)}):', BOLD)}\n")
    for p in providers:
        stats = client.key_manager.key_count(p)
        active = stats["active"]
        total  = stats["total"]
        health = _c(f"{active}/{total} keys", GREEN) if active > 0 else _c(f"0/{total} keys", RED)
        status = _c("✓", GREEN) if active > 0 else _c("✗", RED)
        print(f"  {status}  {_c(p, BOLD):<30s}  {health}")
    print()


def cmd_ping(args) -> None:
    import asyncio, time
    from llmcycle import LLMCycle

    _safe_load_env()
    client = LLMCycle()
    providers = [args.provider.lower()] if getattr(args, "provider", None) else client.get_providers()

    if not providers:
        print(_c("  No providers loaded.", YELLOW))
        return

    print(f"\n{_c('Pinging providers...', BOLD)}\n")

    async def _ping_one(name: str) -> dict:
        prov = client._providers.get(name)
        key  = client.key_manager.get_next_key(name)
        if not prov or not key:
            return {"provider": name, "ok": False, "error": "No active keys", "latency_ms": 0}
        t0 = time.monotonic()
        try:
            # Use /models as a lightweight probe
            await prov.get_models(key)
            latency = round((time.monotonic() - t0) * 1000, 1)
            return {"provider": name, "ok": True, "latency_ms": latency}
        except Exception as e:
            return {"provider": name, "ok": False, "error": str(e)[:60], "latency_ms": 0}

    async def _run():
        results = await asyncio.gather(*[_ping_one(p) for p in providers])
        for r in results:
            if r["ok"]:
                lat = _c(f"{r['latency_ms']:.0f}ms", GREEN if r["latency_ms"] < 500 else YELLOW)
                print(f"  {_c('✓', GREEN)}  {_c(r['provider'], BOLD):<28s}  {lat}")
            else:
                err = _c(r.get("error", "failed"), RED)
                print(f"  {_c('✗', RED)}  {_c(r['provider'], BOLD):<28s}  {err}")
        print()

    asyncio.run(_run())


def cmd_keys_add(args) -> None:
    env_path = Path(args.env_file)
    provider = args.provider.upper()
    env_key  = f"{provider}_API_KEYS"
    new_keys = [k.strip() for k in args.keys.split(",") if k.strip()]

    if not new_keys:
        print(_c("  Error: no valid keys provided.", RED))
        sys.exit(1)

    # Merge with existing keys
    existing_raw = os.environ.get(env_key, "")
    existing_keys = [k.strip() for k in existing_raw.split(",") if k.strip()]
    combined = list(dict.fromkeys(existing_keys + new_keys))  # dedup, preserve order

    _set_env_key(env_path, env_key, ",".join(combined))

    print(f"\n{_c('✓', GREEN)}  Saved {_c(str(len(new_keys)), BOLD)} key(s) for "
          f"{_c(provider, BOLD)} to {_c(str(env_path), DIM)}\n")
    for k in new_keys:
        print(f"      {_c(_mask(k), CYAN)}")

    added = len(combined) - len(existing_keys)
    if added < len(new_keys):
        dupes = len(new_keys) - added
        print(_c(f"\n  Note: {dupes} duplicate key(s) skipped.", YELLOW))
    print()


def cmd_keys_list(args) -> None:
    env_path = Path(args.env_file)
    lines = _read_env_file(env_path)
    found: list[tuple[str, list[str]]] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "_API_KEYS=" in stripped or "_API_KEYS =" in stripped:
            k, _, v = stripped.partition("=")
            provider = k.strip().replace("_API_KEYS", "")
            keys     = [x.strip() for x in v.strip().split(",") if x.strip()]
            found.append((provider, keys))

    if not found:
        print(_c("\n  No API keys found in .env\n", YELLOW))
        print(_c("  Add one with:  llmcycle keys add openai sk-xxx\n", DIM))
        return

    total_keys = sum(len(ks) for _, ks in found)
    print(f"\n{_c(f'Stored keys ({total_keys} total across {len(found)} provider(s)):', BOLD)}\n")
    for provider, keys in found:
        print(f"  {_c(provider, BOLD, CYAN)}")
        for k in keys:
            print(f"      {_c(_mask(k), DIM)}")
    print()


def cmd_keys_remove(args) -> None:
    env_path = Path(args.env_file)
    provider = args.provider.upper()
    env_key  = f"{provider}_API_KEYS"
    removed  = _remove_env_key(env_path, env_key)

    if removed:
        print(f"\n{_c('✓', GREEN)}  Removed keys for {_c(provider, BOLD)} from {_c(str(env_path), DIM)}\n")
    else:
        print(_c(f"\n  No keys found for {provider} in {env_path}\n", YELLOW))


def cmd_config(_args) -> None:
    from llmcycle import LLMCycle, __version__
    from llmcycle.providers.cache import get_model_info_cache
    client = LLMCycle()
    providers = client.get_providers()
    cache = get_model_info_cache()
    cs = cache.stats()

    strategy = client.router.strategy.value if hasattr(client, "router") else "priority"
    ui_host  = os.environ.get("LLMCYCLE_UI_HOST", "127.0.0.1")
    ui_port  = os.environ.get("LLMCYCLE_UI_PORT", "8000")

    storage_backend = os.environ.get("LLMCYCLE_STORAGE_BACKEND", _c("not configured", DIM))
    storage_url     = os.environ.get("LLMCYCLE_STORAGE_URL",     _c("not configured", DIM))
    cache_dir_env   = os.environ.get("LLMCYCLE_CACHE_DIR",       _c("default (./llmcycle/storage/model_info)", DIM))

    print(f"""
{_c('LLMCycle Configuration', BOLD, CYAN)}

  {_c('Version', BOLD)}            {_c(__version__, GREEN)}
  {_c('Routing strategy', BOLD)}   {_c(strategy, CYAN)}
  {_c('Providers loaded', BOLD)}   {_c(str(len(providers)), GREEN)} — {", ".join(providers) or _c("none", RED)}

  {_c('Dashboard host', BOLD)}     {ui_host}
  {_c('Dashboard port', BOLD)}     {ui_port}

  {_c('Storage backend', BOLD)}    {storage_backend}
  {_c('Storage URL', BOLD)}        {storage_url[:60] + "..." if len(str(storage_url)) > 60 else storage_url}

  {_c('Cache dir', BOLD)}          {_c(cs['cache_dir'], CYAN)}
  {_c('Cache file', BOLD)}         {_c(cs['cache_file'], DIM)}
  {_c('Cache entries', BOLD)}      {cs['lru_entries']} / {cs['lru_max']} (LRU)   disk: {'yes' if cs['disk_exists'] else 'no'} ({cs['disk_size_kb']} KB)
  {_c('Cache env override', BOLD)} {cache_dir_env}

  {_c('Env file', BOLD)}           {_c(".env", DIM)} (in current directory)
""")


# ─── Cache commands ───────────────────────────────────────────────────────────

def cmd_cache_show(_args) -> None:
    from llmcycle.providers.cache import get_model_info_cache
    cache = get_model_info_cache()
    cs = cache.stats()
    keys = cache.keys()

    print(f"""
{_c('Model Info Cache', BOLD, CYAN)}

  {_c('Directory', BOLD)}   {_c(cs['cache_dir'], CYAN)}
  {_c('File', BOLD)}        {_c(cs['cache_file'], DIM)}
  {_c('Disk exists', BOLD)} {'yes  ' + _c(f"({cs['disk_size_kb']} KB)", DIM) if cs['disk_exists'] else _c('no', YELLOW)}
  {_c('LRU entries', BOLD)} {cs['lru_entries']} / {cs['lru_max']}
""")
    if keys:
        print(f"  {_c('Cached models:', BOLD)}")
        for k in sorted(keys):
            print(f"      {_c(k, DIM)}")
    else:
        print(f"  {_c('No models cached yet — they will be fetched on first use.', DIM)}")
    print()


def cmd_cache_clear(args) -> None:
    from llmcycle.providers.cache import get_model_info_cache
    cache = get_model_info_cache()
    cs    = cache.stats()
    n     = len(cache)

    if n == 0 and not cs["disk_exists"]:
        print(_c("\n  Cache is already empty.\n", DIM))
        return

    # Confirm unless --yes was passed
    if not getattr(args, "yes", False):
        disk_note = f" + disk file {_c(cs['cache_file'], DIM)}" if cs["disk_exists"] else ""
        answer = input(
            f"\n  Clear {_c(str(n), BOLD)} cached model entries{disk_note}? "
            f"[{_c('y', GREEN)}/N] "
        ).strip().lower()
        if answer not in ("y", "yes"):
            print(_c("  Aborted.\n", YELLOW))
            return

    cache.clear()
    print(f"\n{_c('✓', GREEN)}  Model info cache cleared.\n")


def cmd_cache_set_dir(args) -> None:
    """Write LLMCYCLE_CACHE_DIR to .env (with override confirmation if already set)."""
    new_dir  = Path(args.directory).resolve()
    env_path = Path(args.env_file)
    env_key  = "LLMCYCLE_CACHE_DIR"

    # Check if already set
    existing = os.environ.get(env_key, "").strip()
    if existing and existing != str(new_dir):
        if not getattr(args, "yes", False):
            answer = input(
                f"\n  {_c('LLMCYCLE_CACHE_DIR', YELLOW)} is already set to:\n"
                f"    {_c(existing, DIM)}\n"
                f"  Override with {_c(str(new_dir), CYAN)}? [{_c('y', GREEN)}/N] "
            ).strip().lower()
            if answer not in ("y", "yes"):
                print(_c("  Aborted.\n", YELLOW))
                return

    _set_env_key(env_path, env_key, str(new_dir))
    print(
        f"\n{_c('✓', GREEN)}  Cache directory set to {_c(str(new_dir), CYAN)}\n"
        f"    Written to {_c(str(env_path), DIM)}\n"
        f"    Folder structure: {_c(str(new_dir / 'model_info.json'), DIM)}\n"
    )
def cmd_ui(args) -> None:
    import uvicorn
    host = args.host or os.environ.get("LLMCYCLE_UI_HOST", "127.0.0.1")
    port = args.port or int(os.environ.get("LLMCYCLE_UI_PORT", "8000"))
    print(f"\n{_c('LLMCycle Dashboard', BOLD, CYAN)} → {_c(f'http://{host}:{port}', GREEN)}\n")
    uvicorn.run(
        "llmcycle.ui.app:app",
        host=host,
        port=port,
        reload=args.reload,
    )


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    _safe_load_env()

    parser = argparse.ArgumentParser(
        prog="llmcycle",
        description="LLMCycle — Universal LLM Router",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    sub = parser.add_subparsers(dest="command")

    # help
    sub.add_parser("help", help="Show detailed help and examples")

    # version
    sub.add_parser("version", help="Show installed version")

    # list / providers
    sub.add_parser("list",      help="List loaded providers + key health")
    sub.add_parser("providers", help="Alias for 'list'")

    # ping
    ping_p = sub.add_parser("ping", help="Test connectivity to one or all providers")
    ping_p.add_argument("provider", nargs="?", default=None,
                        help="Provider name (omit to ping all)")

    # config
    sub.add_parser("config", help="Show active configuration (includes cache info)")

    # keys subcommand
    keys_p   = sub.add_parser("keys", help="Manage API keys in .env")
    keys_sub = keys_p.add_subparsers(dest="keys_cmd")

    keys_add_p = keys_sub.add_parser("add", help="Add / append API key(s) to .env")
    keys_add_p.add_argument("provider", help="Provider name (e.g. openai, groq, deepseek)")
    keys_add_p.add_argument("keys", help="Comma-separated key(s)  e.g. sk-key1,sk-key2")
    keys_add_p.add_argument("--env-file", default=".env", dest="env_file")

    keys_list_p = keys_sub.add_parser("list", help="Show all keys in .env (masked)")
    keys_list_p.add_argument("--env-file", default=".env", dest="env_file")

    keys_rm_p = keys_sub.add_parser("remove", help="Remove a provider's keys from .env")
    keys_rm_p.add_argument("provider")
    keys_rm_p.add_argument("--env-file", default=".env", dest="env_file")

    # cache subcommand
    cache_p   = sub.add_parser("cache", help="Manage the model-info disk cache")
    cache_sub = cache_p.add_subparsers(dest="cache_cmd")

    cache_sub.add_parser("show", help="Show cache stats and file location")

    cache_clr = cache_sub.add_parser("clear", help="Wipe LRU + disk cache (asks to confirm)")
    cache_clr.add_argument("-y", "--yes", action="store_true",
                           help="Skip confirmation prompt")

    cache_dir_p = cache_sub.add_parser(
        "set-dir", help="Override cache directory (writes LLMCYCLE_CACHE_DIR to .env)"
    )
    cache_dir_p.add_argument("directory", help="New cache directory path")
    cache_dir_p.add_argument("--env-file", default=".env", dest="env_file")
    cache_dir_p.add_argument("-y", "--yes", action="store_true",
                             help="Override without confirmation if already set")

    # ui
    ui_p = sub.add_parser("ui", help="Start the web dashboard")
    ui_p.add_argument("--host", default=None,
                      help="Host to bind (default: LLMCYCLE_UI_HOST or 127.0.0.1)")
    ui_p.add_argument("--port", type=int, default=None,
                      help="Port (default: LLMCYCLE_UI_PORT or 8000)")
    ui_p.add_argument("--reload", action="store_true", default=False,
                      help="Auto-reload on code changes (dev mode)")

    # ── dispatch ──────────────────────────────────────────────────────────────
    args = parser.parse_args()

    if args.command in ("help", None):
        cmd_help(args)

    elif args.command == "version":
        cmd_version(args)

    elif args.command in ("list", "providers"):
        cmd_list(args)

    elif args.command == "ping":
        cmd_ping(args)

    elif args.command == "config":
        cmd_config(args)

    elif args.command == "keys":
        if not args.keys_cmd:
            keys_p.print_help()
        elif args.keys_cmd == "add":
            cmd_keys_add(args)
        elif args.keys_cmd == "list":
            cmd_keys_list(args)
        elif args.keys_cmd == "remove":
            cmd_keys_remove(args)

    elif args.command == "cache":
        if not args.cache_cmd:
            cache_p.print_help()
        elif args.cache_cmd == "show":
            cmd_cache_show(args)
        elif args.cache_cmd == "clear":
            cmd_cache_clear(args)
        elif args.cache_cmd == "set-dir":
            cmd_cache_set_dir(args)

    elif args.command == "ui":
        cmd_ui(args)

    else:
        cmd_help(args)


if __name__ == "__main__":
    main()
