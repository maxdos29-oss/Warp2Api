#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试个人Token是否正常工作
"""
import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()


async def test_personal_token():
    """测试个人Token发送请求"""
    print("=" * 80)
    print("🧪 测试个人Token")
    print("=" * 80)
    
    # 从环境变量获取个人Token
    refresh_token = os.getenv("WARP_REFRESH_TOKEN")
    if not refresh_token:
        print("❌ 未找到WARP_REFRESH_TOKEN环境变量")
        return False
    
    print(f"\n📝 个人Refresh Token: {refresh_token[:50]}...")
    
    # 步骤1: 刷新获取Access Token
    print("\n📝 步骤1: 刷新获取Access Token")
    
    refresh_url = "https://securetoken.googleapis.com/v1/token?key=AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                refresh_url,
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token
                },
                headers={"Content-Type": "application/json"}
            )
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code != 200:
                print(f"   ❌ 刷新失败: {response.text}")
                return False
            
            token_data = response.json()
            access_token = token_data.get("access_token")
            
            if not access_token:
                print(f"   ❌ 未获取到access_token")
                return False
            
            print(f"   ✅ 成功获取Access Token")
            print(f"   Token长度: {len(access_token)} 字符")
            
        except Exception as e:
            print(f"   ❌ 刷新异常: {e}")
            return False
    
    # 步骤2: 使用Access Token发送测试请求
    print("\n📝 步骤2: 使用个人Token发送测试请求")
    
    # 使用简单的protobuf测试数据
    test_data = bytes.fromhex('0a26122463613264313833632d386263622d343936372d383031632d393561633162323030313030')
    
    url = "https://app.warp.dev/ai/multi-agent"
    headers = {
        "accept": "text/event-stream",
        "content-type": "application/x-protobuf",
        "x-warp-client-version": "v0.2025.08.06.08.12.stable_02",
        "x-warp-os-category": "Windows",
        "x-warp-os-name": "Windows",
        "x-warp-os-version": "11 (26100)",
        "authorization": f"Bearer {access_token}",
        "content-length": str(len(test_data)),
    }
    
    print(f"   请求URL: {url}")
    print(f"   数据大小: {len(test_data)} 字节")
    
    async with httpx.AsyncClient(timeout=30.0, http2=True) as client:
        try:
            response = await client.post(url, headers=headers, content=test_data)
            
            print(f"\n   📥 响应状态码: {response.status_code}")
            print(f"   📋 Content-Type: {response.headers.get('content-type', 'N/A')}")
            print(f"   📋 Content-Length: {response.headers.get('content-length', 'N/A')}")
            
            if response.status_code == 200:
                print(f"   ✅ 请求成功！")
                print(f"   响应长度: {len(response.content)} 字节")
                
                # 尝试读取前100字节
                if len(response.content) > 0:
                    print(f"   响应前100字节: {response.content[:100]}")
                
                return True
                
            elif response.status_code == 429:
                try:
                    error_data = response.json()
                    print(f"   ❌ 429错误: {error_data}")
                except:
                    print(f"   ❌ 429错误: {response.text[:200]}")
                
            elif response.status_code == 500:
                print(f"   ❌ 500错误: Warp服务器内部错误")
                print(f"   响应内容: {response.text[:200] if response.text else 'No content'}")
                
                # 显示所有响应头
                print(f"\n   📋 完整响应头:")
                for key, value in response.headers.items():
                    print(f"      {key}: {value}")
                
            else:
                print(f"   ❌ {response.status_code}错误")
                print(f"   响应: {response.text[:200]}")
            
        except Exception as e:
            print(f"   ❌ 请求异常: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return False


async def test_with_different_data():
    """测试使用不同的请求数据"""
    print("\n" + "=" * 80)
    print("🧪 测试使用不同的请求数据")
    print("=" * 80)
    
    # 从环境变量获取个人Token
    refresh_token = os.getenv("WARP_REFRESH_TOKEN")
    if not refresh_token:
        print("❌ 未找到WARP_REFRESH_TOKEN环境变量")
        return False
    
    # 刷新获取Access Token
    refresh_url = "https://securetoken.googleapis.com/v1/token?key=AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            refresh_url,
            json={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
        )
        
        if response.status_code != 200:
            print(f"❌ Token刷新失败")
            return False
        
        access_token = response.json().get("access_token")
    
    # 测试不同的protobuf数据
    test_cases = [
        ("最小数据", bytes.fromhex('0a00')),
        ("简单conversation_id", bytes.fromhex('0a26122463613264313833632d386263622d343936372d383031632d393561633162323030313030')),
        ("空消息", b''),
    ]
    
    url = "https://app.warp.dev/ai/multi-agent"
    
    for name, test_data in test_cases:
        print(f"\n📝 测试: {name}")
        print(f"   数据大小: {len(test_data)} 字节")
        
        headers = {
            "accept": "text/event-stream",
            "content-type": "application/x-protobuf",
            "x-warp-client-version": "v0.2025.08.06.08.12.stable_02",
            "x-warp-os-category": "Windows",
            "x-warp-os-name": "Windows",
            "x-warp-os-version": "11 (26100)",
            "authorization": f"Bearer {access_token}",
            "content-length": str(len(test_data)),
        }
        
        async with httpx.AsyncClient(timeout=30.0, http2=True) as client:
            try:
                response = await client.post(url, headers=headers, content=test_data)
                print(f"   状态码: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"   ✅ 成功！")
                elif response.status_code == 400:
                    print(f"   ❌ 400错误: {response.text[:100]}")
                elif response.status_code == 429:
                    print(f"   ❌ 429错误: 配额用尽")
                elif response.status_code == 500:
                    print(f"   ❌ 500错误: 服务器内部错误")
                else:
                    print(f"   ❌ {response.status_code}错误")
                
            except Exception as e:
                print(f"   ❌ 异常: {e}")


async def main():
    """运行所有测试"""
    print("🚀 开始测试个人Token")
    print("=" * 80)
    
    # 测试1: 基本测试
    result1 = await test_personal_token()
    
    # 测试2: 不同数据测试
    await test_with_different_data()
    
    print("\n" + "=" * 80)
    print("📊 测试完成")
    print("=" * 80)
    
    if result1:
        print("✅ 个人Token工作正常")
    else:
        print("❌ 个人Token遇到问题")


if __name__ == "__main__":
    asyncio.run(main())

