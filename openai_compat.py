#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI Chat Completions compatible server (system-prompt flavored)

Startup entrypoint that exposes the modular app implemented in protobuf2openai.
"""

from __future__ import annotations

import os
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from protobuf2openai.app import app  # FastAPI app


if __name__ == "__main__":
    import argparse
    import uvicorn

    # 解析命令行参数
    parser = argparse.ArgumentParser(description="OpenAI兼容API服务器")
    parser.add_argument("--port", type=int, default=28889, help="服务器监听端口 (默认: 28889)")
    args = parser.parse_args()

    # Debug: print API_TOKEN
    print(f"🔑 API_TOKEN loaded: {os.getenv('API_TOKEN')}")
    
    # Refresh JWT on startup before running the server
    try:
        from warp2protobuf.core.auth import refresh_jwt_if_needed as _refresh_jwt
        asyncio.run(_refresh_jwt())
    except Exception:
        pass
    uvicorn.run(
        app,
        host=os.getenv("HOST", "127.0.0.1"),
        port=args.port,
        log_level="info",
    )
