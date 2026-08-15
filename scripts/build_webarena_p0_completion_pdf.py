#!/usr/bin/env python3
"""Build the evidence-backed WebArena P0 holdout completion report."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
ANALYSIS = REPORTS / "webarena_p0_2x2_analysis.json"
FREEZE = ROOT / "configs" / "webarena_p0_holdout_frozen.json"
EVIDENCE_MANIFEST = ROOT / "data" / "trajectories_webarena_p0_evidence" / "manifest.json"
OUTPUT = ROOT / "output" / "pdf" / "WebArena_P0未见任务2x2验收报告_2026-08-14.pdf"

FONT_REGULAR = Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")
FONT_SERIF = Path(r"C:\Windows\Fonts\NotoSerifSC-VF.ttf")

NAVY = colors.HexColor("#12324A")
BLUE = colors.HexColor("#1768A8")
TEAL = colors.HexColor("#087A67")
AMBER = colors.HexColor("#A15C00")
RED = colors.HexColor("#A93B32")
INK = colors.HexColor("#202A33")
MUTED = colors.HexColor("#64717D")
LINE = colors.HexColor("#CDD6DE")
PALE_BLUE = colors.HexColor("#EAF4FB")
PALE_TEAL = colors.HexColor("#E8F6F2")
PALE_AMBER = colors.HexColor("#FFF4DF")
PALE_RED = colors.HexColor("#FBECEA")
PALE_GRAY = colors.HexColor("#F3F5F7")


pdfmetrics.registerFont(TTFont("NotoSC", str(FONT_REGULAR)))
pdfmetrics.registerFont(TTFont("NotoSerifSC", str(FONT_SERIF)))
BASE = getSampleStyleSheet()
STYLES = {
    "cover_title": ParagraphStyle(
        "cover_title", parent=BASE["Title"], fontName="NotoSerifSC",
        fontSize=25, leading=36, textColor=NAVY, alignment=TA_CENTER,
        spaceAfter=5 * mm,
    ),
    "cover_subtitle": ParagraphStyle(
        "cover_subtitle", parent=BASE["BodyText"], fontName="NotoSC",
        fontSize=11.5, leading=19, textColor=BLUE, alignment=TA_CENTER,
        spaceAfter=7 * mm,
    ),
    "title": ParagraphStyle(
        "title", parent=BASE["Title"], fontName="NotoSerifSC",
        fontSize=19, leading=28, textColor=NAVY, spaceAfter=3 * mm,
    ),
    "h1": ParagraphStyle(
        "h1", parent=BASE["Heading1"], fontName="NotoSerifSC",
        fontSize=14, leading=21, textColor=BLUE,
        spaceBefore=2 * mm, spaceAfter=2.5 * mm,
    ),
    "h2": ParagraphStyle(
        "h2", parent=BASE["Heading2"], fontName="NotoSC",
        fontSize=10.8, leading=17, textColor=NAVY,
        spaceBefore=2 * mm, spaceAfter=2 * mm,
    ),
    "body": ParagraphStyle(
        "body", parent=BASE["BodyText"], fontName="NotoSC",
        fontSize=9.2, leading=16, textColor=INK, spaceAfter=2 * mm,
    ),
    "small": ParagraphStyle(
        "small", parent=BASE["BodyText"], fontName="NotoSC",
        fontSize=7.2, leading=11, textColor=MUTED, spaceAfter=1.2 * mm,
    ),
}


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLES[style])


def bullet(text: str, tone=INK) -> Paragraph:
    style = ParagraphStyle(
        "bullet", parent=STYLES["body"], textColor=tone,
        leftIndent=5 * mm, firstLineIndent=-3.5 * mm, spaceAfter=1.4 * mm,
    )
    return Paragraph(f"• {text}", style)


def callout(text: str, tone: str = "info") -> Table:
    palettes = {
        "info": (PALE_BLUE, BLUE),
        "ok": (PALE_TEAL, TEAL),
        "warn": (PALE_AMBER, AMBER),
        "risk": (PALE_RED, RED),
    }
    fill, accent = palettes[tone]
    content = Paragraph(text, STYLES["body"])
    table = Table([[content]], colWidths=[177 * mm], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), fill),
        ("BOX", (0, 0), (-1, -1), 0.8, accent),
        ("LINEBEFORE", (0, 0), (0, -1), 3.0, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def make_table(rows, widths, *, font_size=7.2, fills=None, center_cols=()):
    cell = ParagraphStyle(
        f"cell_{font_size}", parent=STYLES["body"],
        fontSize=font_size, leading=font_size * 1.52, spaceAfter=0,
    )
    header = ParagraphStyle(
        f"header_{font_size}", parent=cell, textColor=colors.white,
        alignment=TA_CENTER,
    )
    formatted = [
        [Paragraph(str(value), header if index == 0 else cell) for value in row]
        for index, row in enumerate(rows)
    ]
    table = Table(formatted, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for col in center_cols:
        commands.append(("ALIGN", (col, 1), (col, -1), "CENTER"))
    for index, fill in enumerate(fills or [], start=1):
        if fill is not None:
            commands.append(("BACKGROUND", (0, index), (-1, index), fill))
    table.setStyle(TableStyle(commands))
    return table


def pct(value: float, digits: int = 1) -> str:
    return f"{100.0 * value:.{digits}f}%"


def points(value: float) -> str:
    return f"{value:+.2f} pp"


def interval(values: list[float]) -> str:
    return f"[{values[0]:+.2f}, {values[1]:+.2f}] pp"


def draw_page(c: canvas.Canvas, doc) -> None:
    c.saveState()
    width, height = A4
    if doc.page > 1:
        c.setFillColor(NAVY)
        c.rect(0, height - 9 * mm, width, 9 * mm, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("NotoSC", 7.4)
        c.drawString(16 * mm, height - 5.7 * mm, "WebArena P0 未见任务 2×2 验收")
        c.drawRightString(width - 16 * mm, height - 5.7 * mm, "真实在线实验 · 不改写负结果")
    c.setFillColor(MUTED)
    c.setFont("NotoSC", 7.3)
    c.drawString(16 * mm, 8 * mm, "证据截止：2026-08-14 · Classic WebArena 冻结 90 题 holdout")
    c.drawRightString(width - 16 * mm, 8 * mm, f"第 {doc.page} 页")
    c.restoreState()


def build() -> Path:
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    archive = json.loads(EVIDENCE_MANIFEST.read_text(encoding="utf-8"))
    claim = analysis["relative_sr_plus_10_claim"]
    cells = analysis["cell_metrics"]
    comparisons = analysis["paired_comparisons"]
    factorial = analysis["factorial_effects"]

    if analysis["evaluator_failures"]:
        raise ValueError("P0 analysis still contains unresolved evaluator failures")
    if analysis["commonly_judged_unique_tasks"] != 90:
        raise ValueError("P0 report requires the complete frozen 90-task holdout")
    if archive["episode_count"] != 360:
        raise ValueError("P0 report requires 360 archived episode trajectories")

    story = []
    story += [
        Spacer(1, 27 * mm),
        p("大学生创新创业训练计划 · P0 专项验收", "cover_subtitle"),
        p("WebArena 未见任务<br/>2×2 在线因果实验报告", "cover_title"),
        p("Reactive / W4 × 导航护栏开 / 关<br/>3 站 × 30 题 × 4 单元 = 360 episodes", "cover_subtitle"),
        Spacer(1, 8 * mm),
        callout(
            "<b>验收结论：</b>P0 的冻结 holdout、等预算 2×2 在线运行、配对分析和 360 条轨迹归档均已完成；但是四个单元的成功率均为 0/90。W4 相对 Reactive 的绝对提升为 0.00 个百分点，基线为 0 使相对提升不可定义，因此<b>相对 SR +10% 性能目标未达成</b>。",
            "risk",
        ),
        Spacer(1, 12 * mm),
        make_table(
            [
                ["P0 子任务", "完成状态", "性能判定"],
                ["未见 WebArena holdout", "完成：3 站、每站 30 题", "在线能力未达标"],
                ["隔离世界模型因果贡献", "完成：2×2 + 配对 CI", "未观察到贡献"],
                ["冲刺相对 SR +10%", "实验完成", "目标未达成"],
            ],
            [62 * mm, 61 * mm, 54 * mm],
            fills=[PALE_TEAL, PALE_TEAL, PALE_RED], center_cols=(1, 2),
        ),
        Spacer(1, 14 * mm),
        p(f"报告生成：{datetime.now().strftime('%Y-%m-%d %H:%M')}（Asia/Shanghai）", "small"),
        PageBreak(),
    ]

    story += [
        p("一、实验设计与冻结完整性", "title"),
        callout(
            "<b>核心边界：</b>这是修复前冻结、未使用任务反馈的 90 题三站 holdout；它比早期 9 题 post-fix 回归更能衡量未见任务表现，但仍不是完整 812 题 WebArena benchmark。",
            "info",
        ),
        Spacer(1, 4 * mm),
        make_table(
            [
                ["设计项", "冻结值", "验收意义"],
                ["站点与任务", "GitLab / Reddit / Shopping；30 题/站", "覆盖三类真实在线站点"],
                ["实验单元", "Reactive/W4 × 护栏关/开", "拆分世界模型与共享护栏效应"],
                ["预算", "seed 0；每题最多 12 步", "四单元严格同预算配对"],
                ["总规模", "90 个唯一任务；360 episodes", "满足 P0 最低验收设计"],
                ["冻结时点", freeze["frozen_at_utc"], "首次 holdout episode 前冻结"],
                ["反馈规则", "task_feedback_used=false", "无同题修复、替换或调参"],
            ],
            [45 * mm, 66 * mm, 66 * mm], fills=[PALE_GRAY] * 6,
        ),
        p("不可变性证明", "h1"),
        bullet(f"任务冻结 SHA-256：<font name='NotoSC'>{analysis['freeze_sha256']}</font>。"),
        bullet(f"Agent 发布指纹：<font name='NotoSC'>{analysis['release_fingerprint_sha256']}</font>。"),
        bullet("W4 四单元均核对远程健康证明；护栏标签与单元一致，semantic goal override=false。"),
        bullet("冻结后未更改任务、模型权重、规则护栏、评测器或步数预算；中断/重叠运行被移出正式证据。"),
        p("外部模糊判分器的确定性处理", "h1"),
        bullet(
            f"官方 fuzzy-match evaluator 需要外部 API 密钥；本次共有 {len(analysis['deterministic_failure_adjudications'])} 个“任务×单元”缺少该密钥。"
        ),
        bullet("原始运行在 reset 阶段被密钥检查阻断；随后使用最小恢复适配器重新真实执行：只把“尚未提交答案”的校验短路为非终止 0 分，若提交答案则仍委托原官方 evaluator。"),
        bullet("28 条恢复轨迹均非空、完成真实决策且没有 send_msg；因此不读取参考答案、不模拟 LLM judge，按确定性失败计 0。原始异常、恢复规则与轨迹哈希全部保留。"),
        bullet("分析结束后 unresolved evaluator failures=0，90 个任务在四单元中均有一致判定。"),
        PageBreak(),
    ]

    labels = {
        "reactive_guard_off": "Reactive / 护栏关",
        "reactive_guard_on": "Reactive / 护栏开",
        "w4_guard_off": "W4 / 护栏关",
        "w4_guard_on": "W4 / 护栏开",
    }
    story += [
        p("二、四单元在线关键数据", "title"),
        make_table(
            [["单元", "成功", "SR (95% Wilson CI)", "动作执行率", "平均步数", "平均延迟"]] + [
                [
                    labels[key],
                    f"{value['successes']}/{value['episodes']}",
                    f"{pct(value['success_rate'])} ({pct(value['success_rate_95ci_wilson'][0])}-{pct(value['success_rate_95ci_wilson'][1])})",
                    pct(value["action_execution_rate"]),
                    f"{value['average_steps']:.2f}",
                    f"{value['average_latency_seconds']:.2f} s",
                ]
                for key, value in cells.items()
            ],
            [37 * mm, 21 * mm, 42 * mm, 29 * mm, 23 * mm, 25 * mm],
            font_size=6.8, fills=[PALE_RED] * 4, center_cols=(1, 2, 3, 4, 5),
        ),
        Spacer(1, 4 * mm),
        callout(
            "<b>性能判读：</b>四单元点估计均为 0%，单个 90 题单元的 95% Wilson 上界约为 4.1%。结果不是“尚未统计清楚”，而是在本次冻结范围内没有观察到任何成功；同时，0% 基线造成明显地板效应，限制了对较小方法差异的识别。",
            "risk",
        ),
        p("分站点结果", "h1"),
        make_table(
            [["站点", "Reactive/关", "W4/关", "Reactive/开", "W4/开"]] + [
                [site] + [
                    f"{analysis['per_site_metrics'][site][cell]['successes']}/{analysis['per_site_metrics'][site][cell]['episodes']}"
                    for cell in ["reactive_guard_off", "w4_guard_off", "reactive_guard_on", "w4_guard_on"]
                ]
                for site in analysis["sites"]
            ],
            [45 * mm, 33 * mm, 33 * mm, 33 * mm, 33 * mm],
            fills=[PALE_RED] * 3, center_cols=(1, 2, 3, 4),
        ),
        p("与早期三站 9 题回归的关系", "h1"),
        bullet("早期 9 题 post-fix 回归中 Reactive 与 W4 均为 9/9；该结果使用了同题失败反馈修复后的共享导航规则，只证明回归链路。"),
        bullet("本次 90 题未见集合在冻结后没有使用任务反馈，四单元均为 0/90。二者的巨大落差表明早期 9/9 不能外推为泛化能力。"),
        bullet("不同任务集合之间不做显著性检验；对比用于解释证据层级，不把差异简单归因为某一个代码改动。"),
        PageBreak(),
    ]

    wm_off = comparisons["world_model_effect_guard_off"]
    wm_on = comparisons["world_model_effect_guard_on"]
    guard_r = comparisons["guard_effect_reactive"]
    guard_w = comparisons["guard_effect_world_model"]
    story += [
        p("三、配对因果分析", "title"),
        p("90 个任务按站点、task id 和 seed 一一配对；差值置信区间使用 20,000 次任务级配对 bootstrap。护栏效应只归因于共享导航规则；只有同一护栏水平下的 W4-Reactive 差值用于估计世界模型贡献。", "body"),
        make_table(
            [
                ["配对对比", "基线 SR", "候选 SR", "绝对差", "95% 配对 CI", "仅候选成功"],
                ["W4-Reactive（护栏关）", pct(wm_off["baseline_success_rate"]), pct(wm_off["candidate_success_rate"]), points(wm_off["absolute_improvement_points"]), interval(wm_off["absolute_improvement_95ci_points"]), wm_off["candidate_only_success"]],
                ["W4-Reactive（护栏开）", pct(wm_on["baseline_success_rate"]), pct(wm_on["candidate_success_rate"]), points(wm_on["absolute_improvement_points"]), interval(wm_on["absolute_improvement_95ci_points"]), wm_on["candidate_only_success"]],
                ["护栏开-关（Reactive）", pct(guard_r["baseline_success_rate"]), pct(guard_r["candidate_success_rate"]), points(guard_r["absolute_improvement_points"]), interval(guard_r["absolute_improvement_95ci_points"]), guard_r["candidate_only_success"]],
                ["护栏开-关（W4）", pct(guard_w["baseline_success_rate"]), pct(guard_w["candidate_success_rate"]), points(guard_w["absolute_improvement_points"]), interval(guard_w["absolute_improvement_95ci_points"]), guard_w["candidate_only_success"]],
            ],
            [45 * mm, 23 * mm, 23 * mm, 25 * mm, 38 * mm, 23 * mm],
            font_size=6.7, fills=[PALE_RED] * 4, center_cols=(1, 2, 3, 4, 5),
        ),
        p("2×2 主效应与交互", "h1"),
        make_table(
            [["效应", "点估计", "95% CI"]] + [
                [
                    label,
                    points(factorial[key]["effect_points"]),
                    interval(factorial[key]["effect_95ci_points"]),
                ]
                for label, key in [
                    ("世界模型主效应（跨护栏平均）", "world_model_main_effect_average_across_guard_levels"),
                    ("护栏主效应（跨 Agent 平均）", "guard_main_effect_average_across_agent_modes"),
                    ("世界模型×护栏交互", "world_model_by_guard_interaction_difference_in_differences"),
                ]
            ],
            [83 * mm, 38 * mm, 56 * mm], fills=[PALE_RED] * 3, center_cols=(1, 2),
        ),
        Spacer(1, 4 * mm),
        callout(
            "<b>因果结论：</b>在本次冻结 holdout 与预算下，W4、导航护栏以及两者交互的成功率效应点估计均为 0.00 个百分点。不能声称世界模型带来在线成功率收益；全零结局还意味着该 2×2 设计虽执行完整，却处于地板区，无法回答模型在“已有基础成功能力”条件下是否能改善边缘任务。",
            "warn",
        ),
        PageBreak(),
    ]

    story += [
        p("四、P0 验收、完成好坏与遗留问题", "title"),
        make_table(
            [
                ["验收项", "设计完成度", "结果质量", "最终判定"],
                ["未见 WebArena holdout", "90/90 题；360/360 episodes", "冻结与证据链完整；SR=0%", "实验完成，能力不足"],
                ["隔离世界模型贡献", "2×2、同预算、配对 CI 完成", "主效应=0 pp；存在地板效应", "因果流程完成，无正向证据"],
                ["相对 SR +10%", "按预注册主对比评估", "Reactive=0%，相对值不可定义", "性能目标未达成"],
            ],
            [43 * mm, 50 * mm, 51 * mm, 33 * mm],
            font_size=6.8, fills=[PALE_AMBER, PALE_AMBER, PALE_RED],
        ),
        p("完成得好的部分", "h1"),
        bullet("修复前冻结 90 题，明确排除全部历史使用任务；不因结果差而替换题目。", TEAL),
        bullet("同一任务四单元配对、步数预算一致，W4 发布指纹与护栏状态可验证。", TEAL),
        bullet("正式与中断/重叠运行隔离；最终分析只白名单引用 360 条轨迹并核验 SHA-256。", TEAL),
        bullet("负结果、相对提升不可定义和外部判分依赖均透明呈现。", TEAL),
        p("完成不足与研究遗留", "h1"),
        bullet("Agent 没有在 90 个未见任务中完成任何一个任务；核心在线能力严重不足。", RED),
        bullet("规则候选与目标理解不足以覆盖真实任务，世界模型只能重排既有候选，无法补偿候选空间缺失。", RED),
        bullet("全零基线导致地板效应；下一轮应先把 Reactive 基线提升到非零，再复用冻结协议评估 W4 增量。", AMBER),
        bullet("当前结论只适用于 Classic WebArena 三站 90 题，不代表完整 812 题，也不覆盖其他站点。", AMBER),
        p("建议下一步", "h1"),
        make_table(
            [
                ["优先级", "工作", "最低验收", "GPU"],
                ["P0", "提升基础策略与候选生成", "新的开发集上形成非零 SR；不可触碰本次 holdout", "训练/推理需要"],
                ["P0", "重新冻结第二套未见集合", "修复完成后再冻结；报告绝对 pp、相对值与配对 CI", "推理需要"],
                ["P1", "错误类型诊断", "对 360 轨迹统计目标理解、候选缺失、执行失败与循环", "不需要"],
                ["P1", "完整 benchmark 扩展", "先做分层功效分析，再扩展站点与多种子", "推理建议"],
            ],
            [20 * mm, 52 * mm, 80 * mm, 25 * mm],
            font_size=6.7, fills=[PALE_RED, PALE_RED, PALE_AMBER, PALE_AMBER], center_cols=(0, 3),
        ),
        PageBreak(),
    ]

    story += [
        p("五、证据索引与可复核性", "title"),
        make_table(
            [
                ["证据", "路径 / 数量"],
                ["冻结主清单", "configs/webarena_p0_holdout_frozen.json"],
                ["冻结站点配置", "configs/webarena_p0_holdout_{gitlab,reddit,shopping}_frozen.json"],
                ["四单元分析", "data/reports/webarena_p0_2x2_analysis.json"],
                ["原始单元报告", "data/reports/webarena_p0_<site>_<mode>_guard_<state>.json（12 份）"],
                ["恢复单元报告", "data/reports/webarena_p0_recovery_<site>_<mode>_guard_<state>.json（12 份）"],
                ["清洁轨迹归档", "data/trajectories_webarena_p0_evidence/（360 条 + manifest.json）"],
                ["运行器", "scripts/run_webarena_p0_cell.sh（同站互斥锁、冻结校验、服务重建）"],
                ["恢复适配器", "scripts/recover_webarena_p0_fuzzy_episodes.py（只短路无答案校验）"],
                ["分析器", "scripts/analyze_webarena_p0_2x2.py（Wilson CI、配对 bootstrap、2×2 效应）"],
            ],
            [48 * mm, 129 * mm], fills=[PALE_GRAY] * 9,
        ),
        p("关键证据摘要", "h1"),
        bullet(f"分析任务数：{analysis['commonly_judged_unique_tasks']}；分析 episodes：{analysis['judged_total_episodes_in_analysis']}。"),
        bullet(f"清洁归档 episodes：{archive['episode_count']}；源分析 SHA-256：{archive['analysis_sha256']}。"),
        bullet(f"冻结清单 SHA-256：{analysis['freeze_sha256']}。"),
        bullet(f"W4 发布指纹：{analysis['release_fingerprint_sha256']}。"),
        Spacer(1, 4 * mm),
        callout(
            "<b>最终科研表述：</b>本项目已完成 P0 预定的 90 题三站未见任务和 2×2 因果评估，解决了“没有未见在线集合、无法区分护栏与世界模型”的证据缺口；结果显示四单元均为 0% SR，W4 没有可观察在线增益，申报书相对 SR +10% 指标未达成。P0 应记为“实验与证据交付完成，性能目标失败”。",
            "risk",
        ),
    ]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=16 * mm, bottomMargin=14 * mm,
        title="WebArena P0 未见任务 2×2 验收报告",
        author="项目组",
        subject="结合世界模型的 Agent 决策优化关键技术研究",
    )
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    return OUTPUT


if __name__ == "__main__":
    print(build())
