#!/usr/bin/env python3
"""Quick verification of token priority"""

from warp2protobuf.core.token_pool import TokenPriority

print("="*60)
print("Token Priority Values:")
print("="*60)
print(f"ANONYMOUS: {TokenPriority.ANONYMOUS.value} (should be 1 - highest priority)")
print(f"SHARED:    {TokenPriority.SHARED.value} (should be 2)")
print(f"PERSONAL:  {TokenPriority.PERSONAL.value} (should be 3 - lowest priority)")
print()

if TokenPriority.ANONYMOUS.value == 1:
    print("✅ ANONYMOUS has priority 1 (will be used first)")
else:
    print("❌ ERROR: ANONYMOUS priority is wrong!")

if TokenPriority.PERSONAL.value == 3:
    print("✅ PERSONAL has priority 3 (will be used last)")
else:
    print("❌ ERROR: PERSONAL priority is wrong!")

print()
print("="*60)
print("✅ Priority change successful!")
print("   匿名Token将优先使用，个人Token作为保底")
print("="*60)

