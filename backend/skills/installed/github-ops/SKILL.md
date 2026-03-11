---
name: github-ops
description: GitHub 操作技能 - 创建仓库、推送代码、管理 Release。通过 GitHub REST API 和 Git CLI 实现全自动操作。
tags:
  - github
  - git
  - 仓库
  - repo
  - 推送
  - push
  - release
  - 代码托管
metadata:
  openclaw:
    emoji: "🐙"
    requires:
      bins:
        - git
        - curl
      env:
        - GITHUB_TOKEN
    primaryEnv: GITHUB_TOKEN
---

# GitHub Operations Skill

通过 `sandbox_shell` 工具调用 `git` 和 `curl` 命令，完成 GitHub 仓库管理操作。

**前提**: 环境变量 `GITHUB_TOKEN` 已配置（系统在安装时会引导用户输入）。

---

## 使用方式

所有操作通过 `sandbox_shell` 工具执行。`GITHUB_TOKEN` 已作为环境变量注入，可在命令中直接通过 `%GITHUB_TOKEN%`（Windows）或 `$GITHUB_TOKEN`（Linux/Mac）引用。

---

## 核心功能

### 1. 获取当前用户信息

首先确认 Token 有效并获取用户名：

```bash
curl -s -H "Authorization: token %GITHUB_TOKEN%" https://api.github.com/user
```

从返回的 JSON 中提取 `login` 字段作为用户名。

### 2. 创建仓库

```bash
curl -s -X POST -H "Authorization: token %GITHUB_TOKEN%" -H "Content-Type: application/json" https://api.github.com/user/repos -d "{\"name\":\"仓库名\",\"description\":\"描述\",\"private\":false}"
```

参数说明：
- `name`: 仓库名称（必填）
- `description`: 仓库描述
- `private`: 是否私有仓库（true/false）

### 3. 推送代码

```bash
git init
git add .
git commit -m "提交信息"
git remote add origin https://%GITHUB_TOKEN%@github.com/用户名/仓库名.git
git push -u origin main
```

如果 remote 已存在，先移除再添加：
```bash
git remote remove origin
git remote add origin https://%GITHUB_TOKEN%@github.com/用户名/仓库名.git
```

### 4. 创建 Release

先创建 tag，再通过 API 创建 Release：

```bash
git tag v1.0.0
git push origin v1.0.0
curl -s -X POST -H "Authorization: token %GITHUB_TOKEN%" -H "Content-Type: application/json" https://api.github.com/repos/用户名/仓库名/releases -d "{\"tag_name\":\"v1.0.0\",\"name\":\"v1.0.0\",\"body\":\"Release 说明\"}"
```

### 5. 列出用户仓库

```bash
curl -s -H "Authorization: token %GITHUB_TOKEN%" "https://api.github.com/user/repos?sort=updated&per_page=10"
```

### 6. 查看仓库信息

```bash
curl -s -H "Authorization: token %GITHUB_TOKEN%" https://api.github.com/repos/用户名/仓库名
```

---

## 执行流程

1. 先调用 `sandbox_shell` 执行 `curl` 获取用户信息，确认 Token 有效
2. 根据用户需求选择对应操作
3. 通过 `sandbox_shell` 执行 `git` 或 `curl` 命令
4. 解析返回结果，向用户报告操作结果

## 注意事项

- 所有 `curl` 和 `git` 命令通过 `sandbox_shell` 工具执行
- `GITHUB_TOKEN` 需要有对应权限（repo、workflow 等）
- 推送代码时，工作目录需在 workspace 范围内
- 创建仓库前应先检查同名仓库是否已存在
