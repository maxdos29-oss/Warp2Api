#!/usr/bin/env python3
"""申请新的匿名Token并添加到.env文件"""

import asyncio
import httpx
import json
from dotenv import load_dotenv, set_key
from pathlib import Path


# Warp API配置
GRAPHQL_URL = "https://app.warp.dev/graphql/v2?op=CreateAnonymousUser"
FIREBASE_EXCHANGE_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithCustomToken"
FIREBASE_API_KEY = "AIzaSyBdy3O3S9hrdayLJxJ7mriBR4qgUaUygAs"
FIREBASE_REFRESH_URL = "https://securetoken.googleapis.com/v1/token"

# 代理配置
PROXY_URL = "http://127.0.0.1:3128"


async def create_anonymous_user():
    """步骤1: 创建匿名用户"""
    print("=" * 80)
    print("🧪 步骤1: 创建匿名用户")
    print("=" * 80)
    
    query = """
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
    
    variables = {
        "input": {
            "anonymousUserType": "NATIVE_CLIENT_ANONYMOUS_USER_FEATURE_GATED",
            "expirationType": "NO_EXPIRATION",
            "referralCode": None
        },
        "requestContext": {
            "clientContext": {
                "version": "v0.2025.10.29.08.12.stable_01"
            },
            "osContext": {
                "category": "WINDOWS",
                "linuxKernelVersion": None,
                "name": "Windows",
                "version": "10.0.22631"
            }
        }
    }
    
    payload = {
        "query": query,
        "variables": variables,
        "operationName": "CreateAnonymousUser"
    }
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Warp/v0.2025.10.29.08.12.stable_01"
    }
    
    print(f"📤 发送请求到: {GRAPHQL_URL}")
    print(f"🌐 使用代理: {PROXY_URL}")
    
    async with httpx.AsyncClient(timeout=30.0, proxy=PROXY_URL) as client:
        response = await client.post(GRAPHQL_URL, json=payload, headers=headers)
        
        print(f"📥 响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ HTTP错误: {response.status_code}")
            print(f"响应内容: {response.text}")
            return None
        
        data = response.json()
        
        if "errors" in data:
            print(f"❌ GraphQL错误: {data['errors']}")
            return None
        
        result = data.get("data", {}).get("createAnonymousUser", {})
        
        if result.get("__typename") == "UserFacingError":
            error_msg = result.get("error", {}).get("message", "Unknown error")
            print(f"❌ 创建失败: {error_msg}")
            return None
        
        firebase_uid = result.get("firebaseUid")
        id_token = result.get("idToken")
        
        if not firebase_uid or not id_token:
            print(f"❌ 响应缺少必要字段")
            print(f"响应: {json.dumps(result, indent=2)}")
            return None
        
        print(f"✅ 成功创建匿名用户")
        print(f"   Firebase UID: {firebase_uid}")
        print(f"   ID Token长度: {len(id_token)} 字符")
        
        return id_token


async def exchange_id_token(id_token: str):
    """步骤2: 交换ID Token获取Refresh Token"""
    print("\n" + "=" * 80)
    print("🧪 步骤2: 交换ID Token")
    print("=" * 80)
    
    url = f"{FIREBASE_EXCHANGE_URL}?key={FIREBASE_API_KEY}"
    
    payload = {
        "token": id_token,
        "returnSecureToken": True
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"📤 发送请求到: {url}")
    print(f"🌐 使用代理: {PROXY_URL}")
    
    async with httpx.AsyncClient(timeout=30.0, proxy=PROXY_URL) as client:
        response = await client.post(url, json=payload, headers=headers)
        
        print(f"📥 响应状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ HTTP错误: {response.status_code}")
            print(f"响应内容: {response.text}")
            return None
        
        data = response.json()
        
        refresh_token = data.get("refreshToken")
        
        if not refresh_token:
            print(f"❌ 响应缺少refreshToken")
            print(f"响应: {json.dumps(data, indent=2)}")
            return None
        
        print(f"✅ 成功获取Refresh Token")
        print(f"   Refresh Token: {refresh_token[:50]}...")
        print(f"   Refresh Token长度: {len(refresh_token)} 字符")
        
        return refresh_token


async def add_to_env(refresh_token: str):
    """添加匿名Token到.env文件"""
    print("\n" + "=" * 80)
    print("💾 添加Token到.env文件")
    print("=" * 80)
    
    env_path = Path(".env")
    
    if not env_path.exists():
        print(f"❌ .env文件不存在")
        return False
    
    # 读取现有的.env内容
    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 查找是否已有ANONYMOUS_REFRESH_TOKEN
    found = False
    for i, line in enumerate(lines):
        if line.startswith('ANONYMOUS_REFRESH_TOKEN='):
            lines[i] = f'ANONYMOUS_REFRESH_TOKEN={refresh_token}\n'
            found = True
            print(f"✅ 更新现有的ANONYMOUS_REFRESH_TOKEN")
            break
    
    if not found:
        # 添加新的ANONYMOUS_REFRESH_TOKEN
        # 找到合适的位置（在WARP_REFRESH_TOKEN之后）
        insert_pos = -1
        for i, line in enumerate(lines):
            if line.startswith('WARP_REFRESH_TOKEN='):
                insert_pos = i + 1
                break
        
        if insert_pos > 0:
            lines.insert(insert_pos, f'\n# 匿名Token (自动申请)\n')
            lines.insert(insert_pos + 1, f'ANONYMOUS_REFRESH_TOKEN={refresh_token}\n')
            print(f"✅ 添加新的ANONYMOUS_REFRESH_TOKEN")
        else:
            # 如果找不到WARP_REFRESH_TOKEN，就添加到文件末尾
            lines.append(f'\n# 匿名Token (自动申请)\n')
            lines.append(f'ANONYMOUS_REFRESH_TOKEN={refresh_token}\n')
            print(f"✅ 添加新的ANONYMOUS_REFRESH_TOKEN到文件末尾")
    
    # 写回文件
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"✅ .env文件已更新")
    return True


async def main():
    """主函数"""
    print("🚀 开始申请匿名Token")
    print("=" * 80)
    
    # 步骤1: 创建匿名用户
    id_token = await create_anonymous_user()
    if not id_token:
        print("\n❌ 申请失败: 无法创建匿名用户")
        print("💡 提示: 可能遇到速率限制，请稍后再试")
        return
    
    # 步骤2: 交换ID Token
    refresh_token = await exchange_id_token(id_token)
    if not refresh_token:
        print("\n❌ 申请失败: 无法获取Refresh Token")
        return
    
    # 步骤3: 添加到.env文件
    success = await add_to_env(refresh_token)
    if not success:
        print("\n❌ 添加到.env失败")
        print(f"💡 请手动添加以下内容到.env文件:")
        print(f"ANONYMOUS_REFRESH_TOKEN={refresh_token}")
        return
    
    print("\n" + "=" * 80)
    print("🎉 成功申请并添加匿名Token!")
    print("=" * 80)
    print(f"✅ Refresh Token: {refresh_token[:50]}...")
    print(f"✅ 已添加到.env文件")
    print(f"\n💡 下次启动服务器时，Token Pool会自动加载这个匿名Token")


if __name__ == "__main__":
    asyncio.run(main())

