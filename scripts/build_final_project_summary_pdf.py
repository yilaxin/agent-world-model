#!/usr/bin/env python3
"""Build the proposal-aligned final project summary PDF.

The report separates offline prediction/ranking evidence, the early three-site
post-fix regression, and the later frozen 90-task P0 unseen holdout.
"""

from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
OUTPUT = ROOT / "output" / "pdf" / "大创项目完整总结与结题评估_2026-08-15.pdf"

FONT_REGULAR = Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")
FONT_SERIF = Path(r"C:\Windows\Fonts\NotoSerifSC-VF.ttf")

NAVY = colors.HexColor("#12324A")
BLUE = colors.HexColor("#1768A8")
CYAN = colors.HexColor("#0E9FB1")
GREEN = colors.HexColor("#087A67")
AMBER = colors.HexColor("#A15C00")
RED = colors.HexColor("#A93B32")
INK = colors.HexColor("#202A33")
MUTED = colors.HexColor("#64717D")
LINE = colors.HexColor("#CDD6DE")
PALE_BLUE = colors.HexColor("#EAF4FB")
PALE_GREEN = colors.HexColor("#E8F6F2")
PALE_AMBER = colors.HexColor("#FFF4DF")
PALE_RED = colors.HexColor("#FBECEA")
PALE_GRAY = colors.HexColor("#F3F5F7")


def load_json(name: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pct(value: float, digits: int = 2) -> str:
    return f"{value * 100:.{digits}f}%"


pdfmetrics.registerFont(TTFont("NotoSC", str(FONT_REGULAR)))
pdfmetrics.registerFont(TTFont("NotoSerifSC", str(FONT_SERIF)))

base = getSampleStyleSheet()
STYLES = {
    "cover_kicker": ParagraphStyle(
        "cover_kicker", parent=base["Normal"], fontName="NotoSC", fontSize=10,
        leading=15, textColor=CYAN, alignment=TA_CENTER, spaceAfter=4 * mm,
    ),
    "cover_title": ParagraphStyle(
        "cover_title", parent=base["Title"], fontName="NotoSerifSC", fontSize=25,
        leading=37, textColor=NAVY, alignment=TA_CENTER, spaceAfter=4 * mm,
    ),
    "cover_subtitle": ParagraphStyle(
        "cover_subtitle", parent=base["BodyText"], fontName="NotoSC", fontSize=12,
        leading=20, textColor=BLUE, alignment=TA_CENTER, spaceAfter=8 * mm,
    ),
    "title": ParagraphStyle(
        "title", parent=base["Title"], fontName="NotoSerifSC", fontSize=22,
        leading=31, textColor=NAVY, alignment=TA_LEFT, spaceAfter=4 * mm,
    ),
    "lead": ParagraphStyle(
        "lead", parent=base["BodyText"], fontName="NotoSC", fontSize=10.2,
        leading=18, textColor=INK, spaceAfter=4 * mm,
    ),
    "h1": ParagraphStyle(
        "h1", parent=base["Heading1"], fontName="NotoSerifSC", fontSize=15,
        leading=22, textColor=BLUE, spaceBefore=2 * mm, spaceAfter=3 * mm,
    ),
    "h2": ParagraphStyle(
        "h2", parent=base["Heading2"], fontName="NotoSC", fontSize=11,
        leading=17, textColor=NAVY, spaceBefore=2 * mm, spaceAfter=2 * mm,
    ),
    "body": ParagraphStyle(
        "body", parent=base["BodyText"], fontName="NotoSC", fontSize=9.2,
        leading=16, textColor=INK, spaceAfter=2.2 * mm,
    ),
    "small": ParagraphStyle(
        "small", parent=base["BodyText"], fontName="NotoSC", fontSize=7.5,
        leading=12, textColor=MUTED, spaceAfter=1.5 * mm,
    ),
    "table_header": ParagraphStyle(
        "table_header", parent=base["BodyText"], fontName="NotoSC", fontSize=7.4,
        leading=11, textColor=colors.white, alignment=TA_CENTER,
    ),
    "table_cell": ParagraphStyle(
        "table_cell", parent=base["BodyText"], fontName="NotoSC", fontSize=7.3,
        leading=11.3, textColor=INK,
    ),
    "table_cell_small": ParagraphStyle(
        "table_cell_small", parent=base["BodyText"], fontName="NotoSC", fontSize=6.7,
        leading=10.2, textColor=INK,
    ),
}


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLES[style])


def bullet(text: str, tone=INK) -> Paragraph:
    style = ParagraphStyle(
        "bullet_local", parent=STYLES["body"], textColor=tone,
        leftIndent=5 * mm, firstLineIndent=-3.4 * mm, spaceAfter=1.5 * mm,
    )
    return Paragraph(f"• {text}", style)


def callout(text: str, tone: str = "info") -> Table:
    palette = {
        "info": (PALE_BLUE, BLUE),
        "ok": (PALE_GREEN, GREEN),
        "warn": (PALE_AMBER, AMBER),
        "risk": (PALE_RED, RED),
    }
    fill, accent = palette[tone]
    style = ParagraphStyle(
        f"callout_{tone}", parent=STYLES["body"], fontSize=9.4, leading=16,
        textColor=INK, spaceAfter=0,
    )
    t = Table([[Paragraph(text, style)]], colWidths=[177 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("BOX", (0, 0), (-1, -1), 0.8, accent),
        ("LINEBEFORE", (0, 0), (0, -1), 3.0, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def make_table(rows, widths, *, font_size: float = 7.3, row_fills=None, center_cols=()):
    cell_style = ParagraphStyle(
        f"table_cell_{font_size}", parent=STYLES["table_cell"], fontSize=font_size,
        leading=font_size * 1.55,
    )
    header_style = ParagraphStyle(
        f"table_header_{font_size}", parent=STYLES["table_header"], fontSize=font_size,
        leading=font_size * 1.45,
    )
    formatted = []
    for idx, row in enumerate(rows):
        style = header_style if idx == 0 else cell_style
        formatted.append([Paragraph(str(cell), style) for cell in row])
    table = Table(formatted, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for col in center_cols:
        commands.append(("ALIGN", (col, 1), (col, -1), "CENTER"))
    if row_fills:
        for row_idx, fill in enumerate(row_fills, start=1):
            if fill is not None:
                commands.append(("BACKGROUND", (0, row_idx), (-1, row_idx), fill))
    table.setStyle(TableStyle(commands))
    return table


def section_title(title: str, subtitle: str) -> list[Flowable]:
    return [p(title, "title"), p(subtitle, "lead")]


def draw_page(c: canvas.Canvas, doc) -> None:
    c.saveState()
    width, height = A4
    if doc.page > 1:
        c.setFillColor(NAVY)
        c.rect(0, height - 9 * mm, width, 9 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("NotoSC", 7.5)
        c.drawString(16 * mm, height - 5.7 * mm, "结合世界模型的 Agent 决策优化关键技术研究")
        c.drawRightString(width - 16 * mm, height - 5.7 * mm, "项目完整总结与结题评估")
    c.setFillColor(MUTED)
    c.setFont("NotoSC", 7.5)
    c.drawString(16 * mm, 8 * mm, "证据截止：2026-08-15 · 数据与结论均来自本项目本地归档")
    c.drawRightString(width - 16 * mm, 8 * mm, f"第 {doc.page} 页")
    c.restoreState()


def build() -> Path:
    dataset_card = load_json("phase2_evidence_review_dataset_card.json")
    cf = load_json("phase2_counterfactual_collection_p2.json")
    p2 = load_json("phase2_p2_multiseed_ensemble_gpu.json")
    structure = load_json("phase3_structure_alignment_gpu.json")
    ranking = load_json("phase3_counterfactual_ranking_p2_gpu.json")
    multistep = load_json("phase3_multistep_observed_p2_gpu.json")
    planner = load_json("phase3_evaluation_ensemble_gpu.json")
    candidate = load_json("candidate_generator_ablation_gpu.json")
    phase3_online = load_json("webarena_phase3_online_evaluation_gpu.json")
    phase4 = load_json("phase4_feedback_experiment_gpu.json")
    web = load_json("webarena_online_evaluation_w4.json")
    p0_first = load_json("webarena_p0_2x2_analysis.json")
    p0 = load_json("webarena_p0_round2_2x2_analysis.json")
    p0_analysis_sha256 = file_sha256(REPORTS / "webarena_p0_round2_2x2_analysis.json")
    wm_off = p0["paired_comparisons"]["world_model_effect_guard_off"]
    wm_on = p0["paired_comparisons"]["world_model_effect_guard_on"]
    guard_main = p0["factorial_effects"]["guard_main_effect_average_across_agent_modes"]
    interaction = p0["factorial_effects"]["world_model_by_guard_interaction_difference_in_differences"]
    android = load_json("androidworld_task_eval_final.json")
    android_w4 = load_json("androidworld_task_eval_w4.json")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    story: list[Flowable] = []

    # Cover: editorial report treatment.
    story += [
        Spacer(1, 28 * mm),
        p("天津大学大学生创新创业训练计划 · 创新训练项目", "cover_kicker"),
        p("结合世界模型的 Agent 决策优化<br/>关键技术研究", "cover_title"),
        p("项目完整总结、完成度评估与遗留问题审计", "cover_subtitle"),
        Spacer(1, 10 * mm),
        make_table(
            [
                ["项目信息", "内容"],
                ["负责人", "卢政坤"],
                ["指导教师", "吴华明 教授"],
                ["申报实施期", "2026 年 5 月 - 2027 年 5 月"],
                ["本次证据截止", "2026 年 8 月 15 日"],
                ["主要平台", "WebArena（主实验） / AndroidWorld（少量迁移）"],
            ],
            [42 * mm, 135 * mm], font_size=8.5, row_fills=[PALE_GRAY, None, PALE_GRAY, None, PALE_GRAY],
        ),
        Spacer(1, 8 * mm),
        callout(
            "<b>结题判断：</b>四阶段技术闭环与研究原型已基本形成，并完成两套三站 90 题冻结未见 holdout；第二套主验收的 Reactive/W4 在护栏关时均为 1/90、护栏开时均为 2/90。世界模型主效应为 0.00 个百分点，申报书核心指标“WebArena 相对反应式基线成功率提升 10% 以上”未达成。因此项目可评价为<b>技术与实验交付基本完成、证据链较强、核心在线性能目标失败</b>。",
            "warn",
        ),
        Spacer(1, 19 * mm),
        p("本报告不把离线指标等同于在线成功率，不把同题修复后的 9 题回归等同于泛化；P0 未见结果与负结论均按原始证据呈现。", "small"),
        PageBreak(),
    ]

    # Executive summary.
    story += section_title("执行摘要", "先给结论，再解释证据。")
    story += [
        callout(
            "<b>完成质量：</b>研究方法、工程链路与 P0 在线因果实验完成度高；在线性能差。当前成果最适合表述为“完成世界模型 Agent 原型、多层离线验证与冻结未见在线评估”，不适合表述为“世界模型提升了完整 WebArena 成功率”。",
            "info",
        ),
        Spacer(1, 4 * mm),
        make_table(
            [
                ["维度", "结论", "证据", "评价"],
                ["研究实施", "四阶段均有代码、配置、模型和报告", "状态表征、世界模型、规划、反馈模块齐备", "好"],
                ["离线模型", "预测、校准、排序与风险门禁通过", "P2 测试 12/12；W4 发布门禁通过", "好"],
                ["在线链路", "三站 evaluator-backed 流程已打通", "90 题 × 4 单元 = 360 episodes", "好"],
                ["在线效果", "第二套 P0 为 1/90、2/90、1/90、2/90", "两种护栏条件下 W4-Reactive 均为 0 pp", "未达目标"],
                ["泛化性", "完成冻结三站未见 holdout", "90 题；仍非完整 812 题", "有限"],
                ["移动端迁移", "完成少量真实检查", "主检查双方 91.4%；W4 5/7", "有限"],
                ["成果形态", "源代码和多份实验报告已形成；论文仅为初稿", "仓库、JSON、轨迹与报告齐备", "部分完成"],
            ],
            [29 * mm, 55 * mm, 66 * mm, 27 * mm],
            row_fills=[PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_RED, PALE_AMBER, PALE_AMBER, PALE_AMBER],
            center_cols=(3,),
        ),
        Spacer(1, 4 * mm),
        p("最关键的三条判断", "h2"),
        bullet("离线预测/校准/反事实排序/有限步轨迹漂移回答的是“模型在已记录分布上的预测与排序质量”，不能替代完整 WebArena 在线任务成功率。"),
        bullet("早期三站 9 题 post-fix regression 使用同题失败反馈修复，只证明链路；本次 P0 在修复前冻结 90 个历史未使用任务，不再把两者混为一谈。"),
        bullet("第二套 P0 中 W4 与 Reactive 逐题成功结果完全相同：护栏关均 1/90、护栏开均 2/90；世界模型主效应与交互效应均为 0 个百分点，未满足相对 SR +10%。"),
        PageBreak(),
    ]

    # Proposal goals.
    story += section_title("一、申报书目标与实际完成矩阵", "以《大创申报书 33.0》的研究目标、阶段安排与预期成果为唯一验收基线。")
    story += [
        make_table(
            [
                ["申报目标", "实际完成", "关键证据", "状态"],
                ["统一状态表征与动作条件世界模型", "完成 AXTree/DOM/任务/历史融合、512 维状态编码和动作条件多任务预测", "13,348 转移；P2 测试状态 F1 98.69%、任务 F1 98.90%", "已完成"],
                ["动态任务-界面结构对齐", "完成 8 维结构特征与学习式对齐器", "Top-1 63.9%→82.9%；错配率 36.1%→17.1%", "已完成"],
                ["多时间尺度与置信度感知排序", "完成 W0-W3、H=1/2/3、集成不确定性与安全降级", "515/515 状态匹配；有限步合规 100%", "已完成"],
                ["决策后悔驱动反馈优化", "完成预测误差、regret、rank flip、stall、结构错配优先回灌与消融", "反馈池 9,388；7 个训练策略/消融 + 保守发布", "已完成（离线）"],
                ["WebArena 相对 SR +10%", "完成第二套三站 90 题冻结 P0 2×2；W4 与 Reactive 成功率相同", "护栏关/开 W4-Reactive 均为 0 pp、相对提升均为 0%", "未完成"],
                ["AndroidWorld 少量迁移", "完成 7 任务真实迁移检查", "主检查 reactive/phase3 均 91.4%；W4 5/7", "已完成（小样本）"],
            ],
            [46 * mm, 69 * mm, 45 * mm, 17 * mm],
            font_size=6.9,
            row_fills=[PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_RED, PALE_AMBER],
            center_cols=(3,),
        ),
        Spacer(1, 4 * mm),
        callout(
            "<b>进度解释：</b>申报书实施期为 2026 年 5 月至 2027 年 5 月，而本报告证据截止为 2026 年 8 月 15 日。当前在时间上属于提前完成大量工程任务；但结题质量仍应按“承诺是否被证据支持”判断，而不能因为进度提前而降低在线主指标要求。",
            "info",
        ),
        p("预期成果完成度", "h2"),
        make_table(
            [
                ["申报成果", "当前形态", "评价"],
                ["研究报告 1 篇", "阶段一至阶段四报告、补强报告及本完整总结已形成", "已完成"],
                ["论文发表 1 篇", "已形成 PHASE3_PAPER_DRAFT.md，但无投稿/录用/发表证据", "未完成"],
                ["源代码与实验报告 1 套", "核心源码、配置、模型清单、160 份可解析 JSON 报告和在线轨迹均在本地仓库", "已完成"],
            ],
            [45 * mm, 105 * mm, 27 * mm], row_fills=[PALE_GREEN, PALE_RED, PALE_GREEN], center_cols=(2,),
        ),
        PageBreak(),
    ]

    # Phase 1.
    story += section_title("二、阶段一：环境、基线与统一状态原型", "完成文献与环境准备，建立可重复的真实交互和状态记录入口。")
    story += [
        p("完成内容", "h1"),
        bullet("搭建轻量 BrowserGym/WebArena 环境，完成反应式 Agent、轨迹 JSONL、DOM/Accessibility Tree 抽取与任务相关剪枝。"),
        bullet("将任务、URL、标签页、AXTree、DOM 与最近 5 步动作编码为 512 维确定性状态表示。"),
        bullet("完成 input、scroll、click、back 动作链；MiniWoB click-test 与 WebArena 27 环境烟雾均 1 步成功。"),
        make_table(
            [
                ["关键数据", "结果", "含义"],
                ["MiniWoB click-test", "奖励 1.0，1 步终止", "动作/轨迹/评测链路通过"],
                ["WebArena 27 环境烟雾", "奖励 1.0，1 步终止", "真实环境与 evaluator 可用"],
                ["状态维度", "512", "轻量 CPU 编码，无需 GPU"],
                ["阶段报告", "all_passed=true", "阶段一工程门禁通过"],
            ],
            [46 * mm, 48 * mm, 83 * mm], row_fills=[PALE_GREEN, PALE_GREEN, PALE_BLUE, PALE_GREEN],
        ),
        Spacer(1, 4 * mm),
        callout(
            "<b>质量判断：</b>阶段一作为后续数据入口完成良好；但固定成功用例属于环境烟雾，不是通用 WebArena 能力。截图像素未进入最终轻量状态编码，严格意义上的“截图+DOM 多模态融合”实现仍弱于申报书设想。",
            "warn",
        ),
        PageBreak(),
    ]

    # Phase 2.
    story += section_title("三、阶段二：动作条件世界模型与多次训练", "从早期 P1 数据扩展到 P2 数据，完成五次多种子 GPU 训练、校准和独立测试。")
    test = p2["ensemble_test"]
    story += [
        p("最终数据规模", "h1"),
        make_table(
            [
                ["指标", "最终值", "质量控制"],
                ["状态转移 / episode / 任务", f"{dataset_card['transition_count']:,} / {dataset_card['episode_count']:,} / {dataset_card['task_count']}", "按 episode 切分"],
                ["Train / Validation / Test", "9,388 / 2,017 / 1,943", "无 episode 泄漏"],
                ["观察反事实", f"{cf['valid_pairs']:,} 对有效；{cf['informative_pairs']:,} 对有信息", f"信息率 {pct(cf['informative_pair_rate'])}"],
                ["采集失败 / 状态匹配", f"{cf['failed_pairs']} / {pct(cf['pair_state_match_rate'])}", "仅使用环境观测结果"],
                ["反事实严重失败正例", f"{cf['counterfactual_severe_failure_positives']:,}", "风险覆盖补强"],
            ],
            [54 * mm, 65 * mm, 58 * mm], row_fills=[PALE_BLUE, PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_GREEN],
        ),
        p("五次训练与模型选择", "h1"),
        make_table(
            [["训练标签", "Seed", "最佳 Epoch", "验证 Pairwise", "测试 Risk F1", "测试 Progress MAE"]] + [
                [
                    run["tag"], run["seed"], run["best_epoch"],
                    pct(run["validation"]["pairwise_accuracy"]),
                    pct(run["test"]["risk_f1"]),
                    f"{run['test']['progress_mae']:.4f}",
                ] for run in p2["runs"]
            ],
            [41 * mm, 16 * mm, 25 * mm, 32 * mm, 29 * mm, 34 * mm],
            font_size=6.8, row_fills=[PALE_BLUE, PALE_BLUE, PALE_BLUE, None, None], center_cols=(1, 2, 3, 4, 5),
        ),
        Spacer(1, 3 * mm),
        p("仅依据验证集选择 seed 29、73、17 作为三个成员；成员权重为 0.2 / 0.8 / 0.0。风险校准 ECE 由 0.03454 降至 0.01103，测试集在选择结束后独立评估。", "body"),
        p("最终独立测试", "h1"),
        make_table(
            [
                ["状态变化 F1", "任务信号 F1", "风险 F1", "风险 AUROC", "进度 MAE", "奖励 MAE", "风险 ECE"],
                [pct(test["state_delta_f1"]), pct(test["task_signal_f1"]), pct(test["risk_f1"]), pct(test["risk_auroc"]), f"{test['progress_mae']:.4f}", f"{test['reward_mae']:.4f}", f"{test['risk_ece']:.5f}"],
            ],
            [25 * mm] * 7, font_size=6.7, row_fills=[PALE_GREEN], center_cols=tuple(range(7)),
        ),
        Spacer(1, 4 * mm),
        callout(
            "<b>阶段二结论：</b>五次多种子训练、验证集选型、概率校准和 12 项独立测试门禁全部通过，阶段二完成质量好。其指标仍是离线世界模型质量，不等于 WebArena 在线成功率。",
            "ok",
        ),
        PageBreak(),
    ]

    # Phase 3.
    s0 = structure["baseline"]["test"]
    s1 = structure["selected_test"]
    rank_test = ranking["results"]["test"]
    story += section_title("四、阶段三：结构对齐、反事实排序与有限步推演", "围绕“选什么动作、推演多远、何时相信模型”完成前瞻决策模块。")
    story += [
        p("动态结构对齐", "h1"),
        make_table(
            [
                ["测试指标", "规则基线", "学习模型", "变化"],
                ["Top-1", pct(s0["target_recall_at_1"], 1), pct(s1["target_recall_at_1"], 1), "+19.0 个百分点"],
                ["Recall@3", pct(s0["target_recall_at_3"], 1), pct(s1["target_recall_at_3"], 1), "持平"],
                ["MRR", f"{s0['mrr']:.4f}", f"{s1['mrr']:.4f}", "+0.0898"],
                ["结构错配率", pct(s0["structure_mismatch_rate"], 1), pct(s1["structure_mismatch_rate"], 1), "-19.0 个百分点"],
            ],
            [47 * mm, 39 * mm, 39 * mm, 52 * mm], row_fills=[PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_GREEN], center_cols=(1, 2, 3),
        ),
        p("观察反事实排序", "h1"),
        make_table(
            [
                ["方法", "观察配对", "有效配对", "Pairwise", "NDCG@2", "平均后悔"],
                ["最佳单模型", rank_test["selected_single"]["observed_pair_count"], rank_test["selected_single"]["informative_pair_count"], pct(rank_test["selected_single"]["pairwise_accuracy"]), f"{rank_test['selected_single']['ndcg_at_2']:.4f}", f"{rank_test['selected_single']['mean_decision_regret']:.4f}"],
                ["校准集成", rank_test["calibrated_ensemble"]["observed_pair_count"], rank_test["calibrated_ensemble"]["informative_pair_count"], pct(rank_test["calibrated_ensemble"]["pairwise_accuracy"]), f"{rank_test['calibrated_ensemble']['ndcg_at_2']:.4f}", f"{rank_test['calibrated_ensemble']['mean_decision_regret']:.4f}"],
            ],
            [38 * mm, 28 * mm, 28 * mm, 30 * mm, 25 * mm, 28 * mm], row_fills=[PALE_BLUE, PALE_GREEN], center_cols=(1, 2, 3, 4, 5),
        ),
        p("集成没有提高 Pairwise Accuracy，但把平均后悔从 0.0638 降至 0.0511；配对准确率差的 95% CI 为 [-1.01%, 1.01%]。", "body"),
        p("真实连续轨迹 H=1/2/3", "h1"),
        make_table(
            [["视野", "窗口数", "Latent MSE", "Cosine", "Persistence MSE", "Progress MAE"]] + [
                [h, m["window_count"], f"{m['latent_mse']:.6f}", f"{m['latent_cosine_similarity']:.4f}", f"{m['persistence_baseline_mse']:.6f}", f"{m['progress_mae']:.4f}"]
                for h, m in multistep["metrics"].items()
            ],
            [22 * mm, 27 * mm, 33 * mm, 27 * mm, 39 * mm, 29 * mm], row_fills=[PALE_GREEN, PALE_AMBER, PALE_AMBER], center_cols=(0, 1, 2, 3, 4, 5),
        ),
        Spacer(1, 3 * mm),
        callout(
            "<b>重要负结果：</b>H=1/2/3 的 latent MSE 均差于简单 persistence baseline，且 H 越深漂移越明显。预设覆盖门禁虽然通过，但这表明多步潜在动力学尚未形成相对持久性基线的预测优势。W3 因此采用置信度自适应视野，而不是固定 H=3。",
            "warn",
        ),
        PageBreak(),
    ]

    methods = planner["metrics"]["methods"]
    story += section_title("五、阶段三：决策阶梯、候选生成与首次在线贯通", "离线动作一致性是诊断指标；真实在线成功率另行报告。")
    story += [
        p("B0/W0-W3 离线决策阶梯", "h1"),
        make_table(
            [["方法", "总体动作一致率", "成功动作一致率", "危险动作规避率"]] + [
                [label, pct(methods[key]["recorded_action_agreement"], 1), pct(methods[key]["positive_recorded_action_agreement"], 1), pct(methods[key]["risky_recorded_action_diversion"], 1)]
                for label, key in [("B0 reactive", "reactive"), ("W0 one-step", "w0_one_step"), ("W1 structure", "w1_structure"), ("W2 multiscale", "w2_multiscale"), ("W3 adaptive", "phase3")]
            ],
            [48 * mm, 43 * mm, 43 * mm, 43 * mm], row_fills=[PALE_GRAY, PALE_BLUE, PALE_BLUE, PALE_AMBER, PALE_BLUE], center_cols=(1, 2, 3),
        ),
        Spacer(1, 3 * mm),
        p("W3 在 515/515 样本上实现状态匹配、候选合法、安全动作 Recall@K、解释完整和有限步合规均 100%；平均置信度 0.690，推理平均/P95 为 20.59/64.03 ms。", "body"),
        p("候选生成消融", "h1"),
        make_table(
            [
                ["生成器", "严格 JSON", "候选合法", "记录动作 Recall@K", "平均候选数", "延迟"],
                ["规则生成", pct(candidate["metrics"]["rules"]["strict_json_success_rate"]), pct(candidate["metrics"]["rules"]["candidate_schema_valid_rate"]), pct(candidate["metrics"]["rules"]["recorded_action_recall_at_k"]), f"{candidate['metrics']['rules']['average_candidate_count']:.2f}", f"{candidate['metrics']['rules']['latency_ms_mean']:.2f} ms"],
                ["本地 Qwen2.5-3B", pct(candidate["metrics"]["local_llm"]["strict_json_success_rate"]), pct(candidate["metrics"]["local_llm"]["candidate_schema_valid_rate"]), pct(candidate["metrics"]["local_llm"]["recorded_action_recall_at_k"]), f"{candidate['metrics']['local_llm']['average_candidate_count']:.2f}", f"{candidate['metrics']['local_llm']['latency_ms_mean']:.2f} ms"],
            ],
            [39 * mm, 28 * mm, 28 * mm, 38 * mm, 23 * mm, 21 * mm], row_fills=[PALE_GREEN, PALE_AMBER], center_cols=(1, 2, 3, 4, 5),
        ),
        p("首次真实 WebArena 在线贯通", "h1"),
        make_table(
            [
                ["范围", "成功", "动作执行率", "平均步数", "结论"],
                ["Reddit 任务 27-31，seed 0", f"{phase3_online['world_model_agent_metrics']['successes']}/{phase3_online['world_model_agent_metrics']['episodes']}", pct(phase3_online["world_model_agent_metrics"]["action_execution_rate"]), f"{phase3_online['world_model_agent_metrics']['average_steps']:.1f}", "链路打通，能力未达标"],
            ],
            [53 * mm, 26 * mm, 31 * mm, 28 * mm, 39 * mm], row_fills=[PALE_RED], center_cols=(1, 2, 3),
        ),
        Spacer(1, 4 * mm),
        callout("<b>阶段三结论：</b>结构对齐、有限步排序和置信度降级完成良好；候选 LLM 不优于规则，且首次在线成功率为 0/5。阶段三没有证明在线增益。", "warn"),
        PageBreak(),
    ]

    # Phase 4.
    fsum = phase4["feedback_pool"]["summary"]
    story += section_title("六、阶段四：反馈优化、消融与 W4 发布", "困难样本来自真实环境转移与已记录任务信号；离线重训练采用等预算对比。")
    story += [
        p("反馈池", "h1"),
        make_table(
            [
                ["反馈类型", "数量/均值", "解释"],
                ["样本 / 完整动作对", f"{fsum['example_count']:,} / {fsum['complete_observed_pair_count']:,}", "困难样本池规模"],
                ["预测误差", f"均值 {fsum['prediction_error']['mean']:.5f}；P95 {fsum['prediction_error']['p95']:.5f}", "状态与任务信号偏差"],
                ["决策后悔", f"均值 {fsum['regret']['mean']:.5f}；正例 {fsum['regret']['positive_count']:,}", "影响候选排序的损失"],
                ["Rank flip", f"{fsum['rank_flip']['positive_count']}", "极稀少，消融解释需谨慎"],
                ["Stall", f"{fsum['stall']['positive_count']:,}", "任务停滞"],
                ["结构错误", f"{fsum['struct_error']['positive_count']:,}", "任务-控件错配"],
            ],
            [48 * mm, 61 * mm, 68 * mm], row_fills=[PALE_BLUE, None, None, PALE_AMBER, None, None],
        ),
        p("主实验与消融（验证集）", "h1"),
        make_table(
            [["策略", "MSE", "Pairwise", "Regret", "Risk ECE"]] + [
                [v["name"].replace("priority_", "no-"), f"{v['validation']['latent_mse']:.6f}", pct(v["validation"]["pairwise_accuracy"]), f"{v['validation']['mean_decision_regret']:.5f}", f"{v['validation']['risk_ece']:.5f}"]
                for v in phase4["variants"]
            ],
            [48 * mm, 31 * mm, 33 * mm, 33 * mm, 32 * mm],
            font_size=6.9, row_fills=[PALE_BLUE, None, PALE_GREEN, None, None, PALE_GREEN, PALE_AMBER], center_cols=(1, 2, 3, 4),
        ),
        Spacer(1, 3 * mm),
        p("Priority 在排序上最好，但其 MSE 退化，不能直接发布。最终选择满足非退化门槛的最大 W4 比例：来源级 50% W3 + 50% priority W4，并在验证集校准六成员权重与温度。", "body"),
        p("发布 W4 独立测试", "h1"),
        make_table(
            [
                ["MSE", "Cosine", "Progress MAE", "Reward MAE", "State F1", "Risk F1", "ECE", "Pairwise", "Regret"],
                [
                    f"{phase4['released_w4']['test']['latent_mse']:.6f}",
                    f"{phase4['released_w4']['test']['latent_cosine']:.6f}",
                    f"{phase4['released_w4']['test']['progress_mae']:.5f}",
                    f"{phase4['released_w4']['test']['reward_mae']:.5f}",
                    pct(phase4['released_w4']['test']['state_delta_f1']),
                    pct(phase4['released_w4']['test']['risk_f1']),
                    f"{phase4['released_w4']['test']['risk_ece']:.5f}",
                    pct(phase4['released_w4']['test']['pairwise_accuracy']),
                    f"{phase4['released_w4']['test']['mean_decision_regret']:.5f}",
                ],
            ],
            [19.5 * mm] * 9, font_size=6.0, row_fills=[PALE_GREEN], center_cols=tuple(range(9)),
        ),
        Spacer(1, 4 * mm),
        callout("<b>阶段四离线结论：</b>反馈优先级、等预算消融、保守发布和独立测试闭环完整，完成质量好；但 W4 只在离线门禁上成立，不能由此推导在线 SR 提升。", "ok"),
        PageBreak(),
    ]

    # WebArena.
    story += section_title("七、WebArena 三站在线结果与科研边界", "早期 9 题回归、第一套全零 holdout 与第二套主验收必须分层解释。")
    story += [
        callout(
            "<b>P0 最终结论：</b>第二套 90 个历史未使用任务在任何 episode 前冻结，完成 Reactive/W4 × 护栏开/关共 360 个已判定 episode。护栏关时 Reactive/W4 均为 1/90，护栏开时均为 2/90；两种条件下 W4 相对 Reactive 的绝对差均为 0.00 个百分点、相对提升均为 0%，+10% 目标未达成。",
            "risk",
        ),
        Spacer(1, 4 * mm),
        p("第二套冻结未见 2×2 主验收", "h1"),
        make_table(
            [
                ["单元", "成功", "SR", "95% Wilson CI", "平均步数", "动作执行率"],
                *[
                    [
                        label,
                        f"{p0['cell_metrics'][key]['successes']}/{p0['cell_metrics'][key]['episodes']}",
                        pct(p0['cell_metrics'][key]['success_rate']),
                        f"{pct(p0['cell_metrics'][key]['success_rate_95ci_wilson'][0], 1)}-{pct(p0['cell_metrics'][key]['success_rate_95ci_wilson'][1], 1)}",
                        f"{p0['cell_metrics'][key]['average_steps']:.2f}",
                        pct(p0['cell_metrics'][key]['action_execution_rate']),
                    ]
                    for label, key in [
                        ("Reactive / 护栏关", "reactive_guard_off"),
                        ("W4 / 护栏关", "w4_guard_off"),
                        ("Reactive / 护栏开", "reactive_guard_on"),
                        ("W4 / 护栏开", "w4_guard_on"),
                    ]
                ],
            ],
            [42 * mm, 22 * mm, 22 * mm, 35 * mm, 27 * mm, 29 * mm], row_fills=[PALE_RED] * 4, center_cols=(1, 2, 3, 4, 5),
        ),
        Spacer(1, 3 * mm),
        p("配对与因果归因", "h1"),
        make_table(
            [
                ["效应", "点估计", "95% 配对 bootstrap CI"],
                ["W4-Reactive（护栏关）", f"{wm_off['absolute_improvement_points']:.2f} pp", f"[{wm_off['absolute_improvement_95ci_points'][0]:.2f}, {wm_off['absolute_improvement_95ci_points'][1]:.2f}] pp"],
                ["W4-Reactive（护栏开）", f"{wm_on['absolute_improvement_points']:.2f} pp", f"[{wm_on['absolute_improvement_95ci_points'][0]:.2f}, {wm_on['absolute_improvement_95ci_points'][1]:.2f}] pp"],
                ["护栏主效应（跨 Agent 平均）", f"{guard_main['effect_points']:.2f} pp", f"[{guard_main['effect_95ci_points'][0]:.2f}, {guard_main['effect_95ci_points'][1]:.2f}] pp"],
                ["世界模型×护栏交互", f"{interaction['effect_points']:.2f} pp", f"[{interaction['effect_95ci_points'][0]:.2f}, {interaction['effect_95ci_points'][1]:.2f}] pp"],
            ],
            [77 * mm, 40 * mm, 60 * mm], row_fills=[PALE_RED] * 4, center_cols=(1, 2),
        ),
        bullet("任务冻结 SHA-256 与 W4 发布指纹均通过复核；每题 seed 0、最多 12 步，四单元同预算配对。"),
        bullet("12 个需模糊判分的冻结任务（Reddit 1、GitLab 2、Shopping 9）在四单元共 48 个 episode 因缺少外部 OPENAI_API_KEY 初始化失败，随后用冻结的无答案适配器重新真实执行；未提交答案时仅返回非终止 0 分，提交答案后仍调用原 evaluator，不读取参考答案。"),
        bullet("最终 12 个逐站报告均为 30/30，evaluator_failures 为空；Windows 归档的 433 个主运行、恢复与重试轨迹文件已逐文件对照 WSL 原件 SHA-256，0 个不匹配。"),
        callout("<b>低成功率边界：</b>第二套基线已非零，因此相对提升可以计算；但 W4 与 Reactive 的逐题成功结果完全相同，世界模型效应为 0。护栏共享效应为 +1.11 pp，95% CI [0.00, 3.33]，只对应 1 个额外成功且不能归因于世界模型。", "warn"),
        p("逐站成功数", "h1"),
        make_table(
            [
                ["站点", "Reactive/关", "Reactive/开", "W4/关", "W4/开"],
                *[
                    [
                        site,
                        f"{p0['per_site_metrics'][site]['reactive_guard_off']['successes']}/30",
                        f"{p0['per_site_metrics'][site]['reactive_guard_on']['successes']}/30",
                        f"{p0['per_site_metrics'][site]['w4_guard_off']['successes']}/30",
                        f"{p0['per_site_metrics'][site]['w4_guard_on']['successes']}/30",
                    ]
                    for site in ["gitlab", "reddit", "shopping"]
                ],
            ],
            [41 * mm, 34 * mm, 34 * mm, 34 * mm, 34 * mm],
            row_fills=[PALE_BLUE, PALE_BLUE, PALE_GRAY], center_cols=(1, 2, 3, 4),
        ),
        p("第一套 90 题 P0（历史对照）", "h1"),
        p(f"第一套三站 90 题的四单元均为 0/90；世界模型、共享护栏和交互效应均为 0 pp。该结果保留为独立负证据，不与第二套任务合并。分析文件记录了 {p0_first['judged_total_episodes_in_analysis']} 个已判定 episode。", "body"),
        p("早期 9 题 post-fix 回归（只作历史对照）", "h1"),
        make_table(
            [
                ["范围", "Reactive", "W4", "解释"],
                ["GitLab/Reddit/Shopping 共 9 题", f"{web['agent_metrics']['successes']}/{web['agent_metrics']['episodes']}", f"{web['world_model_agent_metrics']['successes']}/{web['world_model_agent_metrics']['episodes']}", "同题反馈修复后的链路回归，不是泛化"],
            ],
            [64 * mm, 25 * mm, 25 * mm, 63 * mm], row_fills=[PALE_AMBER], center_cols=(1, 2),
        ),
        Spacer(1, 5 * mm),
    ]

    # Android and engineering.
    story += section_title("八、AndroidWorld 少量迁移与工程质量", "移动端结果是迁移检查，不是统计充分的跨平台提升证明。")
    story += [
        p("AndroidWorld 任务级主检查", "h1"),
        make_table(
            [
                ["方法", "任务", "每任务 episode", "总体成功率", "动作执行率"],
                ["Reactive", "7", android["episodes_per_task"], pct(android["summary"]["reactive"]["success_rate"], 1), pct(android["summary"]["reactive"]["action_execution_rate"])],
                ["Phase3", "7", android["episodes_per_task"], pct(android["summary"]["phase3"]["success_rate"], 1), pct(android["summary"]["phase3"]["action_execution_rate"])],
                ["Released W4", "7", android_w4["episodes_per_task"], pct(android_w4["summary"]["released_w4"]["success_rate"], 1), pct(android_w4["summary"]["released_w4"]["action_execution_rate"])],
            ],
            [46 * mm, 27 * mm, 37 * mm, 38 * mm, 29 * mm], row_fills=[PALE_BLUE, PALE_BLUE, PALE_AMBER], center_cols=(1, 2, 3, 4),
        ),
        Spacer(1, 3 * mm),
        p("主检查中 reactive 与 phase3 均为 91.4%，没有方法增益；W4 的 5/7 仅为每题 1 个 episode，失败是 Wi-Fi 关闭与日历，不能做统计显著性解释。成功由 ADB 系统状态或任务判定器读取，不使用 LLM judge。", "body"),
        p("工程与可复现性", "h1"),
        make_table(
            [
                ["检查", "结果", "说明"],
                ["项目自身测试", "48 通过 / 13 跳过", "tests/ 与 3 个根测试文件；跳过均因本 WSL 环境未安装 PyTorch"],
                ["全目录 pytest", "第三方收集阻断", "MiniWoB 自带测试引用 Gymnasium 旧版 flatten_observation 路径"],
                ["JSON 报告解析", "160/160 有效", "本地报告目录逐一使用 Python JSON 解析"],
                ["WebArena P0 冻结/发布指纹", "均匹配", "任务、模型、护栏与预算未漂移"],
                ["WebArena round-2 归档", "360 个已判定 episode", "433 个主运行/恢复/重试原始文件逐项 SHA-256 一致"],
                ["Git diff whitespace", "通过", "无空白错误"],
            ],
            [51 * mm, 42 * mm, 84 * mm], row_fills=[PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_GREEN],
        ),
        p("安全与发布复核", "h1"),
        bullet("本地静态检查未发现硬编码 API key/token/password；模型权重加载使用 torch.load(..., weights_only=True)。"),
        bullet("推理服务默认只绑定 127.0.0.1，单请求体限制为 2 MB；但服务没有鉴权/TLS。若改为 0.0.0.0 或暴露到不可信网络，应增加认证、速率限制并关闭详细异常回显。"),
        bullet("远程 Agent endpoint 为命令行输入；生产部署应限制到受信任地址，避免把任务状态发送到非预期服务。"),
        bullet("Codex Security 正式桌面扫描控制接口本会话未暴露，因此本节是只读人工静态复核，不冒充正式 Codex Security 扫描报告。"),
        callout("<b>工程结论：</b>本项目的本地证据组织、实验配置与回归测试质量较好；主要安全风险集中在“未来若将本地推理服务公开部署”的边界，而非当前默认 localhost 使用。", "info"),
        Spacer(1, 5 * mm),
    ]

    # Remaining issues and roadmap.
    story += section_title("九、完成好坏评价、遗留问题与后续路线", "对项目价值的判断既包括已完成内容，也包括没有被证据支持的承诺。")
    story += [
        p("完成得好的部分", "h1"),
        bullet("从状态抽取、数据、世界模型、结构对齐、有限步规划到反馈回灌形成了可运行的四阶段工程闭环。"),
        bullet("数据切分、模型选择、校准、独立测试和等预算消融的研究流程较规范；负结果与限制有明确记录。"),
        bullet("第二套 WebArena 三站 90 题、360 episodes、evaluator、逐步轨迹和 SHA-256 证据链完整，解决了“没有非零基线未见集合和因果隔离”的缺陷。"),
        bullet("没有把早期 9 题回归包装成泛化，没有抹去第一套全零 P0，也没有把第二套共享护栏的 1 个额外成功归因于世界模型。"),
        p("完成不足的部分", "h1"),
        bullet("申报书核心在线指标未达成：第二套 P0 的 W4 与 reactive 在护栏关/开时分别同为 1/90 与 2/90，世界模型绝对与相对提升均为 0。", RED),
        bullet("第二套基础成功率仍只有 1.11%-2.22%，Shopping 四单元全零；候选生成、任务理解与动作纠错仍是首要能力瓶颈。", RED),
        bullet("完整 812 题没有执行；90 题证据只覆盖 GitLab、Reddit、Shopping 与 seed 0。", RED),
        bullet("多步 latent MSE 未优于 persistence baseline，说明动力学优势尚未被证明。", AMBER),
        bullet("AndroidWorld W4 只有 7 个 episode；论文只有初稿，没有投稿或发表证据。", AMBER),
        p("优先级路线图", "h1"),
        make_table(
            [
                ["优先级", "任务", "最低验收设计", "是否需要 GPU"],
                ["P0", "未见 WebArena holdout", "已完成：3 站×30 题×4 单元；360 episodes", "已完成"],
                ["P0", "隔离世界模型因果贡献", "已完成 2×2、护栏冻结与配对 CI；效应 0 pp", "已完成"],
                ["P0", "冲刺相对 SR +10%", "第二套实验完成但性能失败；先在新开发集提升策略，再冻结第三套集合", "需要 GPU"],
                ["P1", "360 轨迹错误诊断", "任务理解/定位/执行/循环/预算/evaluator 分型，形成可复核统计", "不需要"],
                ["P1", "修正多步动力学", "加入 persistence/learned-delta 对照；要求 H2/H3 至少不劣于 persistence", "训练需要 GPU"],
                ["P1", "扩大 AndroidWorld", "7 任务 × ≥5 episode × 多种子；统一重置与置信区间", "通常 CPU/本机模拟器"],
                ["P1", "论文完成", "以负结果和因果设计为主线重写；完成导师审阅、投稿或发表", "不需要"],
                ["P2", "安全部署加固", "鉴权、TLS/隧道、速率限制、异常脱敏、endpoint allowlist", "不需要"],
            ],
            [18 * mm, 44 * mm, 86 * mm, 29 * mm], font_size=6.7,
            row_fills=[PALE_RED, PALE_RED, PALE_RED, PALE_AMBER, PALE_AMBER, PALE_AMBER, PALE_BLUE], center_cols=(0, 3),
        ),
        Spacer(1, 4 * mm),
        callout(
            "<b>GPU 通知：</b>本次 round-2 P0 的 360 次在线推理已完成，报告编制、轨迹诊断与证据复核不再需要 GPU。下一次只有在提升基础策略、冻结第三套未见集合复验，或重新训练多步动力学时需要开启 GPU；开启前应先通知项目负责人。",
            "info",
        ),
        PageBreak(),
    ]

    # Final verdict and evidence index.
    story += section_title("十、最终结论与证据索引", "把“完成了什么”和“还没有证明什么”同时作为项目最终成果。")
    story += [
        callout(
            "<b>最终结论：</b>本项目已经完成申报书所设计的四阶段技术原型、三站真实链路，以及两套 90 题冻结未见 P0；第二套 2×2 中 W4 与 Reactive 在两种护栏条件下成功率完全相同，世界模型主效应为 0。因此完整项目不能评价为“全部达标”：WebArena 相对成功率 +10% 的核心效果目标失败，论文发表也未完成。建议结题表述为：<b>技术与实验交付完成良好，证据链完整，核心在线性能指标未达成。</b>",
            "warn",
        ),
        Spacer(1, 5 * mm),
        p("建议对外摘要", "h1"),
        p("项目构建了面向网页与移动端任务的世界模型 Agent 原型，完成统一状态表征、动作条件多任务预测、任务-界面结构对齐、置信度感知有限步规划和决策后悔驱动反馈优化。阶段二独立测试状态变化 F1 98.69%、任务信号 F1 98.90%、风险 F1 94.39%；阶段三观察反事实 Pairwise Accuracy 97.73%；阶段四 W4 测试 Pairwise Accuracy 97.47%、风险 ECE 0.00896。第二套 P0 在 GitLab、Reddit、Shopping 冻结 90 个未见任务，完成 Reactive/W4×护栏开/关共 360 episodes；护栏关两者均为 1/90，护栏开两者均为 2/90，世界模型效应为 0 个百分点，因此相对 SR +10% 未达成。AndroidWorld 结果仅用于少量迁移检查。", "body"),
        p("核心证据索引", "h1"),
        make_table(
            [
                ["证据", "路径"],
                ["阶段一", "PHASE1_COMPLETION_REPORT.md；data/reports/phase1_latest.json"],
                ["阶段二最终补强", "PHASE23_MULTIRUN_COMPLETION_REPORT.md；phase2_p2_multiseed_ensemble_gpu.json"],
                ["阶段三", "PHASE3_COMPLETION_REPORT.md；phase3_structure_alignment_gpu.json；phase3_counterfactual_ranking_p2_gpu.json；phase3_multistep_observed_p2_gpu.json"],
                ["阶段四", "PHASE4_COMPLETION_REPORT.md；phase4_feedback_experiment_gpu.json；artifacts/phase4/world_model_ensemble_w4.json"],
                ["WebArena 第一套 P0", "webarena_p0_2x2_analysis.json；data/trajectories_webarena_p0_evidence/"],
                ["WebArena 第二套 P0", f"webarena_p0_round2_2x2_analysis.json；webarena_p0_round2_consolidated_*.json；data/trajectories_webarena_p0_round2_*/<br/>分析文件 SHA-256：{p0_analysis_sha256}"],
                ["AndroidWorld", "androidworld_task_eval_final.json；androidworld_task_eval_w4.json"],
                ["申报书", "大创申报书 33.0.docx（项目名称、目标、进度、成果与 SR +10% 承诺）"],
            ],
            [44 * mm, 133 * mm], font_size=6.7,
            row_fills=[PALE_GRAY, None, PALE_GRAY, None, PALE_GRAY, None, PALE_GRAY],
        ),
        Spacer(1, 6 * mm),
        p(f"报告生成：{datetime.now().strftime('%Y-%m-%d %H:%M')}（Asia/Shanghai）", "small"),
    ]

    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=14 * mm,
        title="大创项目完整总结与结题评估",
        author="项目组",
        subject="结合世界模型的 Agent 决策优化关键技术研究",
    )
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return OUTPUT


if __name__ == "__main__":
    print(build())
