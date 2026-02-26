const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, 
        HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType } = require('docx');

// 创建文档
const doc = new Document({
  styles: {
    default: { 
      document: { 
        run: { 
          font: "Arial", 
          size: 24  // 12pt
        } 
      } 
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 32, bold: true, font: "Arial" },
        paragraph: { 
          spacing: { before: 240, after: 240 },
          outlineLevel: 0
        }
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 28, bold: true, font: "Arial" },
        paragraph: { 
          spacing: { before: 180, after: 180 },
          outlineLevel: 1
        }
      }
    ]
  },
  sections: [{
    properties: {
      page: {
        size: {
          width: 12240,   // US Letter width (8.5 inches)
          height: 15840   // US Letter height (11 inches)
        },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } // 1 inch margins
      }
    },
    children: [
      // 标题
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        alignment: AlignmentType.CENTER,
        children: [new TextRun("测试文档")]
      }),
      
      // 空行
      new Paragraph({ children: [] }),
      
      // 简介段落
      new Paragraph({
        children: [
          new TextRun("这是一个简单的测试文档，用于演示Word文档创建功能。"),
          new TextRun({ break: 1 }),
          new TextRun("创建时间：2026年2月21日")
        ]
      }),
      
      // 空行
      new Paragraph({ children: [] }),
      
      // 第一部分
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun("第一部分：文档简介")]
      }),
      
      new Paragraph({
        children: [
          new TextRun("这是文档的第一部分，主要介绍文档的基本信息和用途。"),
          new TextRun({ break: 1 }),
          new TextRun("测试文档通常用于验证文档创建工具的功能是否正常。")
        ]
      }),
      
      // 空行
      new Paragraph({ children: [] }),
      
      // 第二部分
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun("第二部分：功能测试")]
      }),
      
      new Paragraph({
        children: [
          new TextRun("这部分测试文档的各种功能，包括："),
          new TextRun({ break: 1 }),
          new TextRun("1. 标题样式"),
          new TextRun({ break: 1 }),
          new TextRun("2. 段落文本"),
          new TextRun({ break: 1 }),
          new TextRun("3. 表格功能"),
          new TextRun({ break: 1 }),
          new TextRun("4. 格式设置")
        ]
      }),
      
      // 空行
      new Paragraph({ children: [] }),
      
      // 表格标题
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun("测试表格")]
      }),
      
      // 创建表格
      new Table({
        width: { size: 9360, type: WidthType.DXA }, // 内容宽度
        columnWidths: [3120, 3120, 3120], // 3列等宽
        rows: [
          // 表头
          new TableRow({
            children: [
              new TableCell({
                borders: {
                  top: { style: BorderStyle.SINGLE, size: 1, color: "000000" },
                  bottom: { style: BorderStyle.SINGLE, size: 1, color: "000000" },
                  left: { style: BorderStyle.SINGLE, size: 1, color: "000000" },
                  right: { style: BorderStyle.SINGLE, size: 1, color: "000000" }
                },
                shading: { fill: "F0F0F0", type: ShadingType.CLEAR },
                margins: { top: 80, bottom: 80, left: 120, right: 120 },
                width: { size: 3120, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun({ text: "列1", bold: true })] })]
              }),
              new TableCell({
                borders: {
                  top: { style: BorderStyle.SINGLE, size: 1, color: "000000" },
                  bottom: { style: BorderStyle.SINGLE, size: 1, color: "000000" },
                  left: { style: BorderStyle.SINGLE, size: 1, color: "000000" },
                  right: { style: BorderStyle.SINGLE, size: 1, color: "000000" }
                },
                shading: { fill: "F0F0F0", type: ShadingType.CLEAR },
                margins: { top: 80, bottom: 80, left: 120, right: 120 },
                width: { size: 3120, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun({ text: "列2", bold: true })] })]
              }),
              new TableCell({
                borders: {
                  top: { style: BorderStyle.SINGLE, size: 1, color: "000000" },
                  bottom: { style: BorderStyle.SINGLE, size: 1, color: "000000" },
                  left: { style: BorderStyle.SINGLE, size: 1, color: "000000" },
                  right: { style: BorderStyle.SINGLE, size: 1, color: "000000" }
                },
                shading: { fill: "F0F0F0", type: ShadingType.CLEAR },
                margins: { top: 80, bottom: 80, left: 120, right: 120 },
                width: { size: 3120, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun({ text: "列3", bold: true })] })]
              })
            ]
          }),
          
          // 数据行
          new TableRow({
            children: [
              new TableCell({
                borders: {
                  top: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  bottom: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  left: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  right: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" }
                },
                margins: { top: 80, bottom: 80, left: 120, right: 120 },
                width: { size: 3120, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("测试数据1")] })]
              }),
              new TableCell({
                borders: {
                  top: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  bottom: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  left: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  right: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" }
                },
                margins: { top: 80, bottom: 80, left: 120, right: 120 },
                width: { size: 3120, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("测试数据2")] })]
              }),
              new TableCell({
                borders: {
                  top: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  bottom: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  left: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  right: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" }
                },
                margins: { top: 80, bottom: 80, left: 120, right: 120 },
                width: { size: 3120, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("测试数据3")] })]
              })
            ]
          }),
          
          // 更多数据行
          new TableRow({
            children: [
              new TableCell({
                borders: {
                  top: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  bottom: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  left: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  right: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" }
                },
                margins: { top: 80, bottom: 80, left: 120, right: 120 },
                width: { size: 3120, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("示例A")] })]
              }),
              new TableCell({
                borders: {
                  top: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  bottom: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  left: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  right: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" }
                },
                margins: { top: 80, bottom: 80, left: 120, right: 120 },
                width: { size: 3120, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("示例B")] })]
              }),
              new TableCell({
                borders: {
                  top: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  bottom: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  left: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" },
                  right: { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" }
                },
                margins: { top: 80, bottom: 80, left: 120, right: 120 },
                width: { size: 3120, type: WidthType.DXA },
                children: [new Paragraph({ children: [new TextRun("示例C")] })]
              })
            ]
          })
        ]
      }),
      
      // 空行
      new Paragraph({ children: [] }),
      
      // 结尾
      new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: "--- 文档结束 ---", bold: true })]
      })
    ]
  }]
});

// 生成文档
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync("test_document.docx", buffer);
  console.log("测试文档已创建：test_document.docx");
  console.log("文档包含：");
  console.log("1. 标题和副标题");
  console.log("2. 多个段落");
  console.log("3. 带有表头的表格");
  console.log("4. 格式化的文本");
}).catch((error) => {
  console.error("创建文档时出错：", error);
});