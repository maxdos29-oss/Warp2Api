#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
匿名Token申请测试用例

直接测试Warp API的匿名Token申请接口，查看返回数据
"""
import asyncio
import json
import httpx
from typing import Dict, Any, Optional

from warp2protobuf.core.logging import logger


# Warp客户端版本信息
CLIENT_VERSION = "v0.2025.10.29.08.12.stable_01"
OS_CATEGORY = "WINDOWS"
OS_NAME = "Windows"
OS_VERSION = "10.0.22631"

# 代理配置
PROXY_URL = "http://127.0.0.1:3128"

# GraphQL查询 - 创建匿名用户
CREATE_ANONYMOUS_USER_QUERY = """
mutation CreateAnonymousUser($input: CreateAnonymousUserInput!, $requestContext: RequestContext!) {
  createAnonymousUser(input: $input, requestContext: $requestContext) {
    __typename
    ... on CreateAnonymousUserOutput {
      expiresAt
      anonymousUserType
      firebaseUid
      idToken
      isInviteValid
      responseContext { serverVersion }
    }
    ... on UserFacingError {
      error { __typename message }
      responseContext { serverVersion }
    }
  }
}
"""

# Firebase Identity Toolkit配置
FIREBASE_API_KEY = "AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"
IDENTITY_TOOLKIT_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"


async def test_create_anonymous_user() -> Optional[Dict[str, Any]]:
    """
    测试步骤1: 调用Warp GraphQL API创建匿名用户
    """
    print("=" * 80)
    print("🧪 测试步骤1: 创建匿名用户")
    print("=" * 80)
    
    url = "https://app.warp.dev/graphql/v2?op=CreateAnonymousUser"

    variables = {
        "input": {
            "anonymousUserType": "NATIVE_CLIENT_ANONYMOUS_USER_FEATURE_GATED",
            "expirationType": "NO_EXPIRATION",
            "referralCode": None
        },
        "requestContext": {
            "clientContext": {"version": CLIENT_VERSION},
            "osContext": {
                "category": OS_CATEGORY,
                "linuxKernelVersion": None,
                "name": OS_NAME,
                "version": OS_VERSION,
            }
        }
    }

    payload = {
        "query": CREATE_ANONYMOUS_USER_QUERY,
        "variables": variables,
        "operationName": "CreateAnonymousUser"
    }

    headers = {
        "accept-encoding": "gzip, br",
        "content-type": "application/json",
        "x-warp-client-version": CLIENT_VERSION,
        "x-warp-os-category": OS_CATEGORY,
        "x-warp-os-name": OS_NAME,
        "x-warp-os-version": OS_VERSION,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    try:
        print(f"📤 发送请求到: {url}")
        print(f"🌐 使用代理: {PROXY_URL}")
        print(f"📝 请求payload:")
        print(json.dumps(payload, indent=2, ensure_ascii=False))

        async with httpx.AsyncClient(timeout=30.0, proxy=PROXY_URL) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            print(f"\n📥 响应状态码: {response.status_code}")
            print(f"📋 响应头:")
            for key, value in response.headers.items():
                print(f"   {key}: {value}")

            print(f"\n📄 响应内容 (前500字符):")
            print(response.text[:500])

            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"\n✅ 响应内容 (JSON):")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                except json.JSONDecodeError as e:
                    print(f"\n❌ 响应不是有效的JSON: {e}")
                    print(f"完整响应内容:")
                    print(response.text)
                    return None
                
                # 检查是否有错误
                if "errors" in data:
                    print(f"\n❌ GraphQL返回错误:")
                    for error in data["errors"]:
                        print(f"   - {error.get('message', 'Unknown error')}")
                    return None
                
                # 提取idToken
                if "data" in data and "createAnonymousUser" in data["data"]:
                    user_data = data["data"]["createAnonymousUser"]

                    # 检查是否是错误响应
                    if user_data.get("__typename") == "UserFacingError":
                        error_info = user_data.get("error", {})
                        print(f"\n❌ Warp API返回错误:")
                        print(f"   错误类型: {error_info.get('__typename', 'Unknown')}")
                        print(f"   错误消息: {error_info.get('message', 'No message')}")
                        return None

                    # 成功响应
                    id_token = user_data.get("idToken")
                    firebase_uid = user_data.get("firebaseUid")
                    anonymous_user_type = user_data.get("anonymousUserType")
                    expires_at = user_data.get("expiresAt")

                    print(f"\n✅ 成功创建匿名用户:")
                    print(f"   Firebase UID: {firebase_uid}")
                    print(f"   匿名用户类型: {anonymous_user_type}")
                    print(f"   过期时间: {expires_at}")
                    print(f"   ID Token长度: {len(id_token) if id_token else 0} 字符")

                    return {
                        "id_token": id_token,
                        "firebase_uid": firebase_uid,
                        "anonymous_user_type": anonymous_user_type,
                        "expires_at": expires_at
                    }
                else:
                    print(f"\n❌ 响应格式不正确，缺少createAnonymousUser数据")
                    return None
            else:
                print(f"\n❌ HTTP错误: {response.status_code}")
                print(f"响应内容: {response.text}")
                return None
                
    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_exchange_id_token(id_token: str) -> Optional[Dict[str, Any]]:
    """
    测试步骤2: 使用ID Token交换Firebase refresh token
    """
    print("\n" + "=" * 80)
    print("🧪 测试步骤2: 交换ID Token为Refresh Token")
    print("=" * 80)
    
    url = f"{IDENTITY_TOOLKIT_URL}?key={FIREBASE_API_KEY}"
    
    payload = {
        "token": id_token,
        "returnSecureToken": True
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    try:
        print(f"📤 发送请求到: {url}")
        print(f"🌐 使用代理: {PROXY_URL}")
        print(f"📝 请求payload:")
        print(json.dumps({
            "token": f"{id_token[:50]}..." if len(id_token) > 50 else id_token,
            "returnSecureToken": True
        }, indent=2))

        async with httpx.AsyncClient(timeout=30.0, proxy=PROXY_URL) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            print(f"\n📥 响应状态码: {response.status_code}")
            print(f"📋 响应头:")
            for key, value in response.headers.items():
                print(f"   {key}: {value}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ 响应内容:")
                # 隐藏敏感信息
                safe_data = data.copy()
                if "idToken" in safe_data:
                    safe_data["idToken"] = f"{safe_data['idToken'][:50]}..."
                if "refreshToken" in safe_data:
                    safe_data["refreshToken"] = f"{safe_data['refreshToken'][:50]}..."
                print(json.dumps(safe_data, indent=2, ensure_ascii=False))
                
                # 提取关键信息
                refresh_token = data.get("refreshToken")
                access_token = data.get("idToken")
                expires_in = data.get("expiresIn")
                
                print(f"\n✅ 成功获取Token:")
                print(f"   Refresh Token长度: {len(refresh_token) if refresh_token else 0} 字符")
                print(f"   Access Token长度: {len(access_token) if access_token else 0} 字符")
                print(f"   过期时间: {expires_in} 秒")
                
                return {
                    "refresh_token": refresh_token,
                    "access_token": access_token,
                    "expires_in": expires_in
                }
            else:
                print(f"\n❌ HTTP错误: {response.status_code}")
                print(f"响应内容: {response.text}")
                return None
                
    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_refresh_token(refresh_token: str) -> Optional[Dict[str, Any]]:
    """
    测试步骤3: 使用Refresh Token获取新的Access Token
    """
    print("\n" + "=" * 80)
    print("🧪 测试步骤3: 使用Refresh Token获取Access Token")
    print("=" * 80)
    
    url = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
    
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    
    try:
        print(f"📤 发送请求到: {url}")
        print(f"🌐 使用代理: {PROXY_URL}")
        print(f"📝 请求payload:")
        print(json.dumps({
            "grant_type": "refresh_token",
            "refresh_token": f"{refresh_token[:50]}..."
        }, indent=2))

        async with httpx.AsyncClient(timeout=30.0, proxy=PROXY_URL) as client:
            response = await client.post(url, json=payload, headers=headers)
            
            print(f"\n📥 响应状态码: {response.status_code}")
            print(f"📋 响应头:")
            for key, value in response.headers.items():
                print(f"   {key}: {value}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ 响应内容:")
                # 隐藏敏感信息
                safe_data = data.copy()
                if "id_token" in safe_data:
                    safe_data["id_token"] = f"{safe_data['id_token'][:50]}..."
                if "access_token" in safe_data:
                    safe_data["access_token"] = f"{safe_data['access_token'][:50]}..."
                if "refresh_token" in safe_data:
                    safe_data["refresh_token"] = f"{safe_data['refresh_token'][:50]}..."
                print(json.dumps(safe_data, indent=2, ensure_ascii=False))
                
                # 提取关键信息
                access_token = data.get("id_token") or data.get("access_token")
                expires_in = data.get("expires_in")
                
                print(f"\n✅ 成功刷新Token:")
                print(f"   Access Token长度: {len(access_token) if access_token else 0} 字符")
                print(f"   过期时间: {expires_in} 秒")
                
                return {
                    "access_token": access_token,
                    "expires_in": expires_in
                }
            else:
                print(f"\n❌ HTTP错误: {response.status_code}")
                print(f"响应内容: {response.text}")
                return None
                
    except Exception as e:
        print(f"\n❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """运行完整的匿名Token申请测试"""
    print("🚀 开始匿名Token申请测试")
    print("=" * 80)
    print("测试目标: 验证Warp API的匿名Token申请流程")
    print("=" * 80)
    
    # 步骤1: 创建匿名用户
    step1_result = await test_create_anonymous_user()
    if not step1_result:
        print("\n❌ 测试失败: 无法创建匿名用户")
        return False
    
    id_token = step1_result.get("id_token")
    if not id_token:
        print("\n❌ 测试失败: 未获取到ID Token")
        return False
    
    # 步骤2: 交换ID Token为Refresh Token
    step2_result = await test_exchange_id_token(id_token)
    if not step2_result:
        print("\n❌ 测试失败: 无法交换ID Token")
        return False
    
    refresh_token = step2_result.get("refresh_token")
    if not refresh_token:
        print("\n❌ 测试失败: 未获取到Refresh Token")
        return False
    
    # 步骤3: 使用Refresh Token获取Access Token
    step3_result = await test_refresh_token(refresh_token)
    if not step3_result:
        print("\n❌ 测试失败: 无法刷新Token")
        return False
    
    access_token = step3_result.get("access_token")
    if not access_token:
        print("\n❌ 测试失败: 未获取到Access Token")
        return False
    
    # 测试总结
    print("\n" + "=" * 80)
    print("📊 测试结果总结")
    print("=" * 80)
    print("✅ 步骤1: 创建匿名用户 - 成功")
    print("✅ 步骤2: 交换ID Token - 成功")
    print("✅ 步骤3: 刷新Access Token - 成功")
    print("\n🎉 所有测试通过！匿名Token申请流程正常工作")
    print("\n📝 获取的Token信息:")
    print(f"   Refresh Token: {refresh_token[:50]}...")
    print(f"   Access Token: {access_token[:50]}...")
    
    return True


if __name__ == "__main__":
    asyncio.run(main())

