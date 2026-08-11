#!/usr/bin/env python3
"""Generate the phase 2/3 final-conclusion report (2026-08-11)."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "阶段二与阶段三最终结论汇报_2026-08-11.pdf"

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")

NAVY = colors.HexColor("#12324A")
BLUE = colors.HexColor("#1768A8")
CYAN = colors.HexColor("#0E9FB1")
GREEN = colors.HexColor("#0F766E")
AMBER = colors.HexColor("#B45309")
RED = colors.HexColor("#B42318")
INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#667085")
LINE = colors.HexColor("#D0D5DD")
PALE_GREEN = colors.HexColor("#E9F7F2")
PALE_AMBER = colors.HexColor("#FFF6E5")
PALE_RED = colors.HexColor("#FDECEC")


pdfmetrics.registerFont(TTFont("MSYH", str(FONT_REGULAR), subfontIndex=0))
pdfmetrics.registerFont(TTFont("MSYH-Bold", str(FONT_BOLD), subfontIndex=0))

base = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle("title", parent=base["Title"], fontName="MSYH-Bold", fontSize=21, leading=29, alignment=TA_LEFT, textColor=NAVY, spaceAfter=4 * mm),
    "kicker": ParagraphStyle("kicker", parent=base["Normal"], fontName="MSYH-Bold", fontSize=9, leading=14, textColor=CYAN, spaceAfter=2 * mm),
    "lead": ParagraphStyle("lead", parent=base["BodyText"], fontName="MSYH", fontSize=10.2, leading=17, textColor=INK, spaceAfter=3 * mm),
    "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="MSYH-Bold", fontSize=13.2, leading=18.5, textColor=BLUE, spaceBefore=2.2 * mm, spaceAfter=2.2 * mm),
    "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="MSYH-Bold", fontSize=10.2, leading=15, textColor=NAVY, spaceBefore=1.4 * mm, spaceAfter=1.4 * mm),
    "body": ParagraphStyle("body", parent=base["BodyText"], fontName="MSYH", fontSize=9, leading=14.5, textColor=INK, spaceAfter=1.6 * mm),
    "bullet": ParagraphStyle("bullet", parent=base["BodyText"], fontName="MSYH", fontSize=9, leading=14.5, textColor=INK, leftIndent=5 * mm, bulletIndent=1.5 * mm, spaceAfter=1 * mm),
    "callout": ParagraphStyle("callout", parent=base["BodyText"], fontName="MSYH", fontSize=9.4, leading=16, textColor=INK, backColor=PALE_GREEN, borderColor=GREEN, borderWidth=0.8, borderPadding=6, spaceAfter=3 * mm),
}


def para(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLES[style])


def draw_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("MSYH-Bold", 8)
    canvas.drawString(14 * mm, A4[1] - 4.4 * mm, "Agent 世界模型决策优化 · 阶段二与阶段三最终结论汇报")
    canvas.setFont("MSYH", 8)
    canvas.drawRightString(A4[0] - 14 * mm, A4[1] - 4.4 * mm, "2026-08-11")
    canvas.setFillColor(MUTED)
    canvas.setFont("MSYH", 8)
    canvas.drawCentredString(A4[0] / 2, 8 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def build() -> None:
    rows = [
        ("观察反事实采集", "3,600 对有效，3,050 对有信息", PALE_GREEN),
        ("阶段二数据质量门禁", "全部通过", PALE_GREEN),
        ("RTX 4090 多种子训练", "5 次训练，选择 3 个成员", PALE_GREEN),
        ("阶段二独立测试", "12 项验收检查全部通过", PALE_GREEN),
        ("阶段三反事实与多步评估", "两项验收均通过", PALE_GREEN),
        ("高风险证据复核", "500 条 evidence_verified；自动证据验收通过", PALE_AMBER),
        ("AndroidWorld", "真实 reset/action 冒烟通过；任务级基线/规划器对比仍待 KVM 环境", PALE_AMBER),
        ("WebArena 在线重评", "本轮未执行，不能声称成功率提高", PALE_RED),
    ]
    story = [
        para("AGENT WORLD MODEL · 最终结论", "kicker"),
        para("阶段二与阶段三最终结论汇报", "title"),
        para("面向《大创申报书 33.0》的技术路线，汇总阶段二（动作条件世界模型）与阶段三（候选动作生成、1–3 步推演与有限步重排）的最终结论：5 项已完成、2 项部分完成、1 项未执行。所有结论均来自已同步的 JSON 报告与真实运行证据，未把离线指标等同于 WebArena 在线成功率。", "lead"),
        para("一、最终结论总览", "h1"),
        Table(
            [["最终结论", "状态"]] + [[name, status] for name, status, _ in rows],
            colWidths=[72 * mm, 108 * mm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "MSYH"),
                ("FONTNAME", (0, 0), (-1, 0), "MSYH-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("BACKGROUND", (0, 1), (-1, 1), PALE_GREEN),
                ("BACKGROUND", (0, 2), (-1, 2), PALE_GREEN),
                ("BACKGROUND", (0, 3), (-1, 3), PALE_GREEN),
                ("BACKGROUND", (0, 4), (-1, 4), PALE_GREEN),
                ("BACKGROUND", (0, 5), (-1, 5), PALE_GREEN),
                ("BACKGROUND", (0, 6), (-1, 6), PALE_AMBER),
                ("BACKGROUND", (0, 7), (-1, 7), PALE_AMBER),
                ("BACKGROUND", (0, 8), (-1, 8), PALE_RED),
            ]),
        ),
        Spacer(1, 2 * mm),
        para("二、已完成项（5 项）", "h1"),
        para("1. 观察反事实采集", "h2"),
        para("3,600 对全部有效、3,050 对有信息（信息率 84.72%）、0 采集失败、配对状态匹配率 100%，且同一初始状态的全部干预只进入一个数据划分，无跨 split 泄漏。", "body"),
        para("2. 阶段二数据质量门禁", "h2"),
        para("训练数据 13,348 条转移、5,930 个 episode、30 个任务；train/validation/test 划分无重复样本与无 episode 泄漏，P0/P1 数据门槛通过。", "body"),
        para("3. RTX 4090 多种子训练", "h2"),
        para("完成 5 个随机种子（17/29/42/73/101）的独立训练，仅按验证集选择 3 个成员组成集成；风险校准 ECE 由 0.0266 降至 0.0104，进度 MAE 由 0.0612 降至 0.0543。", "body"),
        para("4. 阶段二独立测试", "h2"),
        para("12 项验收检查全部通过：状态变化 F1 98.69%、任务信号 F1 98.90%、风险 F1 94.39%、风险 AUROC 99.04%、进度 MAE 0.0992。", "body"),
        para("5. 阶段三反事实与多步评估", "h2"),
        para("两项验收均通过：反事实排序 396 个有效测试配对、Pairwise Accuracy 97.73%、NDCG@2 0.9916、集成遗憾 0.0511；真实连续轨迹 H=1/2/3 窗口分别为 1,943/619/329。", "body"),
        para("三、部分完成项（2 项）", "h1"),
        para("6. 高风险证据复核", "h2"),
        para("500/500 条高风险、终止与严重失败样本均唯一回溯到原始环境轨迹，已写为 evidence_verified 并完成自动证据验收；按项目规则人工签字不是验收门槛，审计来源仍如实保留（human_signoff=false，不冒充人工审核）。", "body"),
        para("7. AndroidWorld", "h2"),
        para("官方 0.1.0 在 API 33 软件仿真设备上完成真实 reset/action/state 冒烟（18 个无障碍 UI 元素，截图带 SHA-256 证据）；容器无 /dev/kvm，任务级基线/规划器对比仍需 KVM 加速主机，因此不能声称迁移完成。", "body"),
        para("四、未完成项（1 项）", "h1"),
        para("8. WebArena 在线重评", "h2"),
        para("本轮未配置多站点在线环境，未执行新的成功率评测，因此不能声称成功率提高。已具备可重复的 Reddit 在线评测链，自主 Agent 此前实测 0/5，相对反应式基线提升 +10% 属于阶段四目标。", "body"),
        para("五、总体结论与下一步", "h1"),
        para("阶段二与阶段三的离线工程目标已经完成：数据规模与质量门禁通过，五次多种子 GPU 训练完成，阶段二联合预测和阶段三反事实/多步评估均通过既定验收；证据复核与 AndroidWorld 冒烟也已完成。未完成的是 WebArena 在线成功率提升和 AndroidWorld 任务级迁移验收，这些事项不得被当前离线结果替代。", "callout"),
        para("建议按以下顺序推进：", "h2"),
        para("1. 恢复 WebArena 多站点在线评测链，以固定任务、固定预算、固定种子做重评，核对相对基线的成功率提升；", "bullet"),
        para("2. 将 AndroidWorld 模拟器迁移到 KVM 主机（或本机 WHPX），复跑预检与冒烟后执行任务级基线/规划器对比；", "bullet"),
        para("3. 完成上述在线与跨环境证据后，再进入阶段四的反馈—遗憾闭环实验。", "bullet"),
        para("六、关键指标速览", "h1"),
        Table(
            [
                ["指标", "数值"],
                ["训练数据", "13,348 条转移 · 5,930 episodes · 30 任务"],
                ["观察反事实", "3,600 对有效 · 3,050 对有信息（84.72%）"],
                ["多种子训练", "5 个种子 · 验证集选 3 成员集成"],
                ["阶段二测试", "状态 F1 98.69% · 任务 F1 98.90% · 风险 F1 94.39%"],
                ["风险校准", "ECE 0.0266 → 0.0104"],
                ["阶段三排序", "Pairwise 97.73% · NDCG@2 0.9916 · 集成遗憾 0.0511"],
                ["多步窗口", "H=1 1,943 · H=2 619 · H=3 329"],
                ["AndroidWorld", "API 33 冒烟通过 · 18 个 UI 元素"],
                ["证据复核", "500/500 evidence_verified"],
            ],
            colWidths=[52 * mm, 128 * mm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "MSYH"),
                ("FONTNAME", (0, 0), (-1, 0), "MSYH-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#EAF2F8")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]),
        ),
        Spacer(1, 2 * mm),
        para("七、证据与交付物", "h1"),
        para("• 代码仓库：github.com/yilaxin/agent-world-model（分支 codex/phase2-world-model，草稿 PR #1）；", "bullet"),
        para("• 公开看板：https://yilaxin.github.io/agent-world-model/（GitHub Pages，与私有 Sites 看板内容一致）；", "bullet"),
        para("• 运行证据：data/reports/ 下 phase2_* 训练/评估 JSON、androidworld_preflight_latest.json、androidworld_smoke_latest.json 及截图；", "bullet"),
        para("• 报告文件：AndroidWorld真实迁移冒烟验收汇报_2026-08-11.pdf、阶段二阶段三最终进度与遗留问题报告_2026-08-10.pdf；", "bullet"),
        para("• GPU 服务器：/root/autodl-tmp/agent_world_model_phase23_latest（权重、日志与结果）。", "bullet"),
    ]

    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    print(OUTPUT)


if __name__ == "__main__":
    build()
