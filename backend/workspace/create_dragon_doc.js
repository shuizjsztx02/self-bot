const fs = require('fs');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, 
        Header, Footer, AlignmentType, PageOrientation, LevelFormat, 
        HeadingLevel, BorderStyle, WidthType, ShadingType, 
        VerticalAlign, PageNumber, PageBreak } = require('docx');

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
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 26, bold: true, font: "Arial" },
        paragraph: { 
          spacing: { before: 120, after: 120 }
        }
      }
    ]
  },
  numbering: {
    config: [
      {
        reference: "numbers",
        levels: [{
          level: 0,
          format: LevelFormat.DECIMAL,
          text: "%1.",
          alignment: AlignmentType.LEFT,
          style: {
            paragraph: {
              indent: { left: 720, hanging: 360 }
            }
          }
        }]
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
        margin: { 
          top: 1440,      // 1 inch
          right: 1440, 
          bottom: 1440, 
          left: 1440 
        }
      }
    },
    headers: {
      default: new Header({
        children: [
          new Paragraph({
            children: [
              new TextRun({
                text: "龙年吉祥祝福语大全",
                bold: true,
                size: 20
              })
            ],
            alignment: AlignmentType.CENTER
          })
        ]
      })
    },
    footers: {
      default: new Footer({
        children: [
          new Paragraph({
            children: [
              new TextRun("第 "),
              new TextRun({ children: [PageNumber.CURRENT] }),
              new TextRun(" 页")
            ],
            alignment: AlignmentType.CENTER
          })
        ]
      })
    },
    children: [
      // 标题
      new Paragraph({
        heading: HeadingLevel.HEADING_1,
        children: [
          new TextRun("龙年吉祥祝福语大全")
        ],
        alignment: AlignmentType.CENTER,
        spacing: { after: 480 }
      }),

      // 副标题
      new Paragraph({
        children: [
          new TextRun({
            text: "2024年（甲辰龙年）",
            bold: true,
            size: 26
          })
        ],
        alignment: AlignmentType.CENTER,
        spacing: { after: 360 }
      }),

      // 引言
      new Paragraph({
        children: [
          new TextRun("龙年到来，万象更新。龙在中国文化中象征着吉祥、尊贵和力量。以下是为您精心整理的龙年祝福语，适用于各种场合，表达对亲朋好友的美好祝愿。")
        ],
        spacing: { before: 240, after: 480 }
      }),

      // 分隔线
      new Paragraph({
        children: [
          new TextRun("————————————————————————————————")
        ],
        alignment: AlignmentType.CENTER,
        spacing: { before: 120, after: 240 }
      }),

      // 一、通用祝福语
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [
          new TextRun("一、通用祝福语")
        ],
        spacing: { before: 240, after: 180 }
      }),

      // 通用祝福语列表
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun({
            text: "龙年大吉，万事如意！",
            bold: true
          })
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙马精神，身体健康！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙腾虎跃，事业腾飞！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年行大运，财源滚滚来！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年吉祥，阖家幸福！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙飞凤舞，前程似锦！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年好运，心想事成！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年快乐，福气满满！")
        ]
      }),

      new Paragraph({
        children: [new PageBreak()]
      }),

      // 二、商务祝福语
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [
          new TextRun("二、商务祝福语")
        ],
        spacing: { before: 240, after: 180 }
      }),

      // 商务祝福语列表
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun({
            text: "龙年生意兴隆，财源广进！",
            bold: true
          })
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙腾四海，事业蒸蒸日上！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年大展宏图，再创辉煌！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙行天下，商机无限！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年合作愉快，共赢未来！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年财源茂盛，生意红火！")
        ]
      }),

      // 三、家庭祝福语
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [
          new TextRun("三、家庭祝福语")
        ],
        spacing: { before: 240, after: 180 }
      }),

      // 家庭祝福语列表
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun({
            text: "龙年阖家欢乐，幸福安康！",
            bold: true
          })
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年子孙满堂，家庭和睦！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年平安喜乐，万事顺心！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年福星高照，好运连连！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年身体健康，笑口常开！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年家和万事兴，幸福永相随！")
        ]
      }),

      new Paragraph({
        children: [new PageBreak()]
      }),

      // 四、朋友祝福语
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [
          new TextRun("四、朋友祝福语")
        ],
        spacing: { before: 240, after: 180 }
      }),

      // 朋友祝福语列表
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun({
            text: "龙年友谊长存，情谊永固！",
            bold: true
          })
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年快乐相伴，幸福相随！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年心想事成，梦想成真！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年好运连连，开心每一天！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年笑口常开，青春永驻！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年友谊万岁，真情永恒！")
        ]
      }),

      // 五、创意祝福语
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [
          new TextRun("五、创意祝福语")
        ],
        spacing: { before: 240, after: 180 }
      }),

      // 创意祝福语列表
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun({
            text: "龙年龙抬头，好运天天有！",
            bold: true
          })
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年舞龙灯，幸福亮晶晶！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年赛龙舟，快乐永不休！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年画龙点睛，事业更光明！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年龙吟虎啸，气势冲云霄！")
        ]
      }),
      new Paragraph({
        numbering: { reference: "numbers", level: 0 },
        children: [
          new TextRun("龙年龙飞九天，梦想都实现！")
        ]
      }),

      // 结语
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [
          new TextRun("结语")
        ],
        spacing: { before: 480, after: 240 }
      }),

      new Paragraph({
        children: [
          new TextRun("龙年象征着新的开始和无限可能。愿这些祝福语能为您带来好运和快乐，祝您龙年大吉，万事如意！")
        ],
        spacing: { before: 120, after: 240 }
      }),

      new Paragraph({
        children: [
          new TextRun({
            text: "愿龙年的祥瑞之气伴随您一整年，让好运如龙般腾飞，幸福如龙般长久！",
            bold: true,
            size: 26
          })
        ],
        alignment: AlignmentType.CENTER,
        spacing: { before: 240, after: 480 }
      }),

      // 页脚信息
      new Paragraph({
        children: [
          new TextRun("————————————————————————————————")
        ],
        alignment: AlignmentType.CENTER,
        spacing: { before: 360, after: 120 }
      }),

      new Paragraph({
        children: [
          new TextRun({
            text: "祝福语整理于2024年龙年春节前夕",
            italics: true
          })
        ],
        alignment: AlignmentType.CENTER
      }),

      new Paragraph({
        children: [
          new TextRun({
            text: "愿您和家人朋友共享龙年的喜悦与幸福",
            italics: true
          })
        ],
        alignment: AlignmentType.CENTER,
        spacing: { after: 480 }
      })
    ]
  }]
});

// 保存文档
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync('龙年吉祥祝福语大全.docx', buffer);
  console.log('Word文档已创建：龙年吉祥祝福语大全.docx');
}).catch((error) => {
  console.error('创建文档时出错：', error);
});