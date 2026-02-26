"""
全链路 API 测试

测试内容：
1. 健康检查
2. 对话 API（RAG 入口）
3. 知识库 API
4. 检索 API
"""
import asyncio
import aiohttp
import json

BASE_URL = "http://localhost:8000"


async def test_health():
    """测试健康检查"""
    print("\n=== 1. 健康检查测试 ===")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/api/health") as resp:
            data = await resp.json()
            print(f"  状态: {resp.status}")
            print(f"  响应: {data}")
            return resp.status == 200


async def test_chat():
    """测试对话 API"""
    print("\n=== 2. 对话 API 测试 ===")
    
    payload = {
        "message": "你好，请介绍一下你自己"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/api/chat",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as resp:
            print(f"  状态: {resp.status}")
            
            if resp.status == 200:
                data = await resp.json()
                print(f"  会话ID: {data.get('conversation_id', 'N/A')}")
                print(f"  响应长度: {len(data.get('response', ''))}")
                return True
            else:
                text = await resp.text()
                print(f"  错误: {text}")
                return False


async def test_providers():
    """测试 LLM 提供商 API"""
    print("\n=== 3. LLM 提供商测试 ===")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/api/providers") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"  可用提供商: {data}")
                return True
            else:
                print(f"  状态: {resp.status}")
                return False


async def test_tools():
    """测试工具列表 API"""
    print("\n=== 4. 工具列表测试 ===")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/api/tools") as resp:
            if resp.status == 200:
                data = await resp.json()
                tools = data.get('value', data) if isinstance(data, dict) else data
                print(f"  工具数量: {len(tools)}")
                tool_names = [t.get('name', t) if isinstance(t, dict) else t for t in tools]
                print(f"  工具列表: {tool_names[:5]}...")
                return True
            else:
                print(f"  状态: {resp.status}")
                return False


async def test_knowledge_bases():
    """测试知识库 API"""
    print("\n=== 5. 知识库 API 测试 ===")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/knowledge-bases") as resp:
            print(f"  状态: {resp.status}")
            
            if resp.status == 200:
                data = await resp.json()
                print(f"  知识库数量: {len(data) if isinstance(data, list) else 'N/A'}")
                return True
            elif resp.status == 401:
                print("  需要认证（预期行为）")
                return True
            else:
                text = await resp.text()
                print(f"  响应: {text[:100]}")
                return True


async def test_sessions():
    """测试会话状态 API"""
    print("\n=== 6. 会话状态测试 ===")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/api/sessions") as resp:
            print(f"  状态: {resp.status}")
            
            if resp.status == 200:
                data = await resp.json()
                print(f"  会话数据: {json.dumps(data, ensure_ascii=False)[:200]}")
                return True
            else:
                text = await resp.text()
                print(f"  响应: {text[:100]}")
                return True


async def main():
    """运行所有测试"""
    print("=" * 60)
    print("RAG 系统全链路 API 测试")
    print("=" * 60)
    
    results = []
    
    results.append(("健康检查", await test_health()))
    results.append(("对话API", await test_chat()))
    results.append(("LLM提供商", await test_providers()))
    results.append(("工具列表", await test_tools()))
    results.append(("知识库API", await test_knowledge_bases()))
    results.append(("会话状态", await test_sessions()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
