# Warp2Api 服务器启动脚本
# 
# 此脚本会启动两个服务器：
# 1. server.py (端口28888) - 主服务器，处理Warp API请求
# 2. openai_compat.py (端口28889) - OpenAI兼容层
#
# 使用方法：
#   .\start_servers.ps1
#
# 停止服务器：
#   按 Ctrl+C

Write-Host "🚀 启动 Warp2Api 服务器..." -ForegroundColor Green
Write-Host ""

# 检查是否已有服务器在运行
$port28888 = Get-NetTCPConnection -LocalPort 28888 -ErrorAction SilentlyContinue
$port28889 = Get-NetTCPConnection -LocalPort 28889 -ErrorAction SilentlyContinue

if ($port28888) {
    Write-Host "⚠️  端口 28888 已被占用，请先停止现有服务器" -ForegroundColor Yellow
    Write-Host "   可以使用以下命令查看进程："
    Write-Host "   Get-Process | Where-Object {`$_.Id -eq $($port28888.OwningProcess)}"
    exit 1
}

if ($port28889) {
    Write-Host "⚠️  端口 28889 已被占用，请先停止现有服务器" -ForegroundColor Yellow
    Write-Host "   可以使用以下命令查看进程："
    Write-Host "   Get-Process | Where-Object {`$_.Id -eq $($port28889.OwningProcess)}"
    exit 1
}

Write-Host "📋 启动步骤：" -ForegroundColor Cyan
Write-Host "   1. 启动主服务器 (server.py) 在端口 28888"
Write-Host "   2. 等待主服务器就绪"
Write-Host "   3. 启动 OpenAI 兼容层 (openai_compat.py) 在端口 28889"
Write-Host ""

# 启动主服务器
Write-Host "🔧 [1/2] 启动主服务器 (server.py)..." -ForegroundColor Green
$serverJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    uv run python server.py
}

Write-Host "   ✅ 主服务器已启动 (Job ID: $($serverJob.Id))" -ForegroundColor Green
Write-Host "   ⏳ 等待主服务器就绪..." -ForegroundColor Yellow

# 等待主服务器启动
$maxWait = 30
$waited = 0
$serverReady = $false

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 1
    $waited++
    
    # 检查端口是否开始监听
    $port28888 = Get-NetTCPConnection -LocalPort 28888 -ErrorAction SilentlyContinue
    if ($port28888) {
        $serverReady = $true
        Write-Host "   ✅ 主服务器已就绪 (用时 $waited 秒)" -ForegroundColor Green
        break
    }
    
    # 显示进度
    if ($waited % 5 -eq 0) {
        Write-Host "   ⏳ 等待中... ($waited/$maxWait 秒)" -ForegroundColor Yellow
    }
}

if (-not $serverReady) {
    Write-Host "   ❌ 主服务器启动超时" -ForegroundColor Red
    Write-Host "   请检查日志文件查看错误信息"
    Stop-Job -Job $serverJob
    Remove-Job -Job $serverJob
    exit 1
}

Write-Host ""

# 启动 OpenAI 兼容层
Write-Host "🔧 [2/2] 启动 OpenAI 兼容层 (openai_compat.py)..." -ForegroundColor Green
$compatJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    uv run python openai_compat.py
}

Write-Host "   ✅ OpenAI 兼容层已启动 (Job ID: $($compatJob.Id))" -ForegroundColor Green
Write-Host "   ⏳ 等待 OpenAI 兼容层就绪..." -ForegroundColor Yellow

# 等待 OpenAI 兼容层启动
$maxWait = 10
$waited = 0
$compatReady = $false

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 1
    $waited++
    
    # 检查端口是否开始监听
    $port28889 = Get-NetTCPConnection -LocalPort 28889 -ErrorAction SilentlyContinue
    if ($port28889) {
        $compatReady = $true
        Write-Host "   ✅ OpenAI 兼容层已就绪 (用时 $waited 秒)" -ForegroundColor Green
        break
    }
}

if (-not $compatReady) {
    Write-Host "   ❌ OpenAI 兼容层启动超时" -ForegroundColor Red
    Write-Host "   请检查日志文件查看错误信息"
    Stop-Job -Job $serverJob, $compatJob
    Remove-Job -Job $serverJob, $compatJob
    exit 1
}

Write-Host ""
Write-Host "=" * 60 -ForegroundColor Green
Write-Host "🎉 所有服务器已成功启动！" -ForegroundColor Green
Write-Host "=" * 60 -ForegroundColor Green
Write-Host ""
Write-Host "📡 服务器信息：" -ForegroundColor Cyan
Write-Host "   主服务器:        http://127.0.0.1:28888"
Write-Host "   OpenAI 兼容层:   http://127.0.0.1:28889"
Write-Host ""
Write-Host "📝 API 端点：" -ForegroundColor Cyan
Write-Host "   健康检查:        http://127.0.0.1:28889/healthz"
Write-Host "   模型列表:        http://127.0.0.1:28889/v1/models"
Write-Host "   聊天补全:        http://127.0.0.1:28889/v1/chat/completions"
Write-Host ""
Write-Host "📋 日志文件：" -ForegroundColor Cyan
Write-Host "   主服务器:        warp_api.log"
Write-Host "   OpenAI 兼容层:   (控制台输出)"
Write-Host ""
Write-Host "⚠️  按 Ctrl+C 停止所有服务器" -ForegroundColor Yellow
Write-Host ""

# 监控服务器状态
try {
    while ($true) {
        Start-Sleep -Seconds 5
        
        # 检查服务器是否还在运行
        $serverState = Get-Job -Id $serverJob.Id -ErrorAction SilentlyContinue
        $compatState = Get-Job -Id $compatJob.Id -ErrorAction SilentlyContinue
        
        if ($serverState.State -ne "Running") {
            Write-Host "❌ 主服务器已停止" -ForegroundColor Red
            break
        }
        
        if ($compatState.State -ne "Running") {
            Write-Host "❌ OpenAI 兼容层已停止" -ForegroundColor Red
            break
        }
    }
} catch {
    Write-Host ""
    Write-Host "🛑 正在停止服务器..." -ForegroundColor Yellow
} finally {
    # 清理
    Write-Host "🧹 清理资源..." -ForegroundColor Yellow
    Stop-Job -Job $serverJob, $compatJob -ErrorAction SilentlyContinue
    Remove-Job -Job $serverJob, $compatJob -ErrorAction SilentlyContinue
    Write-Host "✅ 所有服务器已停止" -ForegroundColor Green
}

