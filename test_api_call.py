#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试API调用
"""
import httpx
import json


def test_api_call():
    """测试调用本地API服务"""
    url = "http://localhost:28889/v1/chat/completions"
    
    payload = {
        "model": "claude-4-sonnet",
        "messages": [
            {"role": "user", "content": "你好，请介绍一下你自己"}
        ],
        "stream": True
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer test123"
    }
    
    print("=" * 80)
    print("🧪 测试API调用")
    print("=" * 80)
    print(f"📤 请求URL: {url}")
    print(f"🔑 Authorization: {headers.get('Authorization')}")
    print(f"📝 请求payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("=" * 80)
    
    try:
        with httpx.Client(timeout=30.0) as client:
            with client.stream("POST", url, json=payload, headers=headers) as response:
                print(f"\n📥 响应状态码: {response.status_code}")
                print(f"📋 响应头:")
                for key, value in response.headers.items():
                    print(f"   {key}: {value}")
                
                print(f"\n📄 流式响应内容:")
                print("-" * 80)
                
                for line in response.iter_lines():
                    if line.strip():
                        print(line)
                
                print("-" * 80)
                
    except httpx.ConnectError as e:
        print(f"\n❌ 连接失败: {e}")
        print("⚠️ 请确保服务器正在运行: uv run python server.py")
    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_api_call()

