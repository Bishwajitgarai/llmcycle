import argparse
import uvicorn

def main():
    parser = argparse.ArgumentParser(description="LLMCycle CLI")
    parser.add_argument("command", choices=["ui"], help="Command to run")
    parser.add_argument("--host", default="127.0.0.1", help="Host for the UI")
    parser.add_argument("--port", type=int, default=8000, help="Port for the UI")

    args = parser.parse_args()

    if args.command == "ui":
        print(f"Starting LLMCycle Dashboard on http://{args.host}:{args.port}")
        uvicorn.run("llmcycle.ui.app:app", host=args.host, port=args.port, reload=True)

if __name__ == "__main__":
    main()
