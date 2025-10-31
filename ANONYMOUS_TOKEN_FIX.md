# 🔧 匿名Token配额用尽自动刷新修复 (v2)

## 📋 问题描述

用户报告收到429错误：
```
WARP API HTTP ERROR (解析模式) 429: {"error":"No remaining quota: No AI requests remaining"}
```

**根本原因**：
- ❌ 内置的匿名token配额已用尽
- ❌ 系统没有自动申请新的匿名token
- ❌ Token pool中的下一个token选择逻辑有问题（可能重复选择同一个失败的token）
- ❌ **关键问题**: 第一次请求时 `current_token_refresh = None`，无法排除当前失败的token

## 🎯 解决方案

### 1. **添加获取最后使用Token的方法** ✅

添加了新方法 `get_last_used_token()` 来获取最近使用的token：

**文件**: `warp2protobuf/core/token_pool.py` (第222-239行)

```python
def get_last_used_token(self) -> Optional[TokenInfo]:
    """
    Get the most recently used token.

    Returns:
        TokenInfo if available, None if no tokens have been used
    """
    if not self._tokens:
        return None

    # Find the token with the most recent last_used timestamp
    most_recent = None
    for token in self._tokens:
        if token.last_used > 0:
            if most_recent is None or token.last_used > most_recent.last_used:
                most_recent = token

    return most_recent
```

### 2. **修复Token选择逻辑** ✅

添加了新方法 `get_next_token_excluding()` 来排除当前失败的token：

**文件**: `warp2protobuf/core/token_pool.py` (第241-281行)

```python
async def get_next_token_excluding(self, exclude_token: Optional[str] = None) -> Optional[TokenInfo]:
    """
    Get the next available token, excluding a specific token.
    Useful when current token fails and we need to try a different one.
    
    Args:
        exclude_token: refresh_token string to exclude from selection
        
    Returns:
        TokenInfo if available, None if no other tokens available
    """
    # 遍历所有优先级，排除指定的token
    for priority in [TokenPriority.ANONYMOUS, TokenPriority.SHARED, TokenPriority.PERSONAL]:
        priority_tokens = [
            t for t in self._tokens 
            if t.priority == priority 
            and t.is_active 
            and t.refresh_token not in self._failed_tokens
            and (exclude_token is None or t.refresh_token != exclude_token)  # 排除指定token
        ]
        
        if priority_tokens:
            # Round-robin选择
            return priority_tokens[idx]
    
    return None
```

### 3. **自动检测最后使用的Token** ✅

在429错误处理时，如果 `current_token_refresh` 为 `None`，自动检测最后使用的token：

**文件**: `warp2protobuf/warp/api_client.py`

#### **流式API修改** (第118-171行)

```python
# 检测配额耗尽错误
if response.status_code == 429 and attempt == 0:
    logger.warning("WARP API 返回 429 (配额用尽)。尝试从token pool获取下一个token并重试…")
    try:
        # 获取token pool
        pool = await get_token_pool()

        # 如果current_token_refresh为None，尝试获取最后使用的token
        if current_token_refresh is None:
            last_used = pool.get_last_used_token()
            if last_used:
                current_token_refresh = last_used.refresh_token
                logger.info(f"🔍 检测到最后使用的token: {last_used.name}")

        # 获取下一个token（排除当前失败的token）
        token_info = await pool.get_next_token_excluding(current_token_refresh)
        
        if not token_info:
            # 没有其他token了，尝试申请新的匿名token
            logger.warning("⚠️ Token pool中没有其他可用token，尝试申请新的匿名token…")
            try:
                new_jwt = await acquire_anonymous_access_token()
                if new_jwt:
                    logger.info("✅ 成功申请新的匿名token")
                    jwt = new_jwt
                    current_token_refresh = None  # 新的匿名token
                    continue
            except Exception as anon_err:
                logger.error(f"❌ 申请匿名token失败: {anon_err}")
            
            # 所有尝试都失败
            return error_response
        
        # 使用token pool中的下一个token
        if token_info.cached_jwt:
            jwt = token_info.cached_jwt
            current_token_refresh = token_info.refresh_token
            continue
        else:
            # 刷新JWT
            token_data = await refresh_jwt_token_with_token_info(token_info)
            if token_data and "access_token" in token_data:
                jwt = token_data["access_token"]
                current_token_refresh = token_info.refresh_token
                continue
    except Exception as e:
        logger.error(f"❌ Token pool处理失败: {e}")
```

#### **解析模式API修改** (第371-423行)

相同的逻辑应用到解析模式API，包括自动检测最后使用的token。

### 4. **跟踪当前使用的Token** ✅

添加了 `current_token_refresh` 变量来跟踪当前正在使用的refresh token：

```python
current_token_refresh = None  # Track which refresh token is being used

# 当使用token pool中的token时
current_token_refresh = token_info.refresh_token

# 当申请新的匿名token时
current_token_refresh = None  # 新的匿名token没有refresh token
```

这样可以确保在429错误时，不会重复选择同一个失败的token。

## 🔄 工作流程

```
用户请求
   ↓
使用匿名Token (ANONYMOUS_xxxx)
   ↓
收到429错误 (配额用尽)
   ↓
调用 get_next_token_excluding(ANONYMOUS_xxxx)
   ↓
找到其他token? 
   ↓ 是
使用个人Token (PERSONAL_xxxx) ✅
   ↓ 否
调用 acquire_anonymous_access_token() ✅
   ↓
申请新的匿名token
   ↓
成功? → ✅ 使用新token重试
   ↓ 否
❌ 返回错误
```

## 📊 修改总结

### **修改的文件**

1. ✅ `warp2protobuf/core/token_pool.py`
   - 添加 `get_last_used_token()` 方法（第222-239行）
   - 添加 `get_next_token_excluding()` 方法（第241-281行）

2. ✅ `warp2protobuf/warp/api_client.py`
   - 添加 `current_token_refresh` 跟踪变量（流式API第89行，解析模式API第330行）
   - 添加自动检测最后使用token的逻辑（流式API第123-128行，解析模式API第376-381行）
   - 修改429错误处理逻辑（流式API第118-171行，解析模式API第371-423行）
   - 删除重复的匿名token申请代码

### **新增的功能**

1. ✅ **自动检测最后使用的Token** - 解决 `current_token_refresh = None` 的问题
2. ✅ **智能Token选择** - 排除当前失败的token
3. ✅ **自动申请新匿名Token** - 当所有token都失败时
4. ✅ **Token使用跟踪** - 避免重复使用失败的token

### **删除的代码**

- ❌ 删除了重复的匿名token申请逻辑（旧代码在token pool失败后直接调用 `acquire_anonymous_access_token()`）
- ❌ 删除了多余的异常处理代码

## 🎯 预期效果

### **修改前**

```
匿名Token配额用尽 (429)
   ↓
尝试获取下一个token
   ↓
可能还是选择同一个匿名token ❌
   ↓
再次失败 ❌
```

### **修改后**

```
匿名Token配额用尽 (429)
   ↓
排除当前失败的匿名token
   ↓
选择个人Token ✅
   ↓
成功! ✅

或者：

匿名Token配额用尽 (429)
   ↓
没有其他token
   ↓
自动申请新的匿名token ✅
   ↓
成功! ✅
```

## 🚀 如何验证

### 1. **重启服务器**

```bash
# 停止当前服务器 (Ctrl+C)
uv run python server.py
```

### 2. **发送测试请求**

当匿名token配额用尽时，您会看到：

```
❌ Warp API返回错误状态码: 429
   错误内容: {"error":"No remaining quota: No AI requests remaining"}
   响应头: {...}
   请求大小: 178 字节
   尝试次数: 1/2
⚠️ WARP API 返回 429 (配额用尽)。尝试从token pool获取下一个token并重试…
🔍 检测到最后使用的token: ANONYMOUS_xxxx
🎯 Selected token (excluding AMf-vBxd...): PERSONAL_5739 (priority: PERSONAL)
✅ 使用token pool中的下一个token: PERSONAL_5739
✅ 收到HTTP 200响应
```

或者（如果没有个人token）：

```
❌ Warp API返回错误状态码: 429
   错误内容: {"error":"No remaining quota: No AI requests remaining"}
⚠️ WARP API 返回 429 (配额用尽)。尝试从token pool获取下一个token并重试…
🔍 检测到最后使用的token: ANONYMOUS_xxxx
⚠️ Token pool中没有其他可用token，尝试申请新的匿名token…
Acquiring anonymous access token via GraphQL + Identity Toolkit…
✅ 成功申请新的匿名token
✅ 收到HTTP 200响应
```

### 3. **验证成功**

请求应该成功完成：
```
✅ 收到HTTP 200响应
开始处理SSE事件流...
```

## 💡 关键改进

### **1. 自动检测最后使用的Token** ⭐ NEW

**问题**: 第一次请求时 `current_token_refresh = None`，无法排除当前失败的token。

**解决**: 添加 `get_last_used_token()` 方法，在429错误时自动检测最后使用的token。

```python
# 如果current_token_refresh为None，尝试获取最后使用的token
if current_token_refresh is None:
    last_used = pool.get_last_used_token()
    if last_used:
        current_token_refresh = last_used.refresh_token
        logger.info(f"🔍 检测到最后使用的token: {last_used.name}")
```

### **2. 避免重复选择失败的Token**

**问题**: 之前的 `get_next_token()` 方法按优先级选择，可能重复选择同一个失败的token。

**解决**: 新的 `get_next_token_excluding()` 方法可以排除指定的token。

### **3. 自动刷新匿名Token配额**

**问题**: 匿名token配额用尽后，没有自动申请新的匿名token。

**解决**: 当token pool中没有其他可用token时，自动调用 `acquire_anonymous_access_token()`。

### **4. 更清晰的Token跟踪**

**问题**: 不知道当前使用的是哪个token。

**解决**: 使用 `current_token_refresh` 变量跟踪当前token。

## 📝 注意事项

### **匿名Token的特点**

1. **动态申请** - 通过调用Warp API的GraphQL接口申请
2. **有配额限制** - 每个匿名token有使用次数限制
3. **可以重复申请** - 配额用尽后可以申请新的匿名token
4. **无需登录** - 不需要用户账号

### **Token优先级**

当前优先级（从高到低）：
1. 匿名Token (ANONYMOUS) - 优先使用，节省个人配额
2. 共享Token (SHARED) - 中等优先级
3. 个人Token (PERSONAL) - 保底使用

### **配额管理策略**

- ✅ 优先消耗匿名token配额
- ✅ 匿名token失败时切换到个人token
- ✅ 所有token都失败时自动申请新的匿名token
- ✅ 最大化可用性和配额利用率

## 🎉 总结

这次修复（v2）解决了四个关键问题：

1. ✅ **自动检测最后使用的Token** - 解决 `current_token_refresh = None` 的问题 ⭐ NEW
2. ✅ **Token选择逻辑** - 避免重复选择失败的token
3. ✅ **自动配额刷新** - 自动申请新的匿名token
4. ✅ **Token跟踪** - 清楚知道当前使用的token

现在系统可以：
- ✅ 自动检测最后使用的token（即使 `current_token_refresh = None`）
- ✅ 智能地在多个token之间切换
- ✅ 自动处理配额用尽的情况
- ✅ 最大化服务可用性

**请重启服务器测试新的功能！** 🚀

---

## 🔍 调试建议

如果429错误仍然出现，请检查日志中是否有：

```
🔍 检测到最后使用的token: ANONYMOUS_xxxx
```

如果看到这行日志，说明自动检测功能正常工作。

如果没有看到，可能是：
1. Token pool初始化失败
2. 没有可用的token
3. 所有token都已失败

请提供完整的错误日志以便进一步诊断。

