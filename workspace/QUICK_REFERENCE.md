# 快速参考卡 - ClawHub 模式管理

## 🎯 当前状态

```
状态: ✅ Mock 模式
配置: CLAWHUB_USE_MOCK = True
功能: ✅ 完整可用
```

---

## 🚀 一行启动命令

```bash
# 后端
cd backend && python main.py

# 前端（新终端）
cd frontend && npm run dev

# 访问
http://localhost:5173
```

---

## 💻 一行测试命令

```bash
# 用这个 query 测试完整链路
帮我在 Notion 工作区创建一个项目管理系统，需要能查询数据库和创建新的任务页面
```

---

## 🔄 快速切换模式

```bash
# 查看当前模式
python switch_clawhub_mode.py status

# 切到 Mock（推荐，当前已是）
python switch_clawhub_mode.py mock

# 切到真实（需要网络和 ClawHub 可用）
python switch_clawhub_mode.py real
```

---

## 📍 关键文件位置

| 文件 | 用途 |
|------|------|
| `backend/app/config.py` L127 | ClawHub 模式配置 |
| `switch_clawhub_mode.py` | 一键切换工具 |
| `test_real_clawhub.py` | 连接性测试 |

---

## 📚 查看更多信息

```bash
# 详细总结
cat CLAWHUB_SWITCH_SUMMARY.md

# 启动和测试完整指南
cat LAUNCH_GUIDE.md

# ClawHub 当前状态诊断
cat CLAWHUB_STATUS.md

# 真实模式详细指南
cat REAL_CLAWHUB_MODE.md
```

---

## ⚡ 故障排查

| 问题 | 解决方案 |
|------|--------|
| 后端无法启动 | `cd backend && pip install -r requirements.txt` |
| 前端无法启动 | `cd frontend && npm install` |
| 页面打不开 | 检查 http://localhost:5173 是否正确 |
| 没有看到对话框 | 检查浏览器控制台 (F12) 是否有错误 |
| 想用真实 ClawHub | `python switch_clawhub_mode.py real` + 重启后端 |

---

## 🎉 就这么简单！

**下一步**：启动后端和前端，输入推荐的 query，观看完整演示！
