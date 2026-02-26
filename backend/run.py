#!/usr/bin/env python
"""
Self-Bot 后端服务启动脚本
"""
import os
import sys
import argparse
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn
from dotenv import load_dotenv

load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(description='Self-Bot API Server')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='服务监听地址')
    parser.add_argument('--port', type=int, default=8000, help='服务监听端口')
    parser.add_argument('--reload', action='store_true', help='开发模式（热重载）')
    parser.add_argument('--workers', type=int, default=1, help='工作进程数')
    parser.add_argument('--log-level', type=str, default='info', 
                        choices=['critical', 'error', 'warning', 'info', 'debug', 'trace'],
                        help='日志级别')
    return parser.parse_args()


def main():
    args = parse_args()
    
    print("\n" + "=" * 60)
    print("  Self-Bot API Server")
    print("=" * 60)
    print(f"  Host: {args.host}")
    print(f"  Port: {args.port}")
    print(f"  Reload: {args.reload}")
    print(f"  Workers: {args.workers}")
    print(f"  Log Level: {args.log_level}")
    print("=" * 60 + "\n")
    
    os.environ.setdefault('HOST', args.host)
    os.environ.setdefault('PORT', str(args.port))
    
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=args.log_level,
        access_log=True,
    )


if __name__ == "__main__":
    main()
