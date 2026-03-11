#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub仓库创建和代码推送工具
使用GitHub REST API v3
"""

import requests
import json
import os
import subprocess
import sys
from pathlib import Path

class GitHubRepoCreator:
    def __init__(self, token, username=None):
        """
        初始化GitHub API客户端
        
        Args:
            token: GitHub个人访问令牌
            username: GitHub用户名（可选，自动获取）
        """
        self.token = token
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        
        # 获取用户名
        if username:
            self.username = username
        else:
            self.username = self.get_username()
    
    def get_username(self):
        """获取GitHub用户名"""
        try:
            response = requests.get(
                "https://api.github.com/user",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()["login"]
        except Exception as e:
            print(f"获取用户名失败: {e}")
            return None
    
    def create_repository(self, repo_name, description="", private=False, auto_init=True):
        """
        创建GitHub仓库
        
        Args:
            repo_name: 仓库名称
            description: 仓库描述
            private: 是否私有仓库
            auto_init: 是否自动初始化README
        
        Returns:
            仓库信息字典
        """
        url = "https://api.github.com/user/repos"
        
        data = {
            "name": repo_name,
            "description": description,
            "private": private,
            "auto_init": auto_init,
            "gitignore_template": "Python"
        }
        
        try:
            print(f"正在创建仓库: {repo_name}")
            response = requests.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            
            repo_info = response.json()
            print(f"✅ 仓库创建成功!")
            print(f"   仓库名称: {repo_info['full_name']}")
            print(f"   仓库URL: {repo_info['html_url']}")
            print(f"   SSH URL: {repo_info['ssh_url']}")
            print(f"   HTTPS URL: {repo_info['clone_url']}")
            
            return repo_info
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 422:
                print(f"❌ 仓库已存在或名称无效: {repo_name}")
                # 尝试获取现有仓库信息
                return self.get_repository(repo_name)
            else:
                print(f"❌ 创建仓库失败: {e}")
                print(f"   状态码: {response.status_code}")
                print(f"   响应: {response.text}")
                return None
        except Exception as e:
            print(f"❌ 创建仓库时出错: {e}")
            return None
    
    def get_repository(self, repo_name):
        """获取仓库信息"""
        url = f"https://api.github.com/repos/{self.username}/{repo_name}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ 获取仓库信息失败: {e}")
            return None
    
    def push_to_github(self, repo_name, local_path=".", commit_message="Initial commit"):
        """
        推送本地代码到GitHub仓库
        
        Args:
            repo_name: 仓库名称
            local_path: 本地代码路径
            commit_message: 提交信息
        """
        repo_info = self.get_repository(repo_name)
        if not repo_info:
            print("❌ 无法获取仓库信息")
            return False
        
        clone_url = repo_info["clone_url"]
        ssh_url = repo_info["ssh_url"]
        
        print(f"准备推送代码到仓库: {repo_name}")
        print(f"本地路径: {local_path}")
        print(f"远程URL: {clone_url}")
        
        try:
            # 切换到本地目录
            original_dir = os.getcwd()
            local_path = Path(local_path).resolve()
            
            if not local_path.exists():
                print(f"❌ 本地路径不存在: {local_path}")
                return False
            
            os.chdir(local_path)
            
            # 初始化Git仓库（如果尚未初始化）
            if not (local_path / ".git").exists():
                print("初始化Git仓库...")
                subprocess.run(["git", "init"], check=True, capture_output=True)
            
            # 添加远程仓库
            print("配置远程仓库...")
            subprocess.run(["git", "remote", "remove", "origin"], 
                          capture_output=True, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "remote", "add", "origin", clone_url], check=True)
            
            # 配置Git用户信息（如果未配置）
            try:
                subprocess.run(["git", "config", "user.name"], 
                              check=True, capture_output=True)
            except:
                subprocess.run(["git", "config", "user.name", self.username], check=True)
            
            try:
                subprocess.run(["git", "config", "user.email"], 
                              check=True, capture_output=True)
            except:
                # 使用GitHub提供的noreply邮箱
                subprocess.run(["git", "config", "user.email", 
                              f"{self.username}@users.noreply.github.com"], check=True)
            
            # 添加所有文件
            print("添加文件到暂存区...")
            subprocess.run(["git", "add", "."], check=True)
            
            # 提交更改
            print(f"提交更改: {commit_message}")
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            
            # 推送代码（使用token认证）
            print("推送代码到GitHub...")
            
            # 修改远程URL以包含token
            auth_url = clone_url.replace(
                "https://github.com/",
                f"https://{self.username}:{self.token}@github.com/"
            )
            subprocess.run(["git", "remote", "set-url", "origin", auth_url], check=True)
            
            # 推送代码
            result = subprocess.run(["git", "push", "-u", "origin", "main"], 
                                   capture_output=True, text=True)
            
            if result.returncode != 0:
                # 尝试使用master分支
                result = subprocess.run(["git", "push", "-u", "origin", "master"], 
                                       capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ 代码推送成功!")
                print(f"   仓库地址: {repo_info['html_url']}")
                return True
            else:
                print("❌ 代码推送失败:")
                print(result.stderr)
                return False
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Git操作失败: {e}")
            print(f"   输出: {e.output}")
            return False
        except Exception as e:
            print(f"❌ 推送代码时出错: {e}")
            return False
        finally:
            os.chdir(original_dir)
    
    def test_connection(self):
        """测试GitHub API连接"""
        try:
            response = requests.get(
                "https://api.github.com/user",
                headers=self.headers
            )
            response.raise_for_status()
            user_info = response.json()
            print("✅ GitHub API连接成功!")
            print(f"   用户名: {user_info['login']}")
            print(f"   姓名: {user_info.get('name', '未设置')}")
            print(f"   邮箱: {user_info.get('email', '未公开')}")
            return True
        except Exception as e:
            print(f"❌ GitHub API连接失败: {e}")
            return False

def main():
    """主函数"""
    print("="*60)
    print("GitHub仓库创建和代码推送工具")
    print("="*60)
    
    # 检查是否已安装git
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    except:
        print("❌ 未安装Git，请先安装Git")
        print("   Windows: https://git-scm.com/download/win")
        print("   macOS: brew install git")
        print("   Linux: sudo apt-get install git")
        return
    
    # 获取GitHub Token
    print("\n🔑 需要GitHub个人访问令牌(PAT)")
    print("   1. 访问: https://github.com/settings/tokens")
    print("   2. 点击 'Generate new token (classic)'")
    print("   3. 选择权限: repo (完全控制仓库)")
    print("   4. 生成并复制token")
    
    token = input("\n请输入GitHub个人访问令牌: ").strip()
    
    if not token:
        print("❌ 未提供token，程序退出")
        return
    
    # 创建API客户端
    creator = GitHubRepoCreator(token)
    
    # 测试连接
    if not creator.test_connection():
        return
    
    # 获取仓库信息
    repo_name = input("\n请输入仓库名称 (例如: maotai-stock-analysis): ").strip()
    if not repo_name:
        repo_name = "maotai-stock-analysis"
    
    description = input("请输入仓库描述 (可选): ").strip()
    if not description:
        description = "贵州茅台(600519)股票数据分析工具"
    
    private_input = input("是否创建私有仓库? (y/N): ").strip().lower()
    private = private_input == 'y'
    
    # 创建仓库
    repo_info = creator.create_repository(
        repo_name=repo_name,
        description=description,
        private=private,
        auto_init=False  # 我们自己初始化
    )
    
    if not repo_info:
        print("❌ 仓库创建失败，程序退出")
        return
    
    # 推送代码
    print("\n准备推送代码...")
    local_path = input(f"请输入本地代码路径 (默认: {os.getcwd()}): ").strip()
    if not local_path:
        local_path = os.getcwd()
    
    commit_message = input("请输入提交信息 (默认: Initial commit): ").strip()
    if not commit_message:
        commit_message = "Initial commit: 贵州茅台股票数据分析工具"
    
    # 推送代码
    success = creator.push_to_github(
        repo_name=repo_name,
        local_path=local_path,
        commit_message=commit_message
    )
    
    if success:
        print("\n" + "="*60)
        print("✅ 任务完成!")
        print(f"   仓库地址: {repo_info['html_url']}")
        print(f"   克隆命令: git clone {repo_info['clone_url']}")
        print("="*60)
    else:
        print("\n❌ 代码推送失败，请检查错误信息")

if __name__ == "__main__":
    main()