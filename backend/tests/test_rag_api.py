"""
RAG 知识库 API 功能测试脚本

测试范围：
1. 认证功能测试
2. 知识库管理测试
3. 文档管理测试
4. 搜索功能测试
5. 权限管理测试
6. 用户组管理测试
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime
from typing import Optional, Dict, Any

BASE_URL = "http://localhost:8001"
TIMEOUT = 30.0

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []
    
    def add_pass(self, name: str):
        self.passed += 1
        print(f"  ✅ {name}")
    
    def add_fail(self, name: str, error: str):
        self.failed += 1
        self.errors.append((name, error))
        print(f"  ❌ {name}: {error}")
    
    def add_skip(self, name: str, reason: str):
        self.skipped += 1
        print(f"  ⏭️ {name}: {reason}")
    
    def summary(self):
        total = self.passed + self.failed + self.skipped
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)
        print(f"总计: {total} 测试")
        print(f"  ✅ 通过: {self.passed}")
        print(f"  ❌ 失败: {self.failed}")
        print(f"  ⏭️ 跳过: {self.skipped}")
        
        if self.errors:
            print("\n失败详情:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")


class APITester:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
        self.token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.user_id: Optional[str] = None
        self.kb_id: Optional[str] = None
        self.doc_id: Optional[str] = None
        self.folder_id: Optional[str] = None
        self.permission_id: Optional[str] = None
        self.group_id: Optional[str] = None
        self.result = TestResult()
    
    async def close(self):
        await self.client.aclose()
    
    def get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    async def test_health(self):
        """测试健康检查"""
        try:
            resp = await self.client.get("/api/health")
            if resp.status_code == 200:
                self.result.add_pass("健康检查")
            else:
                self.result.add_fail("健康检查", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("健康检查", str(e))
    
    async def test_register(self):
        """测试用户注册"""
        timestamp = int(datetime.now().timestamp())
        user_data = {
            "name": f"test_user_{timestamp}",
            "email": f"test_{timestamp}@example.com",
            "password": "Test123456",
            "department": "测试部门",
        }
        try:
            resp = await self.client.post("/api/auth/register", json=user_data)
            if resp.status_code == 201:
                data = resp.json()
                self.user_id = data.get("id")
                self.result.add_pass("用户注册")
            elif resp.status_code == 400:
                self.result.add_skip("用户注册", "用户已存在")
            else:
                self.result.add_fail("用户注册", f"状态码: {resp.status_code}, {resp.text}")
        except Exception as e:
            self.result.add_fail("用户注册", str(e))
    
    async def test_login(self):
        """测试用户登录"""
        if not self.user_id:
            login_data = {
                "email": "admin@example.com",
                "password": "admin123",
            }
        else:
            login_data = {
                "email": f"test_{int(datetime.now().timestamp())}@example.com",
                "password": "Test123456",
            }
        
        try:
            resp = await self.client.post("/api/auth/login", json=login_data)
            if resp.status_code == 200:
                data = resp.json()
                self.token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.result.add_pass("用户登录")
            else:
                resp = await self.client.post("/api/auth/login", json={
                    "email": "admin@example.com",
                    "password": "admin123"
                })
                if resp.status_code == 200:
                    data = resp.json()
                    self.token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    self.result.add_pass("用户登录 (admin)")
                else:
                    self.result.add_fail("用户登录", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("用户登录", str(e))
    
    async def test_get_current_user(self):
        """测试获取当前用户"""
        if not self.token:
            self.result.add_skip("获取当前用户", "未登录")
            return
        
        try:
            resp = await self.client.get("/api/auth/me", headers=self.get_headers())
            if resp.status_code == 200:
                self.result.add_pass("获取当前用户")
            else:
                self.result.add_fail("获取当前用户", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("获取当前用户", str(e))
    
    async def test_create_knowledge_base(self):
        """测试创建知识库"""
        if not self.token:
            self.result.add_skip("创建知识库", "未登录")
            return
        
        kb_data = {
            "name": f"测试知识库_{int(datetime.now().timestamp())}",
            "description": "自动化测试创建的知识库",
            "chunk_size": 500,
            "chunk_overlap": 50,
        }
        try:
            resp = await self.client.post(
                "/api/knowledge-bases",
                json=kb_data,
                headers=self.get_headers()
            )
            if resp.status_code == 201:
                data = resp.json()
                self.kb_id = data.get("id")
                self.result.add_pass("创建知识库")
            else:
                self.result.add_fail("创建知识库", f"状态码: {resp.status_code}, {resp.text}")
        except Exception as e:
            self.result.add_fail("创建知识库", str(e))
    
    async def test_list_knowledge_bases(self):
        """测试列出知识库"""
        if not self.token:
            self.result.add_skip("列出知识库", "未登录")
            return
        
        try:
            resp = await self.client.get(
                "/api/knowledge-bases",
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    self.result.add_pass("列出知识库")
                else:
                    self.result.add_fail("列出知识库", "返回格式错误")
            else:
                self.result.add_fail("列出知识库", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("列出知识库", str(e))
    
    async def test_get_knowledge_base(self):
        """测试获取知识库详情"""
        if not self.token or not self.kb_id:
            self.result.add_skip("获取知识库详情", "无知识库ID")
            return
        
        try:
            resp = await self.client.get(
                f"/api/knowledge-bases/{self.kb_id}",
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                self.result.add_pass("获取知识库详情")
            else:
                self.result.add_fail("获取知识库详情", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("获取知识库详情", str(e))
    
    async def test_get_kb_stats(self):
        """测试获取知识库统计"""
        if not self.token or not self.kb_id:
            self.result.add_skip("获取知识库统计", "无知识库ID")
            return
        
        try:
            resp = await self.client.get(
                f"/api/knowledge-bases/{self.kb_id}/stats",
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                self.result.add_pass("获取知识库统计")
            else:
                self.result.add_fail("获取知识库统计", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("获取知识库统计", str(e))
    
    async def test_create_folder(self):
        """测试创建文件夹"""
        if not self.token or not self.kb_id:
            self.result.add_skip("创建文件夹", "无知识库ID")
            return
        
        folder_data = {
            "name": f"测试文件夹_{int(datetime.now().timestamp())}",
        }
        try:
            resp = await self.client.post(
                f"/api/knowledge-bases/{self.kb_id}/folders",
                json=folder_data,
                headers=self.get_headers()
            )
            if resp.status_code == 201:
                data = resp.json()
                self.folder_id = data.get("id")
                self.result.add_pass("创建文件夹")
            else:
                self.result.add_fail("创建文件夹", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("创建文件夹", str(e))
    
    async def test_list_folders(self):
        """测试列出文件夹"""
        if not self.token or not self.kb_id:
            self.result.add_skip("列出文件夹", "无知识库ID")
            return
        
        try:
            resp = await self.client.get(
                f"/api/knowledge-bases/{self.kb_id}/folders",
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                self.result.add_pass("列出文件夹")
            else:
                self.result.add_fail("列出文件夹", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("列出文件夹", str(e))
    
    async def test_list_documents(self):
        """测试列出文档"""
        if not self.token:
            self.result.add_skip("列出文档", "未登录")
            return
        
        try:
            params = {"kb_id": self.kb_id} if self.kb_id else {}
            resp = await self.client.get(
                "/api/documents",
                params=params,
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                self.result.add_pass("列出文档")
            else:
                self.result.add_fail("列出文档", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("列出文档", str(e))
    
    async def test_search(self):
        """测试搜索功能"""
        if not self.token:
            self.result.add_skip("搜索功能", "未登录")
            return
        
        search_data = {
            "query": "测试查询",
            "top_k": 5,
            "use_rerank": False,
        }
        if self.kb_id:
            search_data["kb_ids"] = [self.kb_id]
        
        try:
            resp = await self.client.post(
                "/api/search",
                json=search_data,
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                data = resp.json()
                if "results" in data and "total" in data:
                    self.result.add_pass("搜索功能")
                else:
                    self.result.add_fail("搜索功能", "返回格式错误")
            else:
                self.result.add_fail("搜索功能", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("搜索功能", str(e))
    
    async def test_search_single_kb(self):
        """测试单知识库搜索"""
        if not self.token or not self.kb_id:
            self.result.add_skip("单知识库搜索", "无知识库ID")
            return
        
        search_data = {
            "query": "测试查询",
            "top_k": 5,
        }
        try:
            resp = await self.client.post(
                f"/api/search/kb/{self.kb_id}",
                json=search_data,
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                self.result.add_pass("单知识库搜索")
            else:
                self.result.add_fail("单知识库搜索", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("单知识库搜索", str(e))
    
    async def test_get_permissions(self):
        """测试获取权限列表"""
        if not self.token or not self.kb_id:
            self.result.add_skip("获取权限列表", "无知识库ID")
            return
        
        try:
            resp = await self.client.get(
                f"/api/knowledge-bases/{self.kb_id}/permissions",
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                self.result.add_pass("获取权限列表")
            else:
                self.result.add_fail("获取权限列表", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("获取权限列表", str(e))
    
    async def test_list_user_groups(self):
        """测试列出用户组"""
        if not self.token:
            self.result.add_skip("列出用户组", "未登录")
            return
        
        try:
            resp = await self.client.get(
                "/api/user-groups",
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                self.result.add_pass("列出用户组")
            else:
                self.result.add_fail("列出用户组", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("列出用户组", str(e))
    
    async def test_update_knowledge_base(self):
        """测试更新知识库"""
        if not self.token or not self.kb_id:
            self.result.add_skip("更新知识库", "无知识库ID")
            return
        
        update_data = {
            "description": f"更新于 {datetime.now().isoformat()}",
        }
        try:
            resp = await self.client.put(
                f"/api/knowledge-bases/{self.kb_id}",
                json=update_data,
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                self.result.add_pass("更新知识库")
            else:
                self.result.add_fail("更新知识库", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("更新知识库", str(e))
    
    async def test_delete_folder(self):
        """测试删除文件夹"""
        if not self.token or not self.kb_id or not self.folder_id:
            self.result.add_skip("删除文件夹", "无文件夹ID")
            return
        
        try:
            resp = await self.client.delete(
                f"/api/knowledge-bases/{self.kb_id}/folders/{self.folder_id}",
                headers=self.get_headers()
            )
            if resp.status_code in [200, 204]:
                self.result.add_pass("删除文件夹")
            else:
                self.result.add_fail("删除文件夹", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("删除文件夹", str(e))
    
    async def test_delete_knowledge_base(self):
        """测试删除知识库"""
        if not self.token or not self.kb_id:
            self.result.add_skip("删除知识库", "无知识库ID")
            return
        
        try:
            resp = await self.client.delete(
                f"/api/knowledge-bases/{self.kb_id}",
                headers=self.get_headers()
            )
            if resp.status_code in [200, 204]:
                self.result.add_pass("删除知识库")
            else:
                self.result.add_fail("删除知识库", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("删除知识库", str(e))
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("RAG 知识库 API 功能测试")
        print("=" * 60)
        print(f"服务地址: {BASE_URL}")
        print("=" * 60)
        
        print("\n[1] 健康检查测试")
        await self.test_health()
        
        print("\n[2] 认证功能测试")
        await self.test_register()
        await self.test_login()
        await self.test_get_current_user()
        
        print("\n[3] 知识库管理测试")
        await self.test_list_knowledge_bases()
        await self.test_create_knowledge_base()
        await self.test_get_knowledge_base()
        await self.test_get_kb_stats()
        await self.test_update_knowledge_base()
        
        print("\n[4] 文件夹管理测试")
        await self.test_create_folder()
        await self.test_list_folders()
        
        print("\n[5] 文档管理测试")
        await self.test_list_documents()
        
        print("\n[6] 搜索功能测试")
        await self.test_search()
        await self.test_search_single_kb()
        
        print("\n[7] 权限管理测试")
        await self.test_get_permissions()
        
        print("\n[8] 用户组管理测试")
        await self.test_list_user_groups()
        
        print("\n[9] 清理测试数据")
        await self.test_delete_folder()
        await self.test_delete_knowledge_base()
        
        self.result.summary()


async def main():
    tester = APITester()
    try:
        await tester.run_all_tests()
    finally:
        await tester.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
    
    print(f"\n使用服务地址: {BASE_URL}\n")
    asyncio.run(main())
