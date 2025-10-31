# 🚀 Warp2Api 启动指南

## 📋 问题诊断

您之前遇到的429错误没有触发token切换，是因为：

❌ **只启动了 `openai_compat.py`，没有启动 `server.py`**

Warp2Api 需要**两个服务器**同时运行：

```
┌─────────────────────┐
│  openai_compat.py   │  端口 28889 (OpenAI兼容层)
│  (您正在运行的)      │
└──────────┬──────────┘
           │ HTTP请求
           ↓
┌─────────────────────┐
│     server.py       │  端口 28888 (主服务器)
│  (需要启动这个!)     │  ← 我们修改的代码在这里
└──────────┬──────────┘
           │
           ↓
      Warp API
```

## ✅ 正确的启动方式

### **方法1：使用启动脚本（推荐）**

```powershell
# 一键启动两个服务器
.\start_servers.ps1
```

这个脚本会：
1. ✅ 检查端口是否被占用
2. ✅ 启动主服务器 (server.py)
3. ✅ 等待主服务器就绪
4. ✅ 启动 OpenAI 兼容层 (openai_compat.py)
5. ✅ 监控服务器状态

**停止服务器**：按 `Ctrl+C`

---

### **方法2：手动启动（用于调试）**

#### **步骤1：启动主服务器**

打开**第一个终端**：

```powershell
uv run python server.py
```

等待看到：
```
✅ Token Pool已初始化 (优先使用匿名Token以节省个人配额)
🌐 Warp2Api服务器已启动
   监听地址: http://0.0.0.0:28888
```

#### **步骤2：启动 OpenAI 兼容层**

打开**第二个终端**：

```powershell
uv run python openai_compat.py
```

等待看到：
```
[OpenAI Compat] Bridge server is ready at http://127.0.0.1:28888/healthz
Uvicorn running on http://127.0.0.1:28889
```

---

## 🔍 验证服务器状态

### **检查端口监听**

```powershell
netstat -ano | findstr "28888 28889"
```

应该看到两个端口都在监听：
```
TCP    0.0.0.0:28888    0.0.0.0:0    LISTENING    12345
TCP    127.0.0.1:28889  0.0.0.0:0    LISTENING    67890
```

### **测试健康检查**

```powershell
# 测试主服务器
curl http://127.0.0.1:28888/healthz

# 测试 OpenAI 兼容层
curl http://127.0.0.1:28889/healthz
```

---

## 🎯 验证429错误修复

启动服务器后，发送测试请求，您应该看到：

### **主服务器日志** (server.py)

```
❌ Warp API返回错误状态码: 429
   错误内容: {"error":"No remaining quota: No AI requests remaining"}
   响应头: {...}
   请求大小: 178 字节
   尝试次数: 1/2
⚠️ WARP API 返回 429 (配额用尽)。尝试从token pool获取下一个token并重试…
🔍 检测到最后使用的token: ANONYMOUS_xxxx  ← 关键日志
🎯 Selected token (excluding AMf-vBxd...): PERSONAL_5739 (priority: PERSONAL)
✅ 使用token pool中的下一个token: PERSONAL_5739
🔄 刷新token pool中的token: PERSONAL_5739
✅ Token刷新成功，使用新JWT重试
✅ 收到HTTP 200响应
```

### **OpenAI 兼容层日志** (openai_compat.py)

```
[OpenAI Compat] Bridge request URL: http://127.0.0.1:28888/api/warp/send_stream
[OpenAI Compat] Bridge response: {"response":"...", "conversation_id":"...", ...}
```

---

## 🐛 故障排查

### **问题1：端口被占用**

```
⚠️ 端口 28888 已被占用
```

**解决方法**：

```powershell
# 查找占用端口的进程
netstat -ano | findstr "28888"

# 结束进程（替换 PID 为实际进程ID）
taskkill /F /PID <PID>
```

### **问题2：主服务器启动失败**

**检查日志**：

```powershell
# 查看最新的日志文件
Get-Content warp_api.log -Tail 50
```

**常见原因**：
- ❌ `.env` 文件配置错误
- ❌ Token配置问题
- ❌ 依赖包未安装

### **问题3：OpenAI 兼容层无法连接主服务器**

**检查配置**：

```powershell
# 查看 .env 文件中的配置
Get-Content .env | Select-String "WARP_BRIDGE_URL"
```

应该是：
```
WARP_BRIDGE_URL=http://127.0.0.1:28888
```

### **问题4：仍然收到429错误且没有token切换**

**可能原因**：
1. ❌ 主服务器没有运行（只运行了 openai_compat.py）
2. ❌ 使用的是旧版本的代码
3. ❌ Token pool中没有其他可用token

**检查方法**：

```powershell
# 检查主服务器是否在运行
netstat -ano | findstr "28888"

# 如果没有输出，说明主服务器没有运行
# 请启动主服务器：
uv run python server.py
```

---

## 📊 服务器架构

```
┌─────────────────────────────────────────────────────────┐
│                    客户端请求                            │
│              (OpenAI API 格式)                          │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│          openai_compat.py (端口 28889)                  │
│                                                          │
│  - 接收 OpenAI 格式的请求                                │
│  - 转换为 Warp API 格式                                  │
│  - 调用主服务器的 HTTP API                               │
│  - 转换响应为 OpenAI 格式                                │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP 请求
                     ↓
┌─────────────────────────────────────────────────────────┐
│            server.py (端口 28888)                       │
│                                                          │
│  - Token Pool 管理                                       │
│  - JWT 刷新                                              │
│  - Protobuf 编码/解码                                    │
│  - 429 错误处理 ← 我们修改的代码在这里                   │
│  - Token 自动切换                                        │
│  - 匿名 Token 申请                                       │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│                  Warp API                                │
│         (https://app.warp.dev/ai/multi-agent)           │
└─────────────────────────────────────────────────────────┘
```

---

## 📝 配置文件说明

### **.env 文件**

```env
# 主服务器URL（openai_compat.py 需要连接这个地址）
WARP_BRIDGE_URL=http://127.0.0.1:28888

# 个人Token（可选，用于保底）
WARP_REFRESH_TOKEN=your_refresh_token_here

# JWT Token（自动生成，无需手动配置）
WARP_JWT=auto_generated

# 日志级别
W2A_VERBOSE=false
```

---

## 🎉 成功标志

当两个服务器都正常运行时，您会看到：

### **主服务器 (server.py)**

```
============================================================
🚀 Warp2Api 服务器启动
============================================================
✅ Token Pool已初始化 (优先使用匿名Token以节省个人配额)
   📊 总Token数: 2
   ✅ 活跃Token数: 2
   
   使用优先级 (从高到低):
   1️⃣  匿名Token数: 1 (最优先)
   2️⃣  共享Token数: 0
   3️⃣  个人Token数: 1 (保底使用)
============================================================
✅ JWT token有效
============================================================
🌐 Warp2Api服务器已启动
   监听地址: http://0.0.0.0:28888
```

### **OpenAI 兼容层 (openai_compat.py)**

```
[OpenAI Compat] Server starting. BRIDGE_BASE_URL=http://127.0.0.1:28888
[OpenAI Compat] Endpoints: GET /healthz, GET /v1/models, POST /v1/chat/completions
[OpenAI Compat] Bridge server is ready at http://127.0.0.1:28888/healthz
Uvicorn running on http://127.0.0.1:28889 (Press CTRL+C to quit)
```

---

## 💡 提示

1. **推荐使用启动脚本** (`start_servers.ps1`) 来避免手动管理两个终端
2. **查看日志文件** (`warp_api.log`) 来诊断问题
3. **确保两个服务器都在运行** 才能看到token切换功能
4. **第一次启动可能需要等待** JWT token刷新

---

**现在请使用启动脚本启动服务器，然后测试429错误处理！** 🚀

