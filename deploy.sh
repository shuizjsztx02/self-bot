#!/bin/bash

# Self-Bot Docker 部署脚本
# 使用方法: ./deploy.sh [命令]
# 命令: start | stop | restart | rebuild | logs | status

set -e

COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME="self-bot"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_env() {
    if [ ! -f "backend/.env" ]; then
        log_warn "backend/.env 文件不存在，正在从模板创建..."
        if [ -f "backend/.env.example" ]; then
            cp backend/.env.example backend/.env
            log_info "已创建 backend/.env，请修改配置后重新运行"
            exit 1
        else
            log_error "找不到 backend/.env.example 模板文件"
            exit 1
        fi
    fi
}

start() {
    log_info "启动 Self-Bot 服务..."
    check_env
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d
    log_info "服务已启动，访问 http://localhost"
}

stop() {
    log_info "停止 Self-Bot 服务..."
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down
    log_info "服务已停止"
}

restart() {
    log_info "重启 Self-Bot 服务..."
    stop
    start
}

rebuild() {
    log_info "重新构建并启动 Self-Bot 服务..."
    check_env
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME build --no-cache
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --force-recreate
    log_info "服务已重新构建并启动"
}

logs() {
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f --tail=100
}

status() {
    log_info "服务状态:"
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
}

clean() {
    log_warn "这将删除所有容器、卷和镜像！"
    read -p "确定要继续吗? (y/N): " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down -v --rmi all
        log_info "清理完成"
    else
        log_info "已取消"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    rebuild)
        rebuild
        ;;
    logs)
        logs
        ;;
    status)
        status
        ;;
    clean)
        clean
        ;;
    *)
        echo "Self-Bot Docker 部署脚本"
        echo ""
        echo "使用方法: $0 [命令]"
        echo ""
        echo "可用命令:"
        echo "  start     - 启动服务"
        echo "  stop      - 停止服务"
        echo "  restart   - 重启服务"
        echo "  rebuild   - 重新构建并启动服务"
        echo "  logs      - 查看日志"
        echo "  status    - 查看服务状态"
        echo "  clean     - 清理所有容器、卷和镜像"
        ;;
esac
