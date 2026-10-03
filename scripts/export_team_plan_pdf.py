"""Export the beginner-friendly four-person plan as a polished PDF."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "可信医疗问答系统_四人分工与两个月计划.pdf"
FONT_PATH = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")


def p(text, style):
    return Paragraph(text, style)


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#D9E2F0"))
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.setFont("ArialUnicode", 7.5)
    canvas.setFillColor(colors.HexColor("#64748B"))
    canvas.drawString(18 * mm, 10 * mm, "可信医疗问答系统 - 四人分工与两个月计划")
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def weekly_card(week, items, checkpoint, styles):
    rows = [[p(f"第 {week} 周", styles["week"]), p(f"<b>本周检查：</b>{checkpoint}", styles["body"])]]
    labels = ["成员 1 - 资料与质量", "成员 2 - 搜索功能", "成员 3 - 回答与可靠性", "成员 4 - 测试与网页"]
    for label, item in zip(labels, items):
        rows.append([p(label, styles["label"]), p(item, styles["body"])])
    table = Table(rows, colWidths=[39 * mm, 133 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF2FF")),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F7FAFC")),
        ("TEXTCOLOR", (0, 0), (0, 0), colors.HexColor("#174EA6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2F0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return KeepTogether([table, Spacer(1, 4 * mm)])


def main():
    if not FONT_PATH.exists():
        raise FileNotFoundError(f"Chinese font not found: {FONT_PATH}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(TTFont("ArialUnicode", str(FONT_PATH)))

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="titleCN", parent=styles["Title"], fontName="ArialUnicode", fontSize=19,
        leading=25, textColor=colors.HexColor("#123B6D"), alignment=TA_CENTER, spaceAfter=7 * mm,
    ))
    styles.add(ParagraphStyle(
        name="h1CN", parent=styles["Heading1"], fontName="ArialUnicode", fontSize=13,
        leading=18, textColor=colors.HexColor("#174EA6"), spaceBefore=3 * mm, spaceAfter=3 * mm,
    ))
    styles.add(ParagraphStyle(
        name="h2CN", parent=styles["Heading2"], fontName="ArialUnicode", fontSize=10.5,
        leading=15, textColor=colors.HexColor("#1E3A5F"), spaceBefore=2 * mm, spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name="body", parent=styles["BodyText"], fontName="ArialUnicode", fontSize=8.7,
        leading=13, textColor=colors.HexColor("#172033"),
    ))
    styles.add(ParagraphStyle(
        name="small", parent=styles["BodyText"], fontName="ArialUnicode", fontSize=7.7,
        leading=11, textColor=colors.HexColor("#172033"),
    ))
    styles.add(ParagraphStyle(
        name="label", parent=styles["BodyText"], fontName="ArialUnicode", fontSize=7.6,
        leading=11, textColor=colors.HexColor("#344767"),
    ))
    styles.add(ParagraphStyle(
        name="week", parent=styles["BodyText"], fontName="ArialUnicode", fontSize=9,
        leading=13, textColor=colors.HexColor("#174EA6"),
    ))

    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=21 * mm,
        title="可信医疗问答系统：四人分工与两个月计划",
        author="项目组",
    )
    story = []
    story.append(p("可信医疗问答系统", styles["titleCN"]))
    story.append(p("四人分工与两个月计划（初学者版）", styles["h1CN"]))
    story.append(p(
        "我们要做一个中文医疗资料问答网页：系统先从可靠的指南、共识和教材中找相关原文，"
        "再根据原文生成回答，并告诉用户结论来自哪里。资料不足时，系统应明确说“暂时不能可靠回答”，"
        "而不是编造答案。", styles["body"]
    ))
    story.append(Spacer(1, 3 * mm))
    warning = Table([[p("<b>使用边界：</b>本项目仅用于课程和工程练习，不能用于真实诊断、治疗或用药建议。", styles["body"])]], colWidths=[174 * mm])
    warning.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7E6")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#F4B183")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([warning, Spacer(1, 4 * mm), p("读前小词典", styles["h1CN"])])
    glossary = [
        ("语料", "给系统查阅的医疗资料，例如指南、专家共识和教材。"),
        ("分片", "把一篇很长的资料切成适合搜索的小段，并保留其原文位置。"),
        ("检索 / 索引", "检索是找相关小段；索引是资料的“目录”，让搜索更快。"),
        ("重排", "对初次搜索结果再排序，把真正相关的内容放在前面。"),
        ("引用核验", "检查回答中的关键结论，是否真的被它标出的原文支持。"),
        ("拒答", "资料不足、条件不清或证据冲突时，不给出不可靠的具体结论。"),
        ("评测", "用事先准备的问题检查系统效果，并记录结果。"),
    ]
    glossary_table = Table([[p(a, styles["small"]), p(b, styles["small"])] for a, b in glossary], colWidths=[35 * mm, 139 * mm])
    glossary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF2FF")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([glossary_table, Spacer(1, 4 * mm), p("四人的角色", styles["h1CN"])])
    roles = [
        ("成员 1：资料与质量", "整理可用资料，记录来源和可靠性，切分长文并抽查原文。适合耐心、擅长整理的人。", "资料包、来源表、小段数据和抽检记录。"),
        ("成员 2：搜索功能", "建立关键词和语义两种搜索，合并并排序结果。适合愿意学习 Python 和调试的人。", "输入问题后返回相关原文的功能和搜索记录。"),
        ("成员 3：回答与可靠性", "让模型根据原文回答、标出引用，并在资料不足时拒答。适合擅长归纳和写提示词的人。", "回答格式、引用规则、核验/拒答逻辑和失败分析。"),
        ("成员 4：测试与网页", "准备测试题，整合网页，保存实验结果并完成说明与演示。适合偏工程、产品或文档组织的人。", "测试题、结果表、可运行网页和演示材料。"),
    ]
    role_rows = [[p("角色", styles["small"]), p("主要工作", styles["small"]), p("交付物", styles["small"])]]
    role_rows += [[p(a, styles["small"]), p(b, styles["small"]), p(c, styles["small"])] for a, b, c in roles]
    role_table = Table(role_rows, colWidths=[38 * mm, 83 * mm, 53 * mm], repeatRows=1)
    role_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#174EA6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#F1F6FD")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#C9D7EA")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(role_table)

    weeks = [
        (1, ["选定 2-3 个医疗主题；列出可用资料和记录格式。", "安装环境；确定搜索结果应包含哪些信息。", "确定回答模板：答案、引用、不能回答时的提示。", "设计测试题模板，建立共享任务表和实验文件夹。"], "全组能跑通一个最小示例。"),
        (2, ["整理首批资料，切成小段并抽查能否回到原文。", "建立关键词搜索和语义搜索的初版。", "用少量示例实现“根据原文回答并标引用”。", "写 20-30 道测试题，标出每题应找到的原文。"], "用首批资料回答若干测试题。"),
        (3, ["修复切分问题，重点检查表格、剂量、禁忌和否定句。", "合并两种搜索结果，并记录搜索到什么、花多久。", "把搜索结果接入回答；记录模型输入、输出和引用。", "自动保存每次测试结果，制作基础对比表。"], "完成“提问 - 找资料 - 回答”的全流程。"),
        (4, ["按来源抽检低质量小段，确认资料版本。", "加入二次排序和上下文补充，让结果更完整。", "制作“这句话是否被原文支持”的判断样例。", "自动比较不同搜索方案；开始网页框架。"], "确认哪种搜索组合更可靠。"),
        (5, ["根据错误案例修复资料或记录问题。", "用测试题调搜索结果数量和排序参数。", "实现关键句核验：不被支持的句子删除、改写或拒答。", "把搜索、回答和原文引用显示在网页上。"], "人工抽查引用是否真的支持回答。"),
        (6, ["整理资料来源、版本和使用许可说明。", "检查搜索服务稳定性和多人使用时的问题。", "调整拒答标准，重点测试“资料中没有答案”的问题。", "加入资料上传、基础会话和部署配置；完善测试。"], "完整系统能正确处理可答与不可答问题。"),
        (7, ["复核失败题涉及的资料是否有误。", "修复搜不到或搜错资料的问题，固定搜索配置。", "修复引用和拒答失败，固定回答模板。", "跑完全部对比测试，统计准确性、引用和耗时。"], "任何成员可按说明复现同样结果。"),
        (8, ["整理资料说明和质量记录。", "整理搜索构建与检查说明。", "完成引用/拒答人工检查结论。", "完成网页演示、使用指南、实验报告和答辩材料。"], "最终演示彩排与交付归档。"),
    ]
    story.extend([PageBreak(), p("两个月计划：第 1-4 周", styles["h1CN"])])
    story.append(p("四条线同步推进。成员 3 和成员 4 从第 2 周起即可使用小样本开发，不必等待全部资料准备完成。", styles["body"]))
    story.append(Spacer(1, 3 * mm))
    for week in weeks[:4]:
        story.append(weekly_card(*week, styles))
    story.extend([PageBreak(), p("两个月计划：第 5-8 周", styles["h1CN"])])
    for week in weeks[4:]:
        story.append(weekly_card(*week, styles))
    story.extend([PageBreak(), p("每周协作方式与最终交付", styles["h1CN"])])
    collaboration = [
        ("周初", "在共享任务表写清本周要交什么；不懂的术语先在小词典或群里确认。"),
        ("周中", "成员 1 提供小样本；成员 2 即使只有简版搜索也交给成员 3、4 使用，避免等待全量资料。"),
        ("周末", "用 10-20 道固定小题测试一次，记录找到了什么原文、回答是什么、引用对不对、哪里失败。"),
        ("第 4 周后", "资料版本尽量不再随意变动；第 7 周后测试题、搜索参数和回答模板尽量固定，保证结果可重复。"),
    ]
    collaboration_table = Table([[p(a, styles["small"]), p(b, styles["small"])] for a, b in collaboration], colWidths=[32 * mm, 142 * mm])
    collaboration_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF2FF")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2F0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([collaboration_table, Spacer(1, 6 * mm), p("最终交付清单", styles["h1CN"])])
    deliverables = [
        "一个可运行的中文医疗问答网页；",
        "每个关键回答都能查看对应原文和出处；",
        "面对资料不足的问题，系统会说明无法可靠回答；",
        "一套可重复运行的测试及结果表，展示不同方案的效果；",
        "资料说明、使用/部署说明、实验报告和答辩材料。",
    ]
    for item in deliverables:
        story.append(p(f"- {item}", styles["body"]))
        story.append(Spacer(1, 1.5 * mm))
    story.append(Spacer(1, 5 * mm))
    story.append(p("共同责任：每人每周抽查一小批“原文 - 搜索结果 - 回答”的对应关系；不把测试题答案放进资料库；不使用未授权资料或真实患者隐私。", styles["body"]))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
