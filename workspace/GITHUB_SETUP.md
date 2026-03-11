# GitHub仓库创建和代码推送指南

## 准备工作

### 1. 安装Git
确保您的系统已安装Git：

```bash
# 检查Git是否已安装
git --version
```

如果未安装，请访问 https://git-scm.com/downloads 下载并安装。

### 2. 创建GitHub个人访问令牌(PAT)

1. 访问 https://github.com/settings/tokens
2. 点击 "Generate new token (classic)"
3. 输入令牌描述（例如：Stock Analysis Tool）
4. 选择权限：
   - ✅ **repo** (完全控制仓库)
   - ✅ **workflow** (可选，如果需要GitHub Actions)
5. 点击 "Generate token"
6. **重要**：立即复制生成的token，离开页面后将无法再次查看

### 3. 安装Python依赖

```bash
pip install requests
```

## 使用方法

### 方法一：使用提供的脚本（推荐）

1. **运行GitHub仓库创建脚本**：
   ```bash
   python create_github_repo.py
   ```

2. **按照提示操作**：
   - 输入GitHub个人访问令牌
   - 输入仓库名称（例如：maotai-stock-analysis）
   - 输入仓库描述（可选）
   - 选择是否创建私有仓库
   - 指定本地代码路径
   - 输入提交信息

### 方法二：手动创建和推送

#### 1. 创建GitHub仓库

使用GitHub网站：
1. 访问 https://github.com/new
2. 填写仓库信息：
   - Repository name: maotai-stock-analysis
   - Description: 贵州茅台(600519)股票数据分析工具
   - 选择Public或Private
   - **不要**勾选 "Initialize this repository with a README"
3. 点击 "Create repository"

#### 2. 初始化本地Git仓库

```bash
# 进入项目目录
cd /path/to/your/project

# 初始化Git仓库
git init

# 配置用户信息
git config user.name "您的GitHub用户名"
git config user.email "您的GitHub邮箱"

# 添加所有文件
git add .

# 提交更改
git commit -m "Initial commit: 贵州茅台股票数据分析工具"
```

#### 3. 连接到远程仓库并推送

```bash
# 添加远程仓库（替换YOUR_USERNAME和YOUR_TOKEN）
git remote add origin https://YOUR_USERNAME:YOUR_TOKEN@github.com/YOUR_USERNAME/maotai-stock-analysis.git

# 推送代码
git push -u origin main

# 如果使用master分支
git push -u origin master
```

## 文件说明

### 核心文件
1. **get_maotai_stock_data.py** - 获取茅台股票数据的主脚本
2. **create_github_repo.py** - GitHub仓库创建和推送脚本
3. **requirements.txt** - Python依赖列表
4. **README.md** - 项目说明文档

### 生成的数据文件（不会被推送到GitHub）
- `maotai_600519_daily_kline_*.csv` - CSV格式股票数据
- `maotai_600519_daily_kline_*.json` - JSON格式股票数据

## 安全注意事项

### 🔒 保护您的GitHub Token
1. **不要**将token提交到Git仓库
2. **不要**在公共场合分享token
3. 定期更新和轮换token
4. 使用环境变量存储token：

```bash
# Linux/macOS
export GITHUB_TOKEN="your_token_here"

# Windows (PowerShell)
$env:GITHUB_TOKEN="your_token_here"

# Windows (CMD)
set GITHUB_TOKEN=your_token_here
```

### 修改脚本使用环境变量
编辑 `create_github_repo.py`，将：
```python
token = input("\n请输入GitHub个人访问令牌: ").strip()
```
改为：
```python
token = os.environ.get("GITHUB_TOKEN") or input("\n请输入GitHub个人访问令牌: ").strip()
```

## 故障排除

### 常见问题

#### 1. "Permission denied" 错误
- 检查token是否有足够的权限（需要repo权限）
- 确认token未过期
- 检查用户名和token是否正确

#### 2. "Repository already exists" 错误
- 仓库名称已被使用，请选择其他名称
- 或者删除现有的同名仓库

#### 3. Git推送失败
- 检查网络连接
- 确认本地Git已正确配置
- 检查远程仓库URL是否正确

#### 4. Python依赖安装失败
```bash
# 使用国内镜像源
pip install requests -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 调试建议

1. **测试GitHub API连接**：
   ```bash
   curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
   ```

2. **检查Git配置**：
   ```bash
   git config --list
   ```

3. **验证远程仓库**：
   ```bash
   git remote -v
   ```

## 后续步骤

### 1. 设置GitHub Actions（可选）
创建 `.github/workflows/ci.yml` 文件来自动化测试和部署。

### 2. 添加更多功能
- 添加技术指标计算
- 实现数据可视化
- 添加自动更新功能
- 集成其他数据源

### 3. 分享项目
- 添加开源许可证（如MIT License）
- 完善文档
- 发布到PyPI（如果作为库使用）

## 获取帮助

如果遇到问题：
1. 查看GitHub文档：https://docs.github.com
2. 检查脚本输出的错误信息
3. 搜索相关错误解决方案
4. 在GitHub Issues中提问

---

**注意**：股票数据仅供参考，投资有风险，入市需谨慎。