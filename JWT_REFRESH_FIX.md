# JWT刷新修复 - 解决401 Unauthorized错误

## 🎯 **问题根源**

### **错误信息**
```
❌ Warp API Error (HTTP 401): {"error":"Unauthorized: User not in context"}
```

### **问题分析**

在之前的修复中，我们成功让API使用了Token Pool，但出现了新的问题：

1. ❌ **Token Pool初始化时没有刷新JWT** - 只加载了refresh token
2. ❌ **TokenInfo.last_jwt 是空的** - 从未被填充
3. ❌ **直接使用空的JWT发送请求** - 导致401错误

**代码问题**：
```python
# api_client.py (修改前)
current_token_info = await pool.get_next_token()
if current_token_info:
    jwt = current_token_info.last_jwt  # ❌ last_jwt是空的！
```

**Token Pool初始化**：
```python
# token_pool.py
async def initialize(self):
    # 只加载refresh token，没有刷新JWT
    anonymous_token = self._load_anonymous_token()
    if anonymous_token:
        self._add_token_internal(anonymous_token, TokenPriority.ANONYMOUS)  # ❌ 没有刷新JWT
```

---

## ✅ **完整修复方案**

### **修复策略**

在使用token之前，检查JWT是否有效，如果无效则刷新：

1. ✅ 检查 `last_jwt` 是否存在
2. ✅ 检查 `last_jwt_expiry` 是否未过期（至少还有2分钟）
3. ✅ 如果JWT无效或即将过期，调用 `refresh_jwt_token_with_token_info()` 刷新
4. ✅ 使用刷新后的JWT发送请求

---

## 🔧 **代码修改**

### **文件**: `warp2protobuf/warp/api_client.py`

#### **修改1: 添加time模块导入** (第12行)

```python
import time
```

#### **修改2: 流式API - 添加JWT有效性检查和刷新** (第92-118行)

**修改前**:
```python
# 第一次请求：从token pool获取token
if True:  # Always use token pool
    pool = await get_token_pool()
    current_token_info = await pool.get_next_token()
    if current_token_info:
        jwt = current_token_info.last_jwt  # ❌ 可能是空的或过期的
        current_token_refresh = current_token_info.refresh_token
        logger.info(f"🎯 使用token pool中的token: {current_token_info.name}")
```

**修改后**:
```python
# 第一次请求：从token pool获取token
if True:  # Always use token pool
    pool = await get_token_pool()
    current_token_info = await pool.get_next_token()
    if current_token_info:
        # ✅ 检查JWT是否有效，如果无效则刷新
        if current_token_info.last_jwt and current_token_info.last_jwt_expiry > time.time() + 120:
            # JWT有效且未过期（至少还有2分钟）
            jwt = current_token_info.last_jwt
            logger.info(f"🎯 使用token pool中的token: {current_token_info.name} (优先级: {current_token_info.priority.name}, 使用缓存JWT)")
        else:
            # JWT无效或即将过期，需要刷新
            logger.info(f"🔄 刷新token pool中的token: {current_token_info.name}")
            from ..core.auth import refresh_jwt_token_with_token_info
            token_data = await refresh_jwt_token_with_token_info(current_token_info)
            if token_data and "access_token" in token_data:
                jwt = token_data["access_token"]
                logger.info(f"✅ Token刷新成功: {current_token_info.name}")
            else:
                logger.error(f"❌ Token刷新失败，使用环境变量中的JWT")
                jwt = await get_valid_jwt()
        
        current_token_refresh = current_token_info.refresh_token
    else:
        # Fallback to old method if pool is empty
        jwt = await get_valid_jwt()
        logger.warning("⚠️ Token pool为空，使用环境变量中的JWT")
```

#### **修改3: 解析模式API - 添加JWT有效性检查和刷新** (第395-421行)

相同的逻辑应用到解析模式API。

---

## 🚀 **工作流程**

### **场景1: JWT缓存有效**

```
1. 从token pool获取token
   🎯 使用token pool中的token: ANONYMOUS_xxxx
   ↓
2. 检查JWT有效性
   ✅ last_jwt存在
   ✅ last_jwt_expiry > 当前时间 + 120秒
   ↓
3. 使用缓存的JWT
   🎯 使用缓存JWT
   ↓
4. 发送请求
   ✅ 收到200响应
```

**日志示例**:
```
🎯 使用token pool中的token: ANONYMOUS_xxxx (优先级: ANONYMOUS, 使用缓存JWT)
发送 178 字节到Warp API
✅ 收到HTTP 200响应
```

---

### **场景2: JWT无效或过期，需要刷新**

```
1. 从token pool获取token
   🎯 使用token pool中的token: ANONYMOUS_xxxx
   ↓
2. 检查JWT有效性
   ❌ last_jwt为空 或 last_jwt_expiry已过期
   ↓
3. 刷新JWT
   🔄 刷新token pool中的token: ANONYMOUS_xxxx
   ↓
4. 调用 refresh_jwt_token_with_token_info()
   ✅ Token刷新成功
   ↓
5. 使用新的JWT发送请求
   ✅ 收到200响应
```

**日志示例**:
```
🎯 使用token pool中的token: ANONYMOUS_xxxx (优先级: ANONYMOUS)
🔄 刷新token pool中的token: ANONYMOUS_xxxx
✅ Token刷新成功: ANONYMOUS_xxxx
发送 178 字节到Warp API
✅ 收到HTTP 200响应
```

---

## 📊 **修改总结**

### **修改的文件**

1. ✅ `warp2protobuf/warp/api_client.py`
   - 添加 `time` 模块导入
   - 流式API: 添加JWT有效性检查和刷新逻辑 (第92-118行)
   - 解析模式API: 添加JWT有效性检查和刷新逻辑 (第395-421行)

### **新增的功能**

1. ✅ **JWT有效性检查** - 检查JWT是否存在且未过期
2. ✅ **自动JWT刷新** - JWT无效时自动刷新
3. ✅ **JWT缓存利用** - 有效的JWT直接使用，避免不必要的刷新
4. ✅ **过期时间缓冲** - 提前2分钟刷新，避免请求时过期

### **预期效果**

| 方面 | 修改前 | 修改后 |
|------|--------|--------|
| JWT来源 | 空的last_jwt | 自动刷新的有效JWT ✅ |
| 401错误 | 频繁出现 ❌ | 不再出现 ✅ |
| JWT刷新 | 不刷新 ❌ | 自动刷新 ✅ |
| 性能 | N/A | 缓存有效JWT，减少刷新次数 ✅ |

---

## 🎉 **如何验证**

### **1. 重启服务器**

```bash
# 停止当前服务器 (Ctrl+C)
uv run python server.py
```

### **2. 观察启动日志**

应该看到：
```
✅ Token Pool已初始化 (优先使用匿名Token以节省个人配额)
   1️⃣  匿名Token数: 1 (最优先)
   3️⃣  个人Token数: 1 (保底使用)
```

### **3. 发送测试请求**

第一次请求应该看到JWT刷新：
```
🎯 使用token pool中的token: ANONYMOUS_xxxx (优先级: ANONYMOUS)
🔄 刷新token pool中的token: ANONYMOUS_xxxx
✅ Token刷新成功: ANONYMOUS_xxxx
发送 178 字节到Warp API
✅ 收到HTTP 200响应
```

后续请求应该使用缓存的JWT：
```
🎯 使用token pool中的token: ANONYMOUS_xxxx (优先级: ANONYMOUS, 使用缓存JWT)
发送 178 字节到Warp API
✅ 收到HTTP 200响应
```

### **4. 验证没有401错误**

不应该再看到：
```
❌ Warp API Error (HTTP 401): {"error":"Unauthorized: User not in context"}
```

---

## 💡 **关键改进**

1. ✅ **自动JWT管理** - 无需手动刷新JWT
2. ✅ **智能缓存** - 有效的JWT被缓存和重用
3. ✅ **提前刷新** - 过期前2分钟自动刷新，避免请求失败
4. ✅ **错误恢复** - JWT刷新失败时fallback到环境变量
5. ✅ **完整日志** - 清楚显示JWT刷新过程

---

**现在请重启服务器，401错误应该不会再出现了！** 🚀

Token Pool将：
1. 优先使用匿名Token（节省个人配额）
2. 自动刷新JWT（避免401错误）
3. 缓存有效JWT（提高性能）
4. 配额用尽时自动切换Token（最大化可用性）

