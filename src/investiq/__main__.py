"""InvestIQ CLI entry point — run with `python -m investiq`.

Starts the FastAPI/uvicorn HTTP server for the research API.

Respects the Cloud Run PORT environment variable.
Defaults to port 8080 when PORT is not set (Cloud Run convention).

Usage:
    python -m investiq
    python -m investiq --port 8080
    python -m investiq --reload
"""

import argparse
import os
import sys

if __name__ == "__main__":
    import uvicorn

    # Cloud Run injects PORT; fall back to 8080 per Cloud Run convention
    default_port = int(os.environ.get("PORT", "8080"))

    parser = argparse.ArgumentParser(description="InvestIQ Research API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=default_port, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    args = parser.parse_args()

    print(f"\n=======================================================")
    print(f"  InvestIQ Research API running at http://localhost:{args.port}/")
    print(f"=======================================================\n")

    uvicorn.run(
        "investiq.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )