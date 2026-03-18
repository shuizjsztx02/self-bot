# Self-Bot Docker 部署脚本 (Windows PowerShell)
# 使用方法: .\deploy.ps1 [命令]
# 命令: start | stop | restart | rebuild | logs | status

param(
    [Parameter(Position=0)]
    [ValidateSet("start", "stop", "restart", "rebuild", "logs", "status", "clean")]
    [string]$Action = "help"
)

$ComposeFile = "docker-compose.yml"
$ProjectName = "self-bot"

function Write-Info($message) {
    Write-Host "[INFO] " -ForegroundColor Green -NoNewline
    Write-Host $message
}

function Write-Warn($message) {
    Write-Host "[WARN] " -ForegroundColor Yellow -NoNewline
    Write-Host $message
}

function Write-Error($message) {
    Write-Host "[ERROR] " -ForegroundColor Red -NoNewline
    Write-Host $message
}

function Check-Env {
    if (-not (Test-Path "backend\.env")) {
        Write-Warn "backend\.env 文件不存在，正在从模板创建..."
        if (Test-Path "backend\.env.example") {
            Copy-Item "backend\.env.example" "backend\.env"
            Write-Info "已创建 backend\.env，请修改配置后重新运行"
            exit 1
        } else {
            Write-Error "找不到 backend\.env.example 模板文件"
            exit 1
        }
    }
}

function Start-Services {
    Write-Info "启动 Self-Bot 服务..."
    Check-Env
    docker-compose -f $ComposeFile -p $ProjectName up -d
    Write-Info "服务已启动，访问 http://localhost"
}

function Stop-Services {
    Write-Info "停止 Self-Bot 服务..."
    docker-compose -f $ComposeFile -p $ProjectName down
    Write-Info "服务已停止"
}

function Restart-Services {
    Write-Info "重启 Self-Bot 服务..."
    Stop-Services
    Start-Services
}

function Rebuild-Services {
    Write-Info "重新构建并启动 Self-Bot 服务..."
    Check-Env
    docker-compose -f $ComposeFile -p $ProjectName build --no-cache
    docker-compose -f $ComposeFile -p $ProjectName up -d --force-recreate
    Write-Info "服务已重新构建并启动"
}

function Show-Logs {
    docker-compose -f $ComposeFile -p $ProjectName logs -f --tail=100
}

function Show-Status {
    Write-Info "服务状态:"
    docker-compose -f $ComposeFile -p $ProjectName ps
}

function Clean-All {
    Write-Warn "这将删除所有容器、卷和镜像！"
    $confirm = Read-Host "确定要继续吗? (y/N)"
    if ($confirm -eq "y" -or $confirm -eq "Y") {
        docker-compose -f $ComposeFile -p $ProjectName down -v --rmi all
        Write-Info "清理完成"
    } else {
        Write-Info "已取消"
    }
}

switch ($Action) {
    "start" { Start-Services }
    "stop" { Stop-Services }
    "restart" { Restart-Services }
    "rebuild" { Rebuild-Services }
    "logs" { Show-Logs }
    "status" { Show-Status }
    "clean" { Clean-All }
    default {
        Write-Host "Self-Bot Docker 部署脚本"
        Write-Host ""
        Write-Host "使用方法: .\deploy.ps1 [命令]"
        Write-Host ""
        Write-Host "可用命令:"
        Write-Host "  start     - 启动服务"
        Write-Host "  stop      - 停止服务"
        Write-Host "  restart   - 重启服务"
        Write-Host "  rebuild   - 重新构建并启动服务"
        Write-Host "  logs      - 查看日志"
        Write-Host "  status    - 查看服务状态"
        Write-Host "  clean     - 清理所有容器、卷和镜像"
    }
}
