# 🔐 多Token配置指南

## 📋 问题分析

根据您的日志，系统遇到了以下问题：

1. **429错误** - Token配额已用尽
2. **500错误** - 服务器内部错误（可能是token失效导致）
3. **多Token功能未启用** - 系统仍在使用旧的单token逻辑

## ✅ 已完成的修复

我已经修复了以下问题：

### 1. 集成Token Pool到API客户端

修改了以下文件，使其在遇到429错误时使用token pool：

- ✅ `warp2protobuf/warp/api_client.py` - 主API客户端
- ✅ `warp2protobuf/api/protobuf_routes.py` - SSE代理路由
- ✅ `server.py` - 启动时显示token pool信息

### 2. 新的429错误处理流程

现在当遇到429错误时，系统会：

1. 🔄 首先尝试从token pool获取下一个可用token
2. ✅ 如果token有缓存的JWT，直接使用
3. 🔄 如果token需要刷新，自动刷新JWT
4. 🔁 自动重试请求
5. 👤 如果所有tokens都失败，才会尝试申请匿名token作为最后手段

## 🚀 如何配置多Token

### 方案1: 单个个人Token（当前配置）

您当前的 `.env` 文件：

```env
WARP_REFRESH_TOKEN='AMf-vBxd1ju5RCkWFuQCfqsbEIpThIhPt26ff1Vd3XwX2oYYN4nzxbKsI8CB0y-9tAL1d_LWit8n4GuXEccaqpvsFoscRCd5V7QarE__pXI7hbW1NKNJe_jpD2Nd-bhdu5GFjyim6EYtqRDBNLZ54QSY4fXuIISVxjDheO877U7fcz95Gjtd9yuHfe91lkkrwh76GCdl7B7x'
```

这个配置只有1个token，当它配额用尽时就会失败。

### 方案2: 多个个人Tokens（推荐）

如果您有多个Warp账号，可以配置多个tokens：

```env
# 保留原有的单个token（最高优先级）
WARP_REFRESH_TOKEN='AMf-vBxd1ju5RCkWFuQCfqsbEIpThIhPt26ff1Vd3XwX2oYYN4nzxbKsI8CB0y-9tAL1d_LWit8n4GuXEccaqpvsFoscRCd5V7QarE__pXI7hbW1NKNJe_jpD2Nd-bhdu5GFjyim6EYtqRDBNLZ54QSY4fXuIISVxjDheO877U7fcz95Gjtd9yuHfe91lkkrwh76GCdl7B7x'

# 添加更多个人tokens（用逗号分隔，不要有空格）
WARP_PERSONAL_TOKENS='token2_here,token3_here,token4_here'
```

### 方案3: 个人 + 共享 + 匿名（完整配置）

```env
# 个人tokens（最高优先级）
WARP_REFRESH_TOKEN='your_personal_token_1'
WARP_PERSONAL_TOKENS='personal_token_2,personal_token_3'

# 共享tokens（中等优先级）- 当个人token都失败时使用
WARP_SHARED_TOKENS='shared_token_1,shared_token_2,shared_token_3'

# 匿名token（最低优先级）- 最后的后备方案
WARP_ANONYMOUS_TOKEN='anonymous_token_here'
```

## 🔍 Token优先级说明

系统会按以下顺序选择token：

```
1. PERSONAL (个人token) - 最高优先级 ⭐⭐⭐
   ├─ WARP_REFRESH_TOKEN (单个)
   └─ WARP_PERSONAL_TOKENS (多个)
   
2. SHARED (共享token) - 中等优先级 ⭐⭐
   └─ WARP_SHARED_TOKENS
   
3. ANONYMOUS (匿名token) - 最低优先级 ⭐
   └─ WARP_ANONYMOUS_TOKEN 或内置token
```

同优先级内采用**轮询(round-robin)**策略，确保负载均衡。

## 🛠️ 如何获取更多Tokens

### 方法1: 从其他Warp账号获取

1. 在另一台设备或浏览器上登录不同的Warp账号
2. 使用开发者工具获取refresh token
3. 添加到 `.env` 文件的 `WARP_PERSONAL_TOKENS` 中

### 方法2: 使用团队共享Token

如果您在团队中使用，可以：

1. 从团队管理员获取共享tokens
2. 添加到 `.env` 文件的 `WARP_SHARED_TOKENS` 中

### 方法3: 使用匿名Token

系统会自动申请匿名token作为后备，无需手动配置。

## 📊 验证配置

### 1. 重启服务器

```bash
# 停止当前服务器 (Ctrl+C)
# 重新启动
uv run python server.py
```

### 2. 查看启动日志

启动时应该看到类似的输出：

```
============================================================
🔐 初始化Token Pool...
✅ Token Pool已初始化
   📊 总Token数: 5
   ✅ 活跃Token数: 5
   ❌ 失败Token数: 0
   🔝 个人Token数: 3
   🤝 共享Token数: 2
   👤 匿名Token数: 0

📋 Token Pool详细信息:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Token名称                优先级    状态    失败次数  最后使用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Personal-1              PERSONAL  ✅      0         从未使用
Personal-2              PERSONAL  ✅      0         从未使用
Personal-3              PERSONAL  ✅      0         从未使用
Shared-1                SHARED    ✅      0         从未使用
Shared-2                SHARED    ✅      0         从未使用
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
============================================================
```

### 3. 测试API请求

发送一个测试请求，观察日志：

```bash
# 使用curl测试
curl -X POST http://localhost:28888/api/warp/send_stream \
  -H "Content-Type: application/json" \
  -d '{"message_type": "warp.multi_agent.v1.Request", "data": {...}}'
```

### 4. 观察Token切换

当遇到429错误时，应该看到：

```
⚠️ WARP API 返回 429 (配额用尽)。尝试从token pool获取下一个token并重试…
✅ 使用token pool中的下一个token: Personal-2
🔄 刷新token pool中的token: Personal-2
✅ Token刷新成功，使用新JWT重试
```

## 🔧 故障排除

### 问题1: Token Pool未初始化

**症状**: 启动时没有看到Token Pool信息

**解决方案**:
1. 检查 `.env` 文件是否存在
2. 确保至少配置了 `WARP_REFRESH_TOKEN`
3. 重启服务器

### 问题2: 所有Tokens都失败

**症状**: 日志显示 "❌ 所有token尝试失败"

**解决方案**:
1. 检查tokens是否有效（未过期）
2. 检查网络连接
3. 尝试手动刷新tokens：
   ```bash
   uv run python -c "from warp2protobuf.core.auth import recover_failed_tokens; import asyncio; asyncio.run(recover_failed_tokens())"
   ```

### 问题3: 仍然遇到429错误

**症状**: 配置多个tokens后仍然遇到429

**可能原因**:
1. 所有tokens的配额都已用尽
2. Tokens未正确配置
3. Token格式错误（包含空格或引号）

**解决方案**:
1. 等待配额重置（通常每天重置）
2. 添加更多有效的tokens
3. 检查 `.env` 文件格式：
   ```env
   # ❌ 错误 - 包含空格
   WARP_PERSONAL_TOKENS='token1, token2, token3'
   
   # ✅ 正确 - 无空格
   WARP_PERSONAL_TOKENS='token1,token2,token3'
   ```

### 问题4: 500错误

**症状**: API返回500错误

**可能原因**:
1. Token已失效
2. 请求格式错误
3. Warp服务器问题

**解决方案**:
1. 刷新所有tokens
2. 检查请求数据格式
3. 查看详细错误日志

## 📈 监控Token健康状态

### 查看Token Pool状态

```python
from warp2protobuf.core.auth import print_token_pool_info
import asyncio

asyncio.run(print_token_pool_info())
```

### 执行健康检查

```python
from warp2protobuf.core.auth import check_token_pool_health
import asyncio

health = asyncio.run(check_token_pool_health())
print(health)
```

### 恢复失败的Tokens

```python
from warp2protobuf.core.auth import recover_failed_tokens
import asyncio

asyncio.run(recover_failed_tokens())
```

## 🎯 最佳实践

1. **至少配置3个tokens** - 确保高可用性
2. **定期检查token健康状态** - 及时发现问题
3. **使用不同优先级** - 个人token优先，共享token作为后备
4. **监控配额使用** - 避免所有tokens同时耗尽
5. **定期更新tokens** - 替换失效的tokens

## 📞 需要帮助？

如果您在配置过程中遇到问题：

1. 查看启动日志中的Token Pool信息
2. 检查 `.env` 文件格式
3. 运行测试脚本验证配置：
   ```bash
   uv run python test_token_pool.py
   ```
4. 查看详细文档：`docs/MULTI_TOKEN_GUIDE.md`

## 🎉 配置完成后

重启服务器，您应该会看到：

- ✅ Token Pool成功初始化
- ✅ 显示所有配置的tokens
- ✅ 遇到429错误时自动切换token
- ✅ 请求成功率大幅提升

祝使用愉快！🚀

