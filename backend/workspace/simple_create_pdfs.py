#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单创建PDF文件的脚本
使用reportlab创建三个PDF文件
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def create_simple_pdf(filename, title, content_lines):
    """创建简单的PDF文件"""
    try:
        c = canvas.Canvas(filename, pagesize=letter)
        width, height = letter
        
        # 设置标题
        c.setFont("Helvetica-Bold", 16)
        c.drawString(100, height - 100, title)
        
        # 设置内容
        c.setFont("Helvetica", 12)
        y_position = height - 140
        
        for line in content_lines:
            if y_position < 100:  # 如果页面底部空间不足，创建新页面
                c.showPage()
                c.setFont("Helvetica", 12)
                y_position = height - 100
            
            c.drawString(100, y_position, line)
            y_position -= 20
        
        c.save()
        print(f"PDF创建成功: {filename}")
        return True
    except Exception as e:
        print(f"创建PDF失败 {filename}: {e}")
        return False

def main():
    # 创建目录
    output_dir = "backend/rag_datam"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"创建目录: {output_dir}")
    
    # 主题1: 如何追求女孩
    girl_content = [
        "如何追求女孩：实用指南",
        "",
        "一、建立良好的第一印象",
        "1. 保持自信但不自负的态度",
        "2. 注意个人形象和卫生",
        "3. 展现真诚的微笑和眼神交流",
        "4. 找到共同话题，展现兴趣",
        "",
        "二、有效沟通技巧",
        "1. 学会倾听，关注她的感受",
        "2. 避免过于直接或冒昧的问题",
        "3. 分享自己的故事和经历",
        "4. 保持轻松愉快的对话氛围",
        "",
        "三、逐步建立关系",
        "1. 从朋友做起，不要急于求成",
        "2. 寻找共同兴趣和活动",
        "3. 适时表达关心和体贴",
        "4. 尊重她的个人空间和时间",
        "",
        "四、注意事项",
        "1. 不要过分纠缠或骚扰",
        "2. 接受可能的拒绝，保持风度",
        "3. 真诚对待，不要玩弄感情",
        "4. 保持自我，不要完全改变自己",
        "",
        "追求女孩需要耐心和真诚，最重要的是相互尊重和理解。"
    ]
    
    # 主题2: 如何学习大模型
    llm_content = [
        "如何学习大模型：入门指南",
        "",
        "一、基础知识准备",
        "1. 掌握Python编程语言基础",
        "2. 学习线性代数、概率论和微积分",
        "3. 了解机器学习基本概念",
        "4. 熟悉深度学习框架（如PyTorch、TensorFlow）",
        "",
        "二、大模型核心技术",
        "1. 理解Transformer架构原理",
        "2. 学习注意力机制和位置编码",
        "3. 掌握预训练和微调方法",
        "4. 了解模型压缩和优化技术",
        "",
        "三、实践学习路径",
        "1. 从经典模型开始（如BERT、GPT-2）",
        "2. 参与开源项目和实践代码",
        "3. 阅读论文和最新研究成果",
        "4. 参加相关竞赛和社区活动",
        "",
        "四、学习资源推荐",
        "1. 在线课程：Coursera、Udacity",
        "2. 书籍：《深度学习》、《动手学深度学习》",
        "3. 论文：arXiv上的最新研究成果",
        "4. 社区：GitHub、Hugging Face、知乎专栏",
        "",
        "大模型学习需要持续实践和探索，保持好奇心和耐心是关键。"
    ]
    
    # 主题3: 如何低代价使用claude大模型接口
    claude_content = [
        "如何低代价使用Claude大模型接口",
        "",
        "一、成本优化策略",
        "1. 合理控制API调用频率",
        "2. 使用缓存机制减少重复请求",
        "3. 批量处理请求降低单位成本",
        "4. 选择适合的模型版本（如Claude Instant）",
        "",
        "二、技术优化方法",
        "1. 优化提示词设计，减少token消耗",
        "2. 使用流式响应减少等待时间",
        "3. 实现请求队列和优先级管理",
        "4. 监控和分析API使用情况",
        "",
        "三、免费和低成本替代方案",
        "1. 利用免费额度和新用户优惠",
        "2. 结合开源模型降低依赖",
        "3. 使用代理服务获取更优价格",
        "4. 参与测试计划获取免费额度",
        "",
        "四、最佳实践建议",
        "1. 设置预算限制和告警机制",
        "2. 定期评估成本效益比",
        "3. 优化应用架构减少API依赖",
        "4. 关注官方优惠活动和政策变化",
        "",
        "五、具体实施步骤",
        "1. 注册Anthropic账户获取API密钥",
        "2. 了解定价结构和计费方式",
        "3. 实现基本的API调用封装",
        "4. 添加成本监控和优化逻辑",
        "5. 定期评估和调整使用策略",
        "",
        "通过合理规划和优化，可以在保证服务质量的同时显著降低Claude API的使用成本。"
    ]
    
    # 创建PDF文件
    topics = [
        ("如何追求女孩.pdf", "如何追求女孩：实用指南", girl_content),
        ("如何学习大模型.pdf", "如何学习大模型：入门指南", llm_content),
        ("如何低代价使用claude大模型接口.pdf", "如何低代价使用Claude大模型接口", claude_content)
    ]
    
    success_count = 0
    for filename, title, content in topics:
        filepath = os.path.join(output_dir, filename)
        if create_simple_pdf(filepath, title, content):
            success_count += 1
    
    print(f"\n创建完成：成功创建 {success_count}/{len(topics)} 个PDF文件")
    print(f"文件保存在：{output_dir}")
    
    # 列出创建的文件
    if os.path.exists(output_dir):
        files = os.listdir(output_dir)
        print(f"\n目录内容：")
        for file in files:
            filepath = os.path.join(output_dir, file)
            if os.path.isfile(filepath):
                size = os.path.getsize(filepath)
                print(f"  - {file} ({size} bytes)")

if __name__ == "__main__":
    main()