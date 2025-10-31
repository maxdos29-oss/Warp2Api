# Warp2Api

基于 Python 的桥接服务，为 Warp AI 服务提供 OpenAI Chat Completions API 兼容性，通过利用 Warp 的 protobuf 基础架构，实现与 OpenAI 兼容应用程序的无缝集成。

## 🚀 特性

- **OpenAI API 兼容性**: 完全支持 OpenAI Chat Completions API 格式
- **Warp 集成**: 使用 protobuf 通信与 Warp AI 服务无缝桥接
- **双服务器架构**: 
  - 用于 Warp 通信的 Protobuf 编解码服务器
  - 用于客户端应用程序的 OpenAI 兼容 API 服务器
- **JWT 认证**: Warp 服务的自动令牌管理和刷新
- **流式支持**: 与 OpenAI SSE 格式兼容的实时流式响应
- **WebSocket 监控**: 内置监控和调试功能
- **消息重排序**: 针对 Anthropic 风格对话的智能消息处理

## 📋 系统要求

- Python 3.9+ (推荐 3.13+)
- Warp AI 服务访问权限（JWT 令牌会自动获取）
- 支持 Linux、macOS 和 Windows

## 🛠️ 安装

1. **克隆仓库:**
   ```bash
   git clone <repository-url>
   cd Warp2Api
   ```

2. **使用 uv 安装依赖 (推荐):**
   ```bash
   uv sync
   ```

   或使用 pip:
   ```bash
   pip install -e .
   ```

3. **配置环境变量:**
    程序会自动获取匿名JWT TOKEN，您无需手动配置。

    如需自定义配置，可以创建 `.env` 文件:
    ```env
    # Warp2Api 配置
    # 设置为 true 启用详细日志输出，默认 false（静默模式）
    W2A_VERBOSE=false

    # Bridge服务器URL配置
    WARP_BRIDGE_URL=http://127.0.0.1:28888

    # 禁用代理以避免连接问题
    HTTP_PROXY=
    HTTPS_PROXY=
    NO_PROXY=127.0.0.1,localhost

    # ==================== 多Token配置（推荐） ====================
    # 支持配置多个refresh token，系统会按优先级自动选择和轮换

    # 个人refresh token（最高优先级，优先使用）
    WARP_REFRESH_TOKEN=your_personal_token_here

    # 多个个人tokens（可选，逗号分隔）
    # 如果有多个个人账号，可以配置多个token，系统会自动轮换
    # WARP_PERSONAL_TOKENS=token1,token2,token3

    # 共享tokens（中等优先级，可选）
    # 团队共享的tokens，当个人token失败时使用
    # WARP_SHARED_TOKENS=shared_token1,shared_token2

    # 匿名token（最低优先级，可选）
    # 如果不配置，会使用内置的匿名token作为后备
    # WARP_ANONYMOUS_TOKEN=anonymous_token_here
    ```

## 🎯 使用方法

### 快速开始

#### 方法一：一键启动脚本（推荐）

**Linux/macOS:**
```bash
# 启动所有服务器
./start.sh

# 停止所有服务器
./stop.sh

# 查看服务器状态
./stop.sh status
```

**Windows:**
```batch
REM 使用批处理脚本
start.bat          # 启动服务器
stop.bat           # 停止服务器
stop.bat status    # 查看服务器状态
test.bat           # 测试API接口功能

REM 或使用 PowerShell 脚本
.\start.ps1        # 启动服务器
.\start.ps1 -Stop  # 停止服务器
.\start.ps1 -Verbose  # 启用详细日志

REM 测试脚本
test.bat           # 测试API接口功能（静默模式）
test.bat -v        # 测试API接口功能（详细模式）
```

启动脚本会自动：
- ✅ 检查Python环境和依赖
- ✅ 自动配置环境变量（包括API_TOKEN自动设置为"0000"）
- ✅ 按正确顺序启动两个服务器
- ✅ 验证服务器健康状态（循环检查healthz端点）
- ✅ 显示关键配置信息
- ✅ 显示完整的 API 接口 Token
- ✅ 显示 Roocode / KiloCode baseUrl
- ✅ 实时监控服务器日志（verbose模式）
- ✅ 提供详细的错误处理和状态反馈

### 📸 运行演示

#### 项目启动界面
![项目启动界面](docs/screenshots/运行截图.png)

#### 使用示例
![使用示例](docs/screenshots/使用截图.png)

#### 方法二：手动启动

1. **启动 Protobuf 桥接服务器:**
   ```bash
   python server.py
   ```
   默认地址: `http://localhost:28888`

2. **启动 OpenAI 兼容 API 服务器:**
   ```bash
   python openai_compat.py
   ```
   默认地址: `http://localhost:28889`

### 支持的模型

Warp2Api 支持以下 AI 模型：

#### Anthropic Claude 系列
- `claude-4-sonnet` - Claude 4 Sonnet 模型
- `claude-4-opus` - Claude 4 Opus 模型
- `claude-4.1-opus` - Claude 4.1 Opus 模型

#### Google Gemini 系列
- `gemini-2.5-pro` - Gemini 2.5 Pro 模型

#### OpenAI GPT 系列
- `gpt-4.1` - GPT-4.1 模型
- `gpt-4o` - GPT-4o 模型
- `gpt-5` - GPT-5 基础模型
- `gpt-5 (high reasoning)` - GPT-5 高推理模式

#### OpenAI o系列
- `o3` - o3 模型
- `o4-mini` - o4-mini 模型

### 使用 API

#### 🔓 认证说明
**重要：Warp2Api 的 OpenAI 兼容接口不需要 API key 验证！**

- 服务器会自动处理 Warp 服务的认证
- 客户端可以发送任意的 `api_key` 值（或完全省略）
- 所有请求都会使用系统自动获取的匿名 JWT token

两个服务器都运行后，您可以使用任何 OpenAI 兼容的客户端:

#### Python 示例
```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:28889/v1",
    api_key="dummy"  # 可选：某些客户端需要，但服务器不强制验证
)

response = client.chat.completions.create(
    model="claude-4-sonnet",  # 选择支持的模型
    messages=[
        {"role": "user", "content": "你好，你好吗？"}
    ],
    stream=True
)

for chunk in response:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

#### cURL 示例
```bash
# 基本请求
curl -X POST http://localhost:28889/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-4-sonnet",
    "messages": [
      {"role": "user", "content": "你好，请介绍一下你自己"}
    ],
    "stream": true
  }'

# 指定其他模型
curl -X POST http://localhost:28889/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5",
    "messages": [
      {"role": "user", "content": "解释量子计算的基本原理"}
    ],
    "temperature": 0.7,
    "max_tokens": 1000
  }'
```

#### JavaScript/Node.js 示例
```javascript
const OpenAI = require('openai');

const client = new OpenAI({
  baseURL: 'http://localhost:28889/v1',
  apiKey: 'dummy'  // 可选：某些客户端需要，但服务器不强制验证
});

async function main() {
  const completion = await client.chat.completions.create({
    model: 'gemini-2.5-pro',
    messages: [
      { role: 'user', content: '写一个简单的Hello World程序' }
    ],
    stream: true
  });

  for await (const chunk of completion) {
    process.stdout.write(chunk.choices[0]?.delta?.content || '');
  }
}

main();
```

### 模型选择建议

- **编程任务**: 推荐使用 `claude-4-sonnet` 或 `gpt-5`
- **创意写作**: 推荐使用 `claude-4-opus` 或 `gpt-4o`
- **代码审查**: 推荐使用 `claude-4.1-opus`
- **推理任务**: 推荐使用 `gpt-5 (high reasoning)` 或 `o3`
- **轻量任务**: 推荐使用 `o4-mini` 或 `gpt-4o`

### 可用端点

#### Protobuf 桥接服务器 (`http://localhost:28888`)
- `GET /healthz` - 健康检查
- `POST /encode` - 将 JSON 编码为 protobuf
- `POST /decode` - 将 protobuf 解码为 JSON
- `WebSocket /ws` - 实时监控

#### OpenAI API 服务器 (`http://localhost:28889`)
- `GET /` - 服务状态
- `GET /healthz` - 健康检查
- `POST /v1/chat/completions` - OpenAI Chat Completions 兼容端点

## 🏗️ 架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│    客户端应用     │───▶│  OpenAI API     │───▶│   Protobuf      │
│  (OpenAI SDK)   │    │     服务器      │    │    桥接服务器    │
└─────────────────┘    │  (端口 28889)   │    │  (端口 28888)   │
                        └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │    Warp AI      │
                                               │      服务       │
                                               └─────────────────┘
```

### 核心组件

- **`protobuf2openai/`**: OpenAI API 兼容层
  - 消息格式转换
  - 流式响应处理
  - 错误映射和验证

- **`warp2protobuf/`**: Warp protobuf 通信层
  - JWT 认证管理
  - Protobuf 编解码
  - WebSocket 监控
  - 请求路由和验证

## 🔧 配置

### 多Token配置（新功能）

Warp2Api 现在支持配置多个refresh token，实现智能负载均衡和自动故障转移。

#### Token优先级策略

系统按以下优先级使用token：

1. **个人Token（最高优先级）** 🔑
   - 从 `WARP_REFRESH_TOKEN` 或 `WARP_PERSONAL_TOKENS` 读取
   - 优先使用，适合个人账号
   - 支持配置多个，自动轮换使用

2. **共享Token（中等优先级）** 👥
   - 从 `WARP_SHARED_TOKENS` 读取
   - 团队共享使用，当个人token失败时启用
   - 支持配置多个，自动轮换使用

3. **匿名Token（最低优先级）** 🌐
   - 从 `WARP_ANONYMOUS_TOKEN` 读取，或使用内置token
   - 作为最后的后备方案
   - 确保服务始终可用

#### 配置示例

```env
# 单个个人token
WARP_REFRESH_TOKEN=AMf-vBxSRmdh...

# 或配置多个个人tokens（逗号分隔）
WARP_PERSONAL_TOKENS=token1_here,token2_here,token3_here

# 可选：配置共享tokens
WARP_SHARED_TOKENS=shared_token1,shared_token2

# 可选：配置匿名token（不配置则使用内置）
WARP_ANONYMOUS_TOKEN=anonymous_token_here
```

#### 特性

- ✅ **自动轮换**：同优先级的token自动轮换使用，避免单个token过载
- ✅ **故障转移**：token失败时自动切换到下一个可用token
- ✅ **健康监控**：自动监控token健康状态，失败3次后自动禁用
- ✅ **自动恢复**：支持手动或自动恢复失败的token
- ✅ **优先使用个人token**：确保个人账号的token优先被使用

### 环境变量

| 变量 | 描述 | 默认值 |
|------|------|--------|
| `WARP_JWT` | Warp 认证 JWT 令牌 | 自动获取 |
| `WARP_REFRESH_TOKEN` | 个人JWT刷新令牌（单个） | 可选 |
| `WARP_PERSONAL_TOKENS` | 个人JWT刷新令牌（多个，逗号分隔） | 可选 |
| `WARP_SHARED_TOKENS` | 共享JWT刷新令牌（多个，逗号分隔） | 可选 |
| `WARP_ANONYMOUS_TOKEN` | 匿名JWT刷新令牌 | 可选（有内置） |
| `WARP_BRIDGE_URL` | Protobuf 桥接服务器 URL | `http://127.0.0.1:28888` |
| `HTTP_PROXY` | HTTP 代理设置 | 空（禁用代理） |
| `HTTPS_PROXY` | HTTPS 代理设置 | 空（禁用代理） |
| `NO_PROXY` | 不使用代理的主机 | `127.0.0.1,localhost` |
| `HOST` | 服务器主机地址 | `127.0.0.1` |
| `PORT` | OpenAI API 服务器端口 | `28889` |
| `API_TOKEN` | API接口认证令牌 | `0000`（自动设置） |
| `W2A_VERBOSE` | 启用详细日志输出 | `false` |

### 项目脚本

在 `pyproject.toml` 中定义:

```bash
# 启动 protobuf 桥接服务器
warp-server

# 启动 OpenAI API 服务器  
warp-test
```

## 🔐 认证

服务会自动处理 Warp 认证，支持多token智能管理:

1. **多Token池管理**: 支持配置多个refresh token，自动轮换和负载均衡
2. **优先级策略**: 个人token > 共享token > 匿名token，确保个人账号优先使用
3. **JWT 自动刷新**: 自动令牌验证和刷新，无需手动干预
4. **故障自动转移**: Token失败时自动切换到下一个可用token
5. **健康监控**: 实时监控token健康状态，自动禁用失败token
6. **令牌持久化**: 安全的令牌存储和重用

### Token管理工作流程

```
请求到达
    ↓
从Token池获取token（按优先级）
    ↓
尝试刷新JWT
    ↓
成功？ ──是──→ 返回JWT，重置失败计数
    ↓
    否
    ↓
失败计数+1
    ↓
达到最大失败次数？ ──是──→ 禁用该token
    ↓
    否
    ↓
切换到下一个token，重试
```

## 🧪 开发

### 项目结构

```
Warp2Api/
├── protobuf2openai/          # OpenAI API 兼容层
│   ├── app.py               # FastAPI 应用程序
│   ├── router.py            # API 路由
│   ├── models.py            # Pydantic 模型
│   ├── bridge.py            # 桥接初始化
│   └── sse_transform.py     # 服务器发送事件
├── warp2protobuf/           # Warp protobuf 层
│   ├── api/                 # API 路由
│   ├── core/                # 核心功能
│   │   ├── auth.py          # 认证
│   │   ├── protobuf_utils.py # Protobuf 工具
│   │   └── logging.py       # 日志设置
│   ├── config/              # 配置
│   └── warp/                # Warp 特定代码
├── server.py                # Protobuf 桥接服务器
├── openai_compat.py         # OpenAI API 服务器
├── start.sh                 # Linux/macOS 启动脚本
├── stop.sh                  # Linux/macOS 停止脚本
├── test.sh                  # Linux/macOS 测试脚本
├── start.bat                # Windows 批处理启动脚本
├── stop.bat                 # Windows 批处理停止脚本
├── test.bat                 # Windows 批处理测试脚本
├── start.ps1                # Windows PowerShell 启动脚本
├── docs/                    # 项目文档
│   ├── TROUBLESHOOTING.md   # 故障排除指南
│   └── screenshots/         # 项目截图
└── pyproject.toml           # 项目配置
```

### 截图演示

项目运行截图和界面演示请查看 [`docs/screenshots/`](docs/screenshots/) 文件夹。

## 📋 文档

主要依赖项包括:
- **FastAPI**: 现代、快速的 Web 框架
- **Uvicorn**: ASGI 服务器实现
- **HTTPx**: 支持 HTTP/2 的异步 HTTP 客户端
- **Protobuf**: Protocol buffer 支持
- **WebSockets**: WebSocket 通信
- **OpenAI**: 用于类型兼容性

## 🐛 故障排除

详细的故障排除指南请参考 [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md)

### 常见问题

1. **"Server disconnected without sending a response" 错误**
    - 检查 `.env` 文件中的 `WARP_BRIDGE_URL` 配置是否正确
    - 确保代理设置已禁用：`HTTP_PROXY=`, `HTTPS_PROXY=`, `NO_PROXY=127.0.0.1,localhost`
    - 验证桥接服务器是否在端口 28888 上运行
    - 检查防火墙是否阻止了本地连接

2. **JWT 令牌过期**
    - 服务会自动刷新令牌
    - 检查日志中的认证错误
    - 验证 `WARP_REFRESH_TOKEN` 是否有效

3. **桥接服务器未就绪**
    - 确保首先运行 protobuf 桥接服务器
    - 检查 `WARP_BRIDGE_URL` 配置（应为 `http://127.0.0.1:28888`）
    - 验证端口可用性

4. **代理连接错误**
    - 如果遇到 `ProxyError` 或端口 1082 错误
    - 在 `.env` 文件中设置：`HTTP_PROXY=`, `HTTPS_PROXY=`, `NO_PROXY=127.0.0.1,localhost`
    - 或者在系统环境中禁用代理

5. **连接错误**
    - 检查到 Warp 服务的网络连接
    - 验证防火墙设置
    - 确保本地端口 28888 和 28889 未被其他应用占用

### 日志记录

两个服务器都提供详细的日志记录:
- 认证状态和令牌刷新
- 请求/响应处理
- 错误详情和堆栈跟踪
- 性能指标

## 📄 许可证

该项目配置为内部使用。请与项目维护者联系了解许可条款。

## 🤝 贡献

1. Fork 仓库
2. 创建功能分支
3. 进行更改
4. 如适用，添加测试
5. 提交 pull request

## 📞 支持

如有问题和疑问:
1. 查看故障排除部分
2. 查看服务器日志获取错误详情
3. 创建包含重现步骤的 issue