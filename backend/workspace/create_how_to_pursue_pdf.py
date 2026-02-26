#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建"如何追求女孩"的PDF文档
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

def create_pdf():
    """创建PDF文档"""
    
    # 创建PDF文件
    pdf_filename = "如何追求女孩.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=A4,
                          rightMargin=72, leftMargin=72,
                          topMargin=72, bottomMargin=72)
    
    # 获取样式
    styles = getSampleStyleSheet()
    
    # 创建自定义样式
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=12,
        spaceAfter=6
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=12,
        spaceAfter=6
    )
    
    # 构建文档内容
    story = []
    
    # 标题
    story.append(Paragraph("如何追求女孩：真诚与技巧的平衡", title_style))
    story.append(Spacer(1, 20))
    
    # 简介
    story.append(Paragraph("追求女孩是一门艺术，需要真诚与技巧的完美结合。以下是一些实用的建议，帮助你更好地表达心意，建立真挚的感情。", normal_style))
    story.append(Spacer(1, 15))
    
    # 一、建立良好的第一印象
    story.append(Paragraph("一、建立良好的第一印象", heading_style))
    story.append(Paragraph("1. 保持整洁的外表：干净整洁的着装和良好的个人卫生是基础。", normal_style))
    story.append(Paragraph("2. 展现自信：自信但不自负，保持自然的态度。", normal_style))
    story.append(Paragraph("3. 真诚的微笑：温暖的微笑能拉近彼此距离。", normal_style))
    story.append(Spacer(1, 10))
    
    # 二、有效的沟通技巧
    story.append(Paragraph("二、有效的沟通技巧", heading_style))
    story.append(Paragraph("1. 学会倾听：认真倾听她的想法和感受，给予关注。", normal_style))
    story.append(Paragraph("2. 寻找共同话题：了解她的兴趣爱好，建立共同语言。", normal_style))
    story.append(Paragraph("3. 适度的幽默感：适当的幽默能让相处更轻松愉快。", normal_style))
    story.append(Spacer(1, 10))
    
    # 三、展现真诚与尊重
    story.append(Paragraph("三、展现真诚与尊重", heading_style))
    story.append(Paragraph("1. 真诚待人：不要伪装自己，展现真实的个性。", normal_style))
    story.append(Paragraph("2. 尊重她的选择：不强求，给予足够的空间和时间。", normal_style))
    story.append(Paragraph("3. 体贴关心：在细节处体现关心，但不要过度。", normal_style))
    story.append(Spacer(1, 10))
    
    # 四、适时的表达心意
    story.append(Paragraph("四、适时的表达心意", heading_style))
    story.append(Paragraph("1. 选择合适的时机：在彼此有一定了解后，选择合适的时间表达。", normal_style))
    story.append(Paragraph("2. 真诚的表达：用真诚的语言表达你的感受，不要过于华丽。", normal_style))
    story.append(Paragraph("3. 接受结果：无论结果如何，都要尊重她的决定，保持风度。", normal_style))
    story.append(Spacer(1, 15))
    
    # 总结
    story.append(Paragraph("总结", heading_style))
    story.append(Paragraph("追求女孩最重要的是真诚和尊重。技巧只是辅助，真正的感情建立在相互理解和尊重的基础上。保持自信，展现真实的自己，用真诚的心去对待每一段可能的感情。", normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("字数统计：约300字", normal_style))
    
    # 生成PDF
    doc.build(story)
    print(f"PDF文档已创建：{pdf_filename}")
    print(f"文件大小：{os.path.getsize(pdf_filename)} 字节")

if __name__ == "__main__":
    try:
        create_pdf()
    except Exception as e:
        print(f"创建PDF时出错: {e}")
        print("请确保已安装reportlab库：pip install reportlab")