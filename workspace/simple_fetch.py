import requests
import re

# GitHub仓库URL
url = "https://github.com/shuizjsztx02/self-bot/tree/main"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

print(f"正在访问: {url}")

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"状态码: {response.status_code}")
    
    if response.status_code == 200:
        content = response.text
        
        # 提取标题
        title_match = re.search(r'<title>(.*?)</title>', content)
        if title_match:
            print(f"\n📋 仓库标题: {title_match.group(1)}")
        
        # 提取描述
        desc_match = re.search(r'<p class="f4 my-3">(.*?)</p>', content)
        if desc_match:
            print(f"📝 描述: {desc_match.group(1).strip()}")
        
        # 提取文件列表 - 简化版本
        # GitHub的文件在特定的div中
        file_pattern = r'<div role="rowheader".*?>(.*?)</div>'
        files = re.findall(file_pattern, content, re.DOTALL)
        
        if files:
            print(f"\n📁 找到 {len(files)} 个文件/目录:")
            print("-" * 50)
            for i, file in enumerate(files[:20], 1):  # 只显示前20个
                # 清理HTML标签
                clean_file = re.sub(r'<.*?>', '', file).strip()
                if clean_file and clean_file not in ['.', '..']:
                    print(f"{i:2d}. {clean_file}")
            
            if len(files) > 20:
                print(f"... 还有 {len(files) - 20} 个文件")
        
        # 提取README内容
        readme_pattern = r'<div class="Box-body".*?>(.*?)</div>'
        readme_match = re.search(readme_pattern, content, re.DOTALL)
        
        if readme_match:
            readme_text = readme_match.group(1)
            # 清理HTML标签，保留文本
            clean_readme = re.sub(r'<.*?>', ' ', readme_text)
            clean_readme = re.sub(r'\s+', ' ', clean_readme).strip()
            
            print(f"\n📄 README预览 (前200字符):")
            print("-" * 50)
            print(clean_readme[:200] + "..." if len(clean_readme) > 200 else clean_readme)
        
        # 提取统计信息
        stars_match = re.search(r'(\d+)\s+stars', content, re.IGNORECASE)
        forks_match = re.search(r'(\d+)\s+forks', content, re.IGNORECASE)
        
        if stars_match:
            print(f"\n⭐ 星标数: {stars_match.group(1)}")
        if forks_match:
            print(f"🔀 Fork数: {forks_match.group(1)}")
        
        # 保存原始HTML用于进一步分析
        with open('github_page.html', 'w', encoding='utf-8') as f:
            f.write(content[:5000])  # 保存前5000字符
        
        print(f"\n💾 页面片段已保存到: github_page.html")
        
    else:
        print(f"请求失败，状态码: {response.status_code}")
        
except Exception as e:
    print(f"错误: {e}")