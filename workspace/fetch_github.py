#!/usr/bin/env python3
"""
GitHub仓库内容抓取脚本
用于抓取 https://github.com/shuizjsztx02/self-bot/tree/main 的基本内容
"""

import requests
from bs4 import BeautifulSoup
import json

def fetch_github_repo(url):
    """抓取GitHub仓库内容"""
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    try:
        print(f"正在抓取: {url}")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 提取基本信息
        result = {
            'url': url,
            'status': 'success',
            'title': soup.title.string.strip() if soup.title else 'No title',
            'files': []
        }
        
        # 尝试提取仓库描述
        description_elem = soup.find('p', class_='f4 my-3')
        if description_elem:
            result['description'] = description_elem.text.strip()
        
        # 提取文件列表 - GitHub使用特定的结构
        file_items = soup.find_all('div', {'role': 'row', 'class': 'Box-row'})
        
        for item in file_items:
            try:
                # 文件名
                name_elem = item.find('div', {'role': 'rowheader'})
                if name_elem:
                    name = name_elem.text.strip()
                    
                    # 文件类型/大小
                    type_elem = item.find('div', class_='col-5')
                    file_type = type_elem.text.strip() if type_elem else ''
                    
                    # 提交信息
                    commit_elem = item.find('a', class_='Link--primary')
                    commit_msg = commit_elem.text.strip() if commit_elem else ''
                    
                    # 时间
                    time_elem = item.find('relative-time')
                    time_str = time_elem['datetime'] if time_elem else ''
                    
                    result['files'].append({
                        'name': name,
                        'type': file_type,
                        'commit': commit_msg,
                        'last_modified': time_str
                    })
            except:
                continue
        
        # 提取README预览
        readme_elem = soup.find('div', {'class': 'Box-body'})
        if readme_elem:
            readme_text = readme_elem.get_text(separator='\n', strip=True)
            result['readme_preview'] = readme_text[:300] + '...' if len(readme_text) > 300 else readme_text
        
        return result
        
    except Exception as e:
        return {
            'url': url,
            'status': 'error',
            'error': str(e)
        }

def main():
    url = "https://github.com/shuizjsztx02/self-bot/tree/main"
    
    print("开始抓取GitHub仓库内容...")
    print(f"目标URL: {url}")
    print("-" * 60)
    
    result = fetch_github_repo(url)
    
    if result['status'] == 'success':
        print(f"\n✅ 抓取成功!")
        print(f"标题: {result.get('title', 'N/A')}")
        print(f"描述: {result.get('description', '无描述')}")
        print(f"找到文件数量: {len(result.get('files', []))}")
        
        if result.get('files'):
            print("\n📁 文件列表:")
            print("-" * 80)
            for i, file in enumerate(result['files'][:15], 1):  # 显示前15个
                print(f"{i:2d}. {file['name']:40s} | {file['type']:20s}")
            
            if len(result['files']) > 15:
                print(f"... 还有 {len(result['files']) - 15} 个文件")
        
        if result.get('readme_preview'):
            print("\n📝 README预览:")
            print("-" * 80)
            print(result['readme_preview'])
        
        # 保存结果
        with open('github_repo_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 详细结果已保存到: github_repo_result.json")
        
    else:
        print(f"\n❌ 抓取失败!")
        print(f"错误: {result.get('error', '未知错误')}")

if __name__ == "__main__":
    main()