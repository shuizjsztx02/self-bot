#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建三个PDF文件的脚本
主题：
1. 如何追求女孩
2. 如何学习大模型
3. 如何低代价使用claude大模型接口
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch

def create_pdf(filename, title, content):
    """创建PDF文件"""
    try:
        # 创建文档
        doc = SimpleDocTemplate(filename, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # 添加标题
        title_para = Paragraph(title, styles['Title'])
        story.append(title_para)
        story.append(Spacer(1, 0.2*inch))
        
        # 添加内容
        content_para = Paragraph(content, styles['Normal'])
        story.append(content_para)
        
        # 构建PDF
        doc.build(story)
        print(f"PDF文件创建成功: {filename}")
        return True
    except Exception as e:
        print(f"创建PDF文件失败 {filename}: {e}")
        return False

def main():
    # 创建目录
    output_dir = "backend/rag_datam"
    os.makedirs(output_dir, exist_ok=True)
    print(f"创建目录: {output_dir}")
    
    # 定义三个主题的内容
    topics = [
        {
            "filename": os.path.join(output_dir, "如何追求女孩.pdf"),
            "title": "如何追求女孩：实用指南",
            "content": """
            <b>一、建立良好的第一印象</b><br/>
            1. 保持自信但不自负的态度<br/>
            2. 注意个人形象和卫生<br/>
            3. 展现真诚的微笑和眼神交流<br/>
            4. 找到共同话题，展现兴趣<br/><br/>
            
            <b>二、有效沟通技巧</b><br/>
            1. 学会倾听，关注她的感受<br/>
            2. 避免过于直接或冒昧的问题<br/>
            3. 分享自己的故事和经历<br/>
            4. 保持轻松愉快的对话氛围<br/><br/>
            
            <b>三、逐步建立关系</b><br/>
            1. 从朋友做起，不要急于求成<br/>
            2. 寻找共同兴趣和活动<br/>
            3. 适时表达关心和体贴<br/>
            4. 尊重她的个人空间和时间<br/><br/>
            
            <b>四、注意事项</b><br/>
            1. 不要过分纠缠或骚扰<br/>
            2. 接受可能的拒绝，保持风度<br/>
            3. 真诚对待，不要玩弄感情<br/>
            4. 保持自我，不要完全改变自己<br/><br/>
            
            <i>追求女孩需要耐心和真诚，最重要的是相互尊重和理解。</i>
            """
        },
        {
            "filename": os.path.join(output_dir, "如何学习大模型.pdf"),
            "title": "如何学习大模型：入门指南",
            "content": """
            <b>一、基础知识准备</b><br/>
            1. 掌握Python编程语言基础<br/>
            2. 学习线性代数、概率论和微积分<br/>
            3. 了解机器学习基本概念<br/>
            4. 熟悉深度学习框架（如PyTorch、TensorFlow）<br/><br/>
            
            <b>二、大模型核心技术</b><br/>
            1. 理解Transformer架构原理<br/>
            2. 学习注意力机制和位置编码<br/>
            3. 掌握预训练和微调方法<br/>
            4. 了解模型压缩和优化技术<br/><br/>
            
            <b>三、实践学习路径</b><br/>
            1. 从经典模型开始（如BERT、GPT-2）<br/>
            2. 参与开源项目和实践代码<br/>
            3. 阅读论文和最新研究成果<br/>
            4. 参加相关竞赛和社区活动<br/><br/>
            
            <b>四、学习资源推荐</b><br/>
            1. 在线课程：Coursera、Udacity<br/>
            2. 书籍：《深度学习》、《动手学深度学习》<br/>
            3. 论文：arXiv上的最新研究成果<br/>
            4. 社区：GitHub、Hugging Face、知乎专栏<br/><br/>
            
            <i>大模型学习需要持续实践和探索，保持好奇心和耐心是关键。</i>
            """
        },
        {
            "filename": os.path.join(output_dir, "如何低代价使用claude大模型接口.pdf"),
            "title": "如何低代价使用Claude大模型接口",
            "content": """
            <b>一、成本优化策略</b><br/>
            1. 合理控制API调用频率<br/>
            2. 使用缓存机制减少重复请求<br/>
            3. 批量处理请求降低单位成本<br/>
            4. 选择适合的模型版本（如Claude Instant）<br/><br/>
            
            <b>二、技术优化方法</b><br/>
            1. 优化提示词设计，减少token消耗<br/>
            2. 使用流式响应减少等待时间<br/>
            3. 实现请求队列和优先级管理<br/>
            4. 监控和分析API使用情况<br/><br/>
            
            <b>三、免费和低成本替代方案</b><br/>
            1. 利用免费额度和新用户优惠<br/>
            2. 结合开源模型降低依赖<br/>
            3. 使用代理服务获取更优价格<br/>
            4. 参与测试计划获取免费额度<br/><br/>
            
            <b>四、最佳实践建议</b><br/>
            1. 设置预算限制和告警机制<br/>
            2. 定期评估成本效益比<br/>
            3. 优化应用架构减少API依赖<br/>
            4. 关注官方优惠活动和政策变化<br/><br/>
            
            <b>五、具体实施步骤</b><br/>
            1. 注册Anthropic账户获取API密钥<br/>
            2. 了解定价结构和计费方式<br/>
            3. 实现基本的API调用封装<br/>
            4. 添加成本监控和优化逻辑<br/>
            5. 定期评估和调整使用策略<br/><br/>
            
            <i>通过合理规划和优化，可以在保证服务质量的同时显著降低Claude API的使用成本。</i>
            """
        }
    ]
    
    # 创建PDF文件
    success_count = 0
    for topic in topics:
        if create_pdf(topic["filename"], topic["title"], topic["content"]):
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