#!/usr/bin/env python3
"""Generate the proposal-aligned phase 2/3 progress and risk report."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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
OUTPUT = ROOT / "output" / "pdf" / "阶段二阶段三进度与遗留问题报告_2026-08-09.pdf"
FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")

NAVY = colors.HexColor("#14324A")
BLUE = colors.HexColor("#1667A8")
CYAN = colors.HexColor("#14A6B8")
GREEN = colors.HexColor("#0F766E")
AMBER = colors.HexColor("#B45309")
RED = colors.HexColor("#B42318")
INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#667085")
PALE_BLUE = colors.HexColor("#EAF4FB")
PALE_GREEN = colors.HexColor("#E9F7F2")
PALE_AMBER = colors.HexColor("#FFF6E5")
PALE_RED = colors.HexColor("#FDECEC")
LINE = colors.HexColor("#D0D5DD")


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def table(rows, widths, *, header=True, font_size=8.3, row_colors=None):
    formatted = []
    for row_idx, row in enumerate(rows):
        style = STYLES["table_header"] if header and row_idx == 0 else STYLES["table_cell"]
        formatted.append([p(str(cell), style) for cell in row])
    t = Table(formatted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("FONTNAME", (0, 0), (-1, -1), "MSYH"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "MSYH-Bold"),
        ]
    if row_colors:
        start = 1 if header else 0
        for idx, bg in enumerate(row_colors, start=start):
            commands.append(("BACKGROUND", (0, idx), (-1, idx), bg))
    t.setStyle(TableStyle(commands))
    return t


def section(title: str, subtitle: str | None = None):
    items = [Spacer(1, 3 * mm), p(title, STYLES["h1"])]
    if subtitle:
        items.append(p(subtitle, STYLES["subtitle"]))
    items.append(Spacer(1, 2 * mm))
    return items


def bullet(text: str, tone=INK):
    style = ParagraphStyle(
        "bullet_local",
        parent=STYLES["body"],
        textColor=tone,
        leftIndent=5 * mm,
        firstLineIndent=-3.5 * mm,
        bulletIndent=0,
        spaceAfter=2.5 * mm,
    )
    return p(f"• {text}", style)


def draw_page(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 10 * mm, width, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(MUTED)
    canvas.setFont("MSYH", 7.5)
    canvas.drawString(16 * mm, 8 * mm, "Agent 世界模型决策优化 | 阶段二、阶段三")
    canvas.drawRightString(width - 16 * mm, 8 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


pdfmetrics.registerFont(TTFont("MSYH", str(FONT_REGULAR), subfontIndex=0))
pdfmetrics.registerFont(TTFont("MSYH-Bold", str(FONT_BOLD), subfontIndex=0))

base = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle(
        "title",
        parent=base["Title"],
        fontName="MSYH-Bold",
        fontSize=23,
        leading=32,
        alignment=TA_LEFT,
        textColor=NAVY,
        spaceAfter=5 * mm,
    ),
    "kicker": ParagraphStyle(
        "kicker",
        parent=base["Normal"],
        fontName="MSYH-Bold",
        fontSize=9,
        leading=14,
        textColor=CYAN,
        spaceAfter=2 * mm,
    ),
    "lead": ParagraphStyle(
        "lead",
        parent=base["BodyText"],
        fontName="MSYH",
        fontSize=11,
        leading=19,
        textColor=INK,
        spaceAfter=4 * mm,
    ),
    "h1": ParagraphStyle(
        "h1",
        parent=base["Heading1"],
        fontName="MSYH-Bold",
        fontSize=15,
        leading=22,
        textColor=BLUE,
        spaceAfter=2 * mm,
    ),
    "h2": ParagraphStyle(
        "h2",
        parent=base["Heading2"],
        fontName="MSYH-Bold",
        fontSize=11,
        leading=17,
        textColor=NAVY,
        spaceBefore=2 * mm,
        spaceAfter=2 * mm,
    ),
    "subtitle": ParagraphStyle(
        "subtitle",
        parent=base["BodyText"],
        fontName="MSYH",
        fontSize=8.5,
        leading=14,
        textColor=MUTED,
    ),
    "body": ParagraphStyle(
        "body",
        parent=base["BodyText"],
        fontName="MSYH",
        fontSize=9.2,
        leading=16,
        textColor=INK,
        spaceAfter=2.5 * mm,
    ),
    "small": ParagraphStyle(
        "small",
        parent=base["BodyText"],
        fontName="MSYH",
        fontSize=7.6,
        leading=12,
        textColor=MUTED,
    ),
    "table_header": ParagraphStyle(
        "table_header",
        parent=base["BodyText"],
        fontName="MSYH-Bold",
        fontSize=8.1,
        leading=12,
        textColor=colors.white,
        alignment=TA_CENTER,
    ),
    "table_cell": ParagraphStyle(
        "table_cell",
        parent=base["BodyText"],
        fontName="MSYH",
        fontSize=8.1,
        leading=13,
        textColor=INK,
    ),
    "callout": ParagraphStyle(
        "callout",
        parent=base["BodyText"],
        fontName="MSYH-Bold",
        fontSize=10,
        leading=17,
        textColor=NAVY,
        leftIndent=5 * mm,
        rightIndent=5 * mm,
        spaceBefore=3 * mm,
        spaceAfter=3 * mm,
    ),
}


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=15 * mm,
        title="阶段二阶段三进度与遗留问题报告",
        author="Agent 世界模型项目组",
    )
    story = []

    story += [
        Spacer(1, 17 * mm),
        p("项目复核报告 · 2026-08-09", STYLES["kicker"]),
        p("阶段二、阶段三<br/>进度与遗留问题报告", STYLES["title"]),
        p(
            "依据《大创申报书 33.0》重新对齐：阶段二完成动作条件一步世界模型和状态、进度、风险、终止预测；阶段三完成候选动作生成、1 至 3 步推演、综合评分、结构一致性与有限步重排序。",
            STYLES["lead"],
        ),
        Spacer(1, 4 * mm),
        table(
            [
                ["当前结论", "状态"],
                ["阶段二、阶段三代码原型", "已完成并增强"],
                ["本地自动化测试", "58 项通过"],
                ["历史 RTX 4090 多种子训练", "5 次训练，选 3 个模型集成"],
                ["本轮 P0/P1 增强后的 GPU 重跑", "脚本已就绪，待远程终端启动"],
                ["真实 WebArena 成功率", "旧实测 0/5，不能宣称已提高"],
            ],
            [70 * mm, 90 * mm],
            row_colors=[PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_AMBER, PALE_RED],
        ),
        Spacer(1, 6 * mm),
        p(
            "验收口径：代码存在不等于指标达标；模拟或离线排序不等于真实在线成功率；目标值不写成完成值。WebArena 完整多站点和相对成功率 +10% 属于后续闭环验证，不作为阶段二、三当前已完成结论。",
            STYLES["callout"],
        ),
        Spacer(1, 14 * mm),
        p("代码仓库：https://github.com/yilaxin/agent-world-model", STYLES["small"]),
        p("进度看板：https://agent-world-model-phase23-lzk.zhengkunlu4.chatgpt.site", STYLES["small"]),
        p("Git 提交：742658d · 分支：codex/phase2-world-model · PR #1", STYLES["small"]),
    ]

    story.append(PageBreak())
    story += section("1. 与申报书的逐项对齐")
    story.append(
        table(
            [
                ["阶段", "申报书要求", "本轮实现", "验收状态"],
                ["阶段二", "数据集采集", "分组切分、反事实配对、真实多步窗口、人工复核队列与质量门禁", "代码完成；扩充采集待 GPU/环境运行"],
                ["阶段二", "LLM 语义世界模型", "保留语义状态编码接口；候选适配器支持规则、LLM/VLM 同预算比较", "接口完成；具体供应商凭证未绑定"],
                ["阶段二", "可训练一步世界模型", "多任务预测头加入 Pairwise RankNet，支持多种子训练、校准和非负集成权重", "历史 GPU 训练已验证；增强版待重跑"],
                ["阶段二", "状态、进度、风险、终止预测", "状态变化、进度、奖励、成功、停滞、偏离、严重失败和终止联合预测", "完成"],
                ["阶段三", "候选动作生成", "AXTree 安全候选、目标论坛语义动作、动作合法性校验", "完成"],
                ["阶段三", "世界模型推演", "1 至 3 步有限推演和真实连续轨迹 H=1/2/3 漂移评测", "完成；H3 和严重失败覆盖不足"],
                ["阶段三", "综合评分与结构一致性", "短期/长期收益、风险、不确定性、任务元素结构分数联合排序", "完成"],
                ["阶段三", "有限步重排序", "置信度自适应 H=1..3，保留重新观察和安全回退", "完成"],
            ],
            [21 * mm, 42 * mm, 77 * mm, 34 * mm],
            row_colors=[PALE_BLUE, PALE_BLUE, PALE_BLUE, PALE_GREEN, PALE_BLUE, PALE_AMBER, PALE_GREEN, PALE_GREEN],
            font_size=7.6,
        )
    )

    story += section("2. 本轮完成的关键改进")
    story += [
        bullet("反事实 P0：按同一初始状态绑定事实动作与受控候选；训练新增成对排序损失；评测只统计真实有差异的配对，给出 bootstrap 区间、遗憾和非劣门禁。"),
        bullet("数据质量 P1：导出 300 条优先人工复核队列，只有 review_status=approved 且填写 reviewer 的记录才能回写；保留来源和复核元数据。"),
        bullet("多步 P1：构建不跨 episode、不越过终止状态的连续 H=1/2/3 窗口；新增终止、严重失败覆盖门禁和 H3/H1 漂移门禁。"),
        bullet("WebArena：修复 Reddit 目标论坛定位策略，增加搜索框填充、回车和精确搜索结果点击；步数预算由 6 提高到 12；新增真实同重置反事实任务配置。"),
        bullet("AndroidWorld：预检覆盖 ADB、模拟器、API 33、端口 8554、Python 包、gRPC、Docker/KVM，并提供迁移运行手册。"),
        bullet("统一运行：scripts/run_phase23_improvement.sh 串联采集、数据门禁、5 次多种子训练、3 模型集成、反事实评测和真实多步评测。"),
    ]

    story.append(PageBreak())
    story += section("3. 已有真实结果与解释边界", "以下数字来自已存在的 RTX 4090 或真实日志结果，不代表本轮增强版已经重跑。")
    story.append(p("阶段二历史多种子 GPU 结果", STYLES["h2"]))
    story.append(
        table(
            [
                ["指标", "结果", "说明"],
                ["训练次数 / 集成规模", "5 / 3", "5 个种子和配置中选择 3 个成员"],
                ["测试状态变化 F1", "0.9888 ± 0.0011", "5 次训练均值与标准差"],
                ["测试任务信号 F1", "0.9795 ± 0.0047", "invalid_action、terminal"],
                ["测试风险 F1", "0.8977 ± 0.0181", "success、stalled、goal deviation、severe failure"],
                ["测试风险 AUROC", "0.9931 ± 0.0009", "存在类别不平衡，需结合 ECE/Brier"],
                ["校准后风险 ECE", "0.0091", "集成校准后优于校准前 0.0249"],
                ["测试进度 MAE", "0.0658 ± 0.0048", "越低越好"],
            ],
            [50 * mm, 41 * mm, 83 * mm],
            row_colors=[PALE_GREEN] * 7,
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(p("阶段三历史 GPU 决策结果", STYLES["h2"]))
    story.append(
        table(
            [
                ["指标", "结果", "解释"],
                ["评测样本", "515", "离线保留集，不是在线成功率"],
                ["安全记录动作 Recall@K", "1.000", "候选集合覆盖记录中的安全动作"],
                ["有限步合规率", "1.000", "所有决策均使用 H=1..3"],
                ["解释完整率", "1.000", "每次决策给出依据和回退信息"],
                ["风险动作分流率", "0.6655", "阶段三对记录风险动作的分流比例"],
                ["平均决策延迟", "20.59 ms", "离线 GPU 评测"],
                ["真实 WebArena", "0/5", "Reddit 子集旧实测；动作执行率 1.0，但未成功"],
            ],
            [50 * mm, 36 * mm, 88 * mm],
            row_colors=[PALE_BLUE, PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_BLUE, PALE_RED],
        )
    )
    story.append(Spacer(1, 4 * mm))
    story.append(p("本地真实连续轨迹漂移评测", STYLES["h2"]))
    story.append(
        table(
            [
                ["H", "窗口数", "Latent MSE", "余弦相似度", "终止样本", "严重失败"],
                ["1", "231", "0.000244", "0.9324", "34", "0"],
                ["2", "124", "0.000350", "0.9068", "11", "0"],
                ["3", "59", "0.000460", "0.8890", "5", "0"],
            ],
            [18 * mm, 28 * mm, 32 * mm, 35 * mm, 30 * mm, 31 * mm],
            row_colors=[PALE_GREEN, PALE_AMBER, PALE_RED],
        )
    )
    story.append(p("结论：H2 数量和 H3/H1 漂移有界通过；H3 数量、长程终止样本和严重失败样本未达到门禁，且模型 MSE 未优于 persistence baseline，不能标记阶段三多步实证验收通过。", STYLES["body"]))

    story.append(PageBreak())
    story += section("4. 图片中六类问题的处理状态")
    story.append(
        table(
            [
                ["优先级", "问题", "本轮处理", "剩余工作"],
                ["P0", "WebArena 成功率 0%", "修复目标论坛语义导航；步数 6→12；新增受控真实反事实配置", "需在线重跑固定任务；完整多站点和相对 +10% 放在阶段四"],
                ["P0", "反事实仅 100 对", "三策略采集、Pairwise RankNet、非负集成、bootstrap/非劣门禁；目标 3600 MiniWoB +15 WebArena 对", "需在服务器实际采集和重训；旧 100 对结论仍不变"],
                ["P1", "启发式标签为主", "导出 300 条人工复核队列，其中 WebArena 34、终止 166、严重失败 65", "当前 300 条均 pending，需要人工检查证据后批准"],
                ["P1", "H2/3 累积偏差", "真实连续轨迹评测和 H2/H3/终止/严重失败门禁；增加多步、终止失败采集配置", "当前 H3=59、长程严重失败=0，需补采后重训"],
                ["P2", "AndroidWorld 仅适配", "完成官方环境预检与迁移手册", "本机缺 ADB、模拟器、API33 和运行包；服务器还需确认 KVM"],
                ["外部", "GitHub / Sites", "GitHub 已推送；Sites 第 1 版已生产部署并保持仅所有者访问", "已解决"],
            ],
            [16 * mm, 39 * mm, 72 * mm, 47 * mm],
            row_colors=[PALE_AMBER, PALE_AMBER, PALE_AMBER, PALE_AMBER, PALE_RED, PALE_GREEN],
            font_size=7.5,
        )
    )
    story += section("5. GPU 多轮训练执行与验收")
    story += [
        p("服务器目录：/root/autodl-tmp/agent_world_model_phase2", STYLES["body"]),
        p("在已经连接的 VS Code 远程终端中执行：", STYLES["body"]),
        table(
            [["命令"], ["git pull --ff-only origin codex/phase2-world-model<br/>bash scripts/run_phase23_improvement.sh"]],
            [174 * mm],
            row_colors=[colors.HexColor("#F8FAFC")],
        ),
        Spacer(1, 3 * mm),
        bullet("先采集多步、终止失败和反事实数据，再执行数据质量门禁。门禁失败时停止，防止在不足数据上继续给出乐观结果。"),
        bullet("通过门禁后执行 5 次多种子训练，按验证集选择 3 个模型，并在独立测试集报告一次最终结果。"),
        bullet("验收重点：有效反事实配对数、单模型对比的非劣/提升、H3≥100、长程终止≥25、长程严重失败≥10，以及真实 WebArena SR。"),
        bullet("当前 Codex 进程无法复用 VS Code 已建立的口令型 SSH 会话，因此没有伪造“本轮训练已启动/完成”的状态。"),
    ]

    story.append(PageBreak())
    story += section("6. 交付清单与下一步")
    story.append(
        table(
            [
                ["交付物", "位置 / 用途"],
                ["统一 GPU 流水线", "scripts/run_phase23_improvement.sh"],
                ["反事实 P0 手册", "COUNTERFACTUAL_P0_RUNBOOK.md"],
                ["人工复核工具", "scripts/export_human_review_queue.py / apply_human_review_labels.py"],
                ["多步真实轨迹评测", "scripts/evaluate_phase3_multistep.py"],
                ["AndroidWorld 手册", "ANDROIDWORLD_MIGRATION_RUNBOOK.md"],
                ["本地审计报告", "data/reports/phase2_human_review_queue.json / phase3_multistep_observed_cpu_latest.json"],
                ["在线进度看板", "agent-world-model-phase23-lzk.zhengkunlu4.chatgpt.site"],
                ["GitHub", "yilaxin/agent-world-model，分支 codex/phase2-world-model，PR #1"],
            ],
            [55 * mm, 119 * mm],
            row_colors=[PALE_BLUE] * 8,
        )
    )
    story += section("建议顺序")
    story += [
        bullet("1. 在已连接 GPU 终端运行统一脚本，并保留 data/reports/phase23_improvement_gpu.log。", GREEN),
        bullet("2. 完成 300 条人工复核队列中的高风险与 WebArena 项，再回写训练集。", GREEN),
        bullet("3. 对增强版模型执行固定种子 WebArena 重跑；若仍为 0%，先修代理策略，不用继续堆训练轮数。", AMBER),
        bullet("4. WebArena 稳定后再进入阶段四反馈遗憾闭环，并最后做 AndroidWorld 小规模迁移。", BLUE),
    ]
    story.append(Spacer(1, 5 * mm))
    story.append(p("最终判断", STYLES["h2"]))
    story.append(
        p(
            "阶段二、阶段三的工程链路已补齐到可复现、可审计和可继续训练的状态；历史 GPU 模型和离线阶段三决策具备较好指标。但反事实规模、H3/严重失败覆盖和真实 WebArena 成功率仍未通过严格验收，必须以新一轮服务器结果更新结论。",
            STYLES["callout"],
        )
    )

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    print(OUTPUT)


if __name__ == "__main__":
    build()
