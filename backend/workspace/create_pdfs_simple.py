#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建PDF文档的简单版本
使用reportlab库生成PDF
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from datetime import datetime

def register_chinese_font():
    """注册中文字体"""
    try:
        # 尝试使用系统字体
        font_paths = [
            "C:/Windows/Fonts/simhei.ttf",  # Windows 黑体
            "C:/Windows/Fonts/simsun.ttc",  # Windows 宋体
            "/System/Library/Fonts/PingFang.ttc",  # macOS 苹方
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # Linux 文泉驿
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                    return 'ChineseFont'
                except:
                    continue
        
        # 如果找不到中文字体，使用默认字体
        print("警告: 未找到中文字体，使用默认字体可能无法显示中文")
        return 'Helvetica'
        
    except Exception as e:
        print(f"字体注册失败: {e}")
        return 'Helvetica'

def create_pdf(filename, title, content):
    """创建PDF文件"""
    try:
        # 创建文档
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
        
        heading1_style = ParagraphStyle(
            'CustomHeading1',
            parent=styles['Heading2'],
            fontName=chinese_font,
            fontSize=18,
            spaceBefore=20,
            spaceAfter=10
        )
        
        heading2_style = ParagraphStyle(
            'CustomHeading2',
            parent=styles['Heading3'],
            fontName=chinese_font,
            fontSize=14,
            spaceBefore=15,
            spaceAfter=8
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=chinese_font,
            fontSize=12,
            alignment=TA_JUSTIFY,
            spaceAfter=6
        )
        
        # 构建文档内容
        story = []
        
        # 添加标题
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))
        
        # 添加日期
        date_str = datetime.now().strftime("%Y年%m月%d日")
        story.append(Paragraph(f"创建日期: {date_str}", normal_style))
        story.append(Spacer(1, 30))
        
        # 添加内容
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('# '):
                # 一级标题
                story.append(Paragraph(line[2:], title_style))
                story.append(Spacer(1, 15))
            elif line.startswith('## '):
                # 二级标题
                story.append(Paragraph(line[3:], heading1_style))
                story.append(Spacer(1, 10))
            elif line.startswith('### '):
                # 三级标题
                story.append(Paragraph(line[4:], heading2_style))
                story.append(Spacer(1, 8))
            elif line.startswith('- ') or line.startswith('* '):
                # 列表项
                bullet_text = f"• {line[2:]}"
                story.append(Paragraph(bullet_text, normal_style))
            elif line.startswith('1. '):
                # 有序列表
                story.append(Paragraph(line, normal_style))
            else:
                # 普通段落
                story.append(Paragraph(line, normal_style))
                story.append(Spacer(1, 6))
        
        # 生成PDF
        doc.build(story)
        print(f"✓ 成功创建: {filename}")
        return True
        
    except Exception as e:
        print(f"✗ 创建失败 {filename}: {e}")
        return False

def main():
    """主函数"""
    print("PDF文档生成工具")
    print("=" * 50)
    
    # 定义文档内容
    documents = [
        {
            "filename": "代码设计规范.pdf",
            "title": "代码设计规范",
            "content": """# 代码设计规范

## 概述
本规范旨在建立统一的代码设计标准，确保代码质量、可维护性和团队协作效率。遵循规范有助于减少错误、提高开发效率。

## 基本原则
- 可读性优先：代码应易于理解和维护
- 一致性：遵循统一的命名和格式约定
- 模块化：功能模块化，降低耦合度
- 错误处理：完善的异常处理和日志记录

## 命名规范
- 类名：大驼峰命名法，如 UserController
- 函数名：小驼峰命名法，如 getUserInfo
- 变量名：小驼峰命名法，描述性名称
- 常量名：全大写，下划线分隔，如 MAX_RETRY_COUNT

## 代码结构
1. 文件头部注释：包含作者、创建时间、功能描述
2. 导入语句：按标准库、第三方库、本地模块分组
3. 类定义：按功能组织，单一职责原则
4. 函数定义：参数明确，返回值清晰
5. 注释：复杂逻辑需添加注释说明

## 质量要求
- 代码复用率不低于70%
- 单元测试覆盖率不低于80%
- 代码审查通过率100%
- 技术债务及时清理

## 版本控制
- 提交信息规范：类型(范围): 描述
- 分支管理：主分支保护，功能分支开发
- 代码合并：需通过代码审查和自动化测试

## 文档要求
- API文档自动生成
- 使用说明文档完整
- 架构设计文档清晰

本规范适用于所有开发项目，团队成员需严格遵守。定期审查和更新规范，以适应技术发展和项目需求变化。"""
        },
        {
            "filename": "总体方案设计.pdf",
            "title": "总体方案设计",
            "content": """# 总体方案设计

## 项目概述
本项目旨在构建一个高效、可扩展的系统平台，满足业务需求并支持未来发展。系统设计遵循现代化架构理念，确保高性能、高可用性和易维护性。

## 设计目标
1. 性能目标：响应时间<200ms，支持1000并发用户
2. 可用性目标：系统可用性99.9%，故障恢复时间<30分钟
3. 扩展性目标：支持水平扩展，容量可线性增长
4. 安全性目标：符合信息安全等级保护三级要求

## 架构设计
### 整体架构
采用微服务架构，分为以下层次：
- 接入层：负载均衡、API网关
- 业务层：微服务集群，按业务域划分
- 数据层：分布式数据库、缓存、消息队列
- 基础设施层：容器编排、监控告警

### 技术选型
- 开发框架：Spring Cloud Alibaba
- 数据库：MySQL集群 + Redis缓存
- 消息队列：RocketMQ
- 容器化：Docker + Kubernetes
- 监控：Prometheus + Grafana

## 核心功能模块
1. 用户管理模块：注册、登录、权限控制
2. 业务处理模块：核心业务流程实现
3. 数据管理模块：数据存储、查询、分析
4. 系统管理模块：配置管理、日志管理、监控告警

## 部署架构
### 开发环境
- 单节点部署，快速迭代
- 本地数据库，简化配置

### 测试环境
- 多节点部署，模拟生产
- 自动化测试流水线

### 生产环境
- 多可用区部署，高可用
- 自动扩缩容，弹性伸缩
- 蓝绿部署，零停机升级

## 数据设计
### 数据库设计
- 关系型数据库：核心业务数据
- 非关系型数据库：日志、缓存数据
- 数据分片策略：按用户ID哈希分片

### 数据流设计
- 实时数据流：Kafka流处理
- 批量数据处理：Spark批处理
- 数据同步：Canal增量同步

## 安全设计
1. 身份认证：OAuth2.0 + JWT
2. 权限控制：RBAC权限模型
3. 数据安全：数据加密、脱敏处理
4. 网络安全：WAF防护、DDoS防御

## 监控运维
- 应用监控：APM全链路追踪
- 基础设施监控：资源使用率监控
- 业务监控：关键指标监控告警
- 日志管理：集中式日志收集分析

## 实施计划
### 第一阶段（1-2个月）
基础框架搭建，核心功能开发

### 第二阶段（3-4个月）
功能完善，性能优化

### 第三阶段（5-6个月）
系统测试，上线部署

本方案为项目总体设计框架，具体实施需根据实际情况调整。各模块详细设计需在后续阶段完成。"""
        },
        {
            "filename": "硬件电路布设.pdf",
            "title": "硬件电路布设规范",
            "content": """# 硬件电路布设规范

## 概述
本规范规定了硬件电路布设的基本原则、工艺要求和质量控制标准，确保电路板设计的可靠性、稳定性和可制造性。

## 设计原则
1. 信号完整性：保证信号传输质量，减少干扰
2. 电源完整性：提供稳定、干净的电源供应
3. 热管理：合理散热，防止过热损坏
4. EMC/EMI：满足电磁兼容性要求

## PCB布局规范
### 整体布局
- 功能分区：按电路功能划分区域
- 信号流向：遵循信号流向布局，减少交叉
- 电源分区：模拟、数字、射频电源分离

### 元件布局
1. 关键元件优先：CPU、存储器、时钟等核心元件优先布局
2. 接口元件靠边：连接器、开关等靠板边布局
3. 发热元件分散：大功率元件分散布局，避免热集中
4. 敏感元件隔离：模拟电路、射频电路与数字电路隔离

## 布线规范
### 线宽线距
- 电源线：根据电流计算线宽，一般1-2mm
- 信号线：常规0.2-0.3mm，高速信号0.15mm
- 线间距：最小0.15mm，高压部分加大间距

### 布线优先级
1. 电源线和地线
2. 时钟线和高速信号线
3. 模拟信号线
4. 一般数字信号线

### 特殊信号处理
- 时钟信号：最短路径，包地处理，阻抗匹配
- 差分信号：等长等距，对称布线
- 射频信号：50Ω阻抗控制，微带线设计

## 电源设计
### 电源分层
- 顶层：数字电源
- 中间层：模拟电源、地平面
- 底层：射频电源、保护地

### 去耦电容布置
- 大容量电容：电源入口处，100-470uF
- 中容量电容：芯片电源引脚附近，10-100uF
- 小容量电容：芯片每个电源引脚，0.1uF

## 接地设计
### 接地方式
- 单点接地：模拟电路
- 多点接地：数字电路
- 混合接地：复杂系统

### 地平面设计
- 完整地平面：提供低阻抗回流路径
- 分割地平面：模拟地、数字地、射频地分离
- 地孔连接：多层板地平面充分连接

## 热设计
### 散热措施
- 散热孔：大功率元件下方打散热孔
- 散热片：发热元件加装散热片
- 铜箔散热：大面积铜箔辅助散热
- 风道设计：考虑空气流动路径

## 可制造性设计
### 工艺要求
- 最小线宽/线距：满足PCB厂家工艺能力
- 焊盘设计：符合元件封装要求
- 阻焊设计：避免桥接，便于焊接
- 丝印设计：清晰可读，不覆盖焊盘

### 测试点设计
- 关键信号测试点
- 电源测试点
- 地测试点
- 间距足够，便于探针接触

## 质量控制
### 设计检查
1. DRC检查：规则符合性检查
2. 电气规则检查：短路、开路检查
3. 信号完整性分析：仿真验证
4. 热分析：温度分布仿真

### 生产检验
- 首件检验：首批生产全面检验
- 过程检验：生产过程中抽样检验
- 最终检验：成品功能性能测试

## 文档要求
- 原理图完整清晰
- PCB布局图标注明确
- BOM清单准确无误
- 装配图指导生产

本规范为硬件电路布设的基本要求，具体项目可根据实际情况调整。设计人员需严格遵守，确保产品质量。"""
        }
    ]
    
    # 创建PDF文档
    success_count = 0
    for doc in documents:
        if create_pdf(doc["filename"], doc["title"], doc["content"]):
            success_count += 1
    
    print("=" * 50)
    print(f"生成完成: {success_count}/{len(documents)} 个PDF文件成功创建")
    
    if success_count > 0:
        print("生成的PDF文件:")
        for doc in documents:
            if os.path.exists(doc["filename"]):
                file_size = os.path.getsize(doc["filename"])
                print(f"  - {doc['filename']} ({file_size} 字节)")
    
    print("\n注意: 如果中文显示异常，请确保系统已安装中文字体。")

if __name__ == "__main__":
    main()