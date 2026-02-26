#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建多智能体模式设计技术报告的PDF文档
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

def register_chinese_font():
    """注册中文字体"""
    try:
        # 尝试使用系统字体
        font_paths = [
            "C:/Windows/Fonts/simhei.ttf",  # Windows 黑体
            "C:/Windows/Fonts/simsun.ttc",  # Windows 宋体
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                    return 'ChineseFont'
                except:
                    continue
        
        # 如果找不到中文字体，使用默认字体
        print("警告: 未找到中文字体，使用默认字体")
        return 'Helvetica'
        
    except Exception as e:
        print(f"字体注册失败: {e}")
        return 'Helvetica'

def create_multi_agent_pdf():
    """创建多智能体模式设计技术报告的PDF"""
    
    # 文档内容
    title = "多智能体模式设计技术报告"
    
    content = [
        ("标题", title),
        ("摘要", "多智能体系统通过多个自主智能体之间的协作与协调，能够解决单一智能体难以处理的复杂问题。本报告从架构设计、通信机制、协调策略三个核心维度，系统阐述多智能体模式的设计要点与实践方法。"),
        ("一、架构设计", "多智能体架构通常采用分层或混合模式。集中式架构便于全局协调但存在单点故障风险；分布式架构具有更好的容错性但协调复杂度高。实践中推荐采用联邦式架构，结合集中协调与分布式执行的优点，确保系统既具备全局视野又保持局部自主性。"),
        ("二、通信机制", "有效的通信是多智能体协作的基础。消息传递机制应支持同步与异步通信，采用标准化的消息格式（如JSON、XML）。推荐使用发布-订阅模式实现松耦合通信，结合消息队列确保可靠传输。通信协议需考虑安全性、延迟和带宽限制，在复杂环境中可采用自适应通信策略。"),
        ("三、协调策略", "协调策略决定智能体如何协同工作。合同网协议适用于任务分配场景，拍卖机制适合资源竞争环境，基于规则的协调简单高效但灵活性有限。现代多智能体系统常采用混合协调策略，结合集中规划与分布式执行，引入强化学习使智能体能够自适应调整协作行为。"),
        ("结论", "多智能体模式设计需要综合考虑架构、通信和协调三个关键要素。成功的多智能体系统应在保持个体自主性的基础上实现高效协作，通过合理的架构设计平衡集中控制与分布式执行，采用灵活的通信机制支持复杂交互，运用智能协调策略优化整体性能。未来发展趋势将更加注重自适应学习、安全可信和跨平台集成能力。")
    ]
    
    try:
        # 创建PDF文档
        filename = "多智能体模式设计技术报告.pdf"
        doc = SimpleDocTemplate(
            filename,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # 获取样式
        styles = getSampleStyleSheet()
        
        # 注册中文字体
        chinese_font = register_chinese_font()
        
        # 创建自定义样式
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=chinese_font,
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=30
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName=chinese_font,
            fontSize=16,
            spaceBefore=20,
            spaceAfter=10
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=chinese_font,
            fontSize=12,
            alignment=TA_JUSTIFY,
            spaceAfter=12
        )
        
        # 构建文档内容
        story = []
        
        # 添加标题
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))
        
        # 添加内容
        for section_title, section_content in content[1:]:  # 跳过第一个标题
            if section_title == "摘要":
                story.append(Paragraph("摘要", heading_style))
            else:
                story.append(Paragraph(section_title, heading_style))
            
            story.append(Paragraph(section_content, normal_style))
            story.append(Spacer(1, 10))
        
        # 生成PDF
        doc.build(story)
        
        # 统计字数
        total_text = "".join([content for _, content in content])
        chinese_count = sum(1 for char in total_text if '\u4e00' <= char <= '\u9fff')
        
        print(f"PDF文档已创建: {filename}")
        print(f"文档大小: {os.path.getsize(filename)} 字节")
        print(f"中文字数: {chinese_count}字")
        
        return filename
        
    except Exception as e:
        print(f"创建PDF失败: {e}")
        return None

if __name__ == "__main__":
    create_multi_agent_pdf()