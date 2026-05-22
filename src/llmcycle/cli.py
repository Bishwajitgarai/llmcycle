import os
import sys
import argparse
import uvicorn
from pathlib import Path

def _safe_load_env(dotenv_path: str = ".env"):
    """Load .env handling UTF-8 BOM, UTF-16 (Windows Notepad saves), and plain ASCII."""
    path = Path(dotenv_path)
    if not path.exists():
        return
    # Try encodings in order: utf-8-sig (strips BOM), utf-16, utf-8, latin-1
    for enc in ("utf-8-sig", "utf-16", "utf-8", "latin-1"):
        try:
            content = path.read_text(encoding=enc)
            # Write a clean temp .env and load it, or just parse manually
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
            return  # success
        except (UnicodeDecodeError, UnicodeError):
            continue

_safe_load_env()


def main():
    parser = argparse.ArgumentParser(
        prog="llmcycle",
        description="LLMCycle - Universal LLM Router CLI",
    )
    sub = parser.add_subparsers(dest="command")

    # ui command
    ui_p = sub.add_parser("ui", help="Start the web dashboard")
    ui_p.add_argument("--host", default="127.0.0.1")
    ui_p.add_argument("--port", type=int, default=8000)
    ui_p.add_argument("--reload", action="store_true", default=False)

    # providers command
    sub.add_parser("providers", help="List loaded providers")

    args = parser.parse_args()

    if args.command == "ui":
        print(f"\nLLMCycle Dashboard -> http://{args.host}:{args.port}\n")
        uvicorn.run(
            "llmcycle.ui.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )

    elif args.command == "providers":
        from llmcycle import LLMCycle
        client = LLMCycle()
        providers = client.get_providers()
        if not providers:
            print("No providers loaded. Add *_API_KEYS to your .env file.")
        else:
            print(f"\nLoaded providers ({len(providers)}):")
            for p in providers:
                stats = client.key_manager.key_count(p)
                print(f"  ✓ {p:20s}  keys: {stats['active']}/{stats['total']} active")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
