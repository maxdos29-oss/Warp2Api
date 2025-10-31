#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check JWT token status"""

import os
import base64
import json
import time
from dotenv import load_dotenv

load_dotenv()

jwt = os.getenv('WARP_JWT', '')

if not jwt:
    print("❌ JWT token not found in .env")
    exit(1)

print(f"✅ JWT token found")
print(f"   Length: {len(jwt)} characters")

try:
    parts = jwt.split('.')
    if len(parts) != 3:
        print("❌ Invalid JWT format")
        exit(1)
    
    # Decode payload
    payload_b64 = parts[1]
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += '=' * padding
    
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    
    exp = payload.get('exp', 0)
    now = time.time()
    remaining_seconds = exp - now
    remaining_minutes = remaining_seconds / 60
    
    print(f"\n📅 Token Expiry Info:")
    print(f"   Expiry timestamp: {exp}")
    print(f"   Current timestamp: {int(now)}")
    print(f"   Remaining time: {int(remaining_minutes)} minutes ({int(remaining_seconds)} seconds)")
    
    if exp < now:
        print(f"\n❌ Token has EXPIRED {int(-remaining_minutes)} minutes ago!")
    elif remaining_minutes < 5:
        print(f"\n⚠️  Token will expire in {int(remaining_minutes)} minutes (CRITICAL)")
    elif remaining_minutes < 15:
        print(f"\n⚠️  Token will expire in {int(remaining_minutes)} minutes (WARNING)")
    else:
        print(f"\n✅ Token is valid for {int(remaining_minutes)} minutes")
    
    print(f"\n📋 Token Payload:")
    for key, value in payload.items():
        if key == 'exp':
            print(f"   {key}: {value} ({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(value))})")
        elif key == 'iat':
            print(f"   {key}: {value} ({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(value))})")
        else:
            print(f"   {key}: {value}")

except Exception as e:
    print(f"❌ Error decoding JWT: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

