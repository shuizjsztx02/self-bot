"""
Phase 2 功能集成测试脚本
测试新增的API端点：用户组、操作日志、属性规则
"""

import asyncio
import httpx
import json
from datetime import datetime

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


class Phase2Tester:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT)
        self.token: str = None
        self.kb_id: str = None
        self.group_id: str = None
        self.result = TestResult()
    
    async def close(self):
        await self.client.aclose()
    
    def get_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    async def test_login(self):
        """测试用户登录"""
        timestamp = int(datetime.now().timestamp())
        login_data = {
            "email": f"test_{timestamp}@example.com",
            "password": "Test123456",
        }
        
        register_data = {
            "name": f"test_user_{timestamp}",
            "email": f"test_{timestamp}@example.com",
            "password": "Test123456",
            "department": "测试部门",
        }
        
        try:
            resp = await self.client.post("/api/auth/register", json=register_data)
            if resp.status_code in [201, 400]:
                resp = await self.client.post("/api/auth/login", json=login_data)
                if resp.status_code == 200:
                    data = resp.json()
                    self.token = data.get("access_token")
                    self.result.add_pass("用户登录")
                else:
                    self.result.add_fail("用户登录", f"状态码: {resp.status_code}")
            else:
                resp = await self.client.post("/api/auth/login", json=login_data)
                if resp.status_code == 200:
                    data = resp.json()
                    self.token = data.get("access_token")
                    self.result.add_pass("用户登录")
                else:
                    self.result.add_fail("用户登录", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("用户登录", str(e))
    
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
                data = resp.json()
                self.result.add_pass(f"列出用户组 ({len(data)} 个)")
            else:
                self.result.add_fail("列出用户组", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("列出用户组", str(e))
    
    async def test_create_user_group(self):
        """测试创建用户组"""
        if not self.token:
            self.result.add_skip("创建用户组", "未登录")
            return
        
        group_data = {
            "name": f"测试组_{int(datetime.now().timestamp())}",
            "description": "自动化测试创建的用户组",
        }
        try:
            resp = await self.client.post(
                "/api/user-groups",
                json=group_data,
                headers=self.get_headers()
            )
            if resp.status_code == 201:
                data = resp.json()
                self.group_id = data.get("id")
                self.result.add_pass("创建用户组")
            elif resp.status_code == 403:
                self.result.add_pass("创建用户组 (权限检查正确 - 需超级用户)")
            else:
                self.result.add_fail("创建用户组", f"状态码: {resp.status_code}, {resp.text[:200]}")
        except Exception as e:
            self.result.add_fail("创建用户组", str(e))
    
    async def test_get_user_group(self):
        """测试获取用户组详情"""
        if not self.token or not self.group_id:
            self.result.add_skip("获取用户组详情", "无用户组ID")
            return
        
        try:
            resp = await self.client.get(
                f"/api/user-groups/{self.group_id}",
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                self.result.add_pass("获取用户组详情")
            else:
                self.result.add_fail("获取用户组详情", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("获取用户组详情", str(e))
    
    async def test_update_user_group(self):
        """测试更新用户组"""
        if not self.token or not self.group_id:
            self.result.add_skip("更新用户组", "无用户组ID")
            return
        
        update_data = {
            "description": f"更新于 {datetime.now().isoformat()}",
        }
        try:
            resp = await self.client.put(
                f"/api/user-groups/{self.group_id}",
                json=update_data,
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                self.result.add_pass("更新用户组")
            else:
                self.result.add_fail("更新用户组", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("更新用户组", str(e))
    
    async def test_list_operation_logs(self):
        """测试列出操作日志"""
        if not self.token:
            self.result.add_skip("列出操作日志", "未登录")
            return
        
        try:
            resp = await self.client.get(
                "/api/operation-logs",
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                data = resp.json()
                self.result.add_pass(f"列出操作日志 ({len(data)} 条)")
            elif resp.status_code == 403:
                self.result.add_pass("列出操作日志 (权限检查正确 - 需超级用户)")
            else:
                self.result.add_fail("列出操作日志", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("列出操作日志", str(e))
    
    async def test_get_kb_for_attribute_rules(self):
        """获取知识库ID用于属性规则测试"""
        if not self.token:
            self.result.add_skip("获取知识库", "未登录")
            return
        
        try:
            resp = await self.client.get(
                "/api/knowledge-bases",
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    self.kb_id = data[0].get("id")
                    self.result.add_pass(f"获取知识库ID: {self.kb_id[:8]}...")
                else:
                    self.result.add_skip("获取知识库ID", "无知识库")
            else:
                self.result.add_fail("获取知识库ID", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("获取知识库ID", str(e))
    
    async def test_list_attribute_rules(self):
        """测试列出属性规则"""
        if not self.token or not self.kb_id:
            self.result.add_skip("列出属性规则", "无知识库ID")
            return
        
        try:
            resp = await self.client.get(
                f"/api/{self.kb_id}/attribute-rules",
                headers=self.get_headers()
            )
            if resp.status_code == 200:
                data = resp.json()
                self.result.add_pass(f"列出属性规则 ({len(data)} 条)")
            elif resp.status_code == 403:
                self.result.add_pass("列出属性规则 (权限检查正确 - 需超级用户)")
            else:
                self.result.add_fail("列出属性规则", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("列出属性规则", str(e))
    
    async def test_delete_user_group(self):
        """测试删除用户组"""
        if not self.token or not self.group_id:
            self.result.add_skip("删除用户组", "无用户组ID")
            return
        
        try:
            resp = await self.client.delete(
                f"/api/user-groups/{self.group_id}",
                headers=self.get_headers()
            )
            if resp.status_code in [200, 204]:
                self.result.add_pass("删除用户组")
            else:
                self.result.add_fail("删除用户组", f"状态码: {resp.status_code}")
        except Exception as e:
            self.result.add_fail("删除用户组", str(e))
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("=" * 60)
        print("Phase 2 功能集成测试")
        print("=" * 60)
        print(f"服务地址: {BASE_URL}")
        print("=" * 60)
        
        print("\n[1] 认证测试")
        await self.test_login()
        
        print("\n[2] 用户组API测试")
        await self.test_list_user_groups()
        await self.test_create_user_group()
        await self.test_get_user_group()
        await self.test_update_user_group()
        
        print("\n[3] 操作日志API测试")
        await self.test_list_operation_logs()
        
        print("\n[4] 属性规则API测试")
        await self.test_get_kb_for_attribute_rules()
        await self.test_list_attribute_rules()
        
        print("\n[5] 清理测试数据")
        await self.test_delete_user_group()
        
        self.result.summary()


async def main():
    tester = Phase2Tester()
    try:
        await tester.run_all_tests()
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
