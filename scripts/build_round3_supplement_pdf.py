#!/usr/bin/env python3
"""Build the round-3 P0 supplement PDF (2026-08-16)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "data" / "reports"
OUTPUT = ROOT / "output" / "pdf" / "大创第三轮补充报告_2026-08-16.pdf"

FONT_REGULAR = Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf")
FONT_SERIF = Path(r"C:\Windows\Fonts\NotoSerifSC-VF.ttf")

NAVY = colors.HexColor("#12324A")
BLUE = colors.HexColor("#1768A8")
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


def load_json(name: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def pct(value: float, digits: int = 2) -> str:
    return f"{value * 100:.{digits}f}%"


pdfmetrics.registerFont(TTFont("NotoSC", str(FONT_REGULAR)))
pdfmetrics.registerFont(TTFont("NotoSerifSC", str(FONT_SERIF)))

base = getSampleStyleSheet()
STYLES = {
    "h1": ParagraphStyle("h1", parent=base["Normal"], fontName="NotoSC", fontSize=15, leading=21, textColor=NAVY, spaceAfter=6),
    "h2": ParagraphStyle("h2", parent=base["Normal"], fontName="NotoSC", fontSize=11.5, leading=16, textColor=BLUE, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", parent=base["Normal"], fontName="NotoSC", fontSize=9.5, leading=14.5, textColor=INK),
    "small": ParagraphStyle("small", parent=base["Normal"], fontName="NotoSC", fontSize=8, leading=12, textColor=MUTED),
    "cell": ParagraphStyle("cell", parent=base["Normal"], fontName="NotoSC", fontSize=8.5, leading=12, textColor=INK),
    "cell_head": ParagraphStyle("cell_head", parent=base["Normal"], fontName="NotoSC", fontSize=8.5, leading=12, textColor=colors.white),
}


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLES[style])


def build() -> None:
    analysis = load_json("webarena_p0_round3_2x2_analysis.json")
    dev = load_json("webarena_p0_round3_dev_analysis.json")
    android = load_json("androidworld_task_eval_w4_round3_analysis.json")
    residual = load_json("phase3_multistep_residual_round3_gpu.json")
    holdout = json.loads((ROOT / "configs/webarena_p0_round3_holdout_frozen.json").read_text(encoding="utf-8"))

    cells = analysis["cell_metrics"]
    claim = analysis["relative_sr_plus_10_claim"]
    paired = analysis["paired_comparisons"]
    fx = analysis["factorial_effects"]

    dev_r = dev["metrics"]["reactive"]
    dev_w = dev["metrics"]["world-model"]
    android_o = android["overall"]
    residual_metrics = residual["metrics"]

    story = [
        p("天津大学大学生创新创业训练计划 · 创新训练项目", "small"),
        p("结合世界模型的 Agent 决策优化关键技术研究", "h1"),
        p("第三轮 P0 补充报告（策略改进、第三套未见集合 2×2 与迁移/安全收尾）", "h2"),
        p("证据截止：2026-08-16 · 数据与结论均来自本项目本地归档与冻结发布", "small"),
        Spacer(1, 6),
        p(
            "本补充报告按项目《优先级路线图》执行：先完成需要 GPU 的 P0 冲刺与多步动力学对照，"
            "再完成不需要 GPU 的轨迹诊断、AndroidWorld 迁移扩展与安全部署加固；论文撰写按负责人要求暂缓。"
        ),
    ]

    story.append(p("一、第三套未见集合冻结", "h2"))
    story.append(p(
        "第三套 holdout 在任何 episode 前冻结（frozen_before_any_holdout_episode=true），"
        "冻结哈希 %s；W4 发布指纹 %s。"
        % (holdout["freeze_sha256"][:16], holdout["release"]["sha256"][:16])
    ))
    story.append(p(
        "任务构成：GitLab 30 + Reddit 18 + Shopping 30 = 78 个唯一未见任务，四单元共 312 episodes。"
        "Reddit 池被前几轮耗尽（round-1/2 holdout、round-2/3 dev 已占用），且排除需外部 "
        "OPENAI_API_KEY 的 fuzzy_match 评测任务后仅剩 18 个合格任务；因此本套为 78 题而非 90 题，"
        "已如实记录。开发门槛（W4 可判定集 28 集、成功 2 集）通过后冻结。"
    ))

    story.append(p("二、第三套 holdout 2×2 在线结果", "h2"))
    cell_rows = [
        [p("单元格", "cell_head"), p("成功/总数", "cell_head"), p("成功率", "cell_head"), p("平均步数", "cell_head"), p("动作执行率", "cell_head")],
        [p("Reactive / 护栏关", "cell"), p("3/78", "cell"), p(pct(cells["reactive_guard_off"]["success_rate"]), "cell"),
         p(f"{cells['reactive_guard_off']['average_steps']:.2f}", "cell"), p(pct(cells["reactive_guard_off"]["action_execution_rate"]), "cell")],
        [p("Reactive / 护栏开", "cell"), p("3/78", "cell"), p(pct(cells["reactive_guard_on"]["success_rate"]), "cell"),
         p(f"{cells['reactive_guard_on']['average_steps']:.2f}", "cell"), p(pct(cells["reactive_guard_on"]["action_execution_rate"]), "cell")],
        [p("W4 / 护栏关", "cell"), p("2/78", "cell"), p(pct(cells["w4_guard_off"]["success_rate"]), "cell"),
         p(f"{cells['w4_guard_off']['average_steps']:.2f}", "cell"), p(pct(cells["w4_guard_off"]["action_execution_rate"]), "cell")],
        [p("W4 / 护栏开", "cell"), p("4/78", "cell"), p(pct(cells["w4_guard_on"]["success_rate"]), "cell"),
         p(f"{cells['w4_guard_on']['average_steps']:.2f}", "cell"), p(pct(cells["w4_guard_on"]["action_execution_rate"]), "cell")],
    ]
    table = Table(cell_rows, colWidths=[42 * mm, 28 * mm, 28 * mm, 28 * mm, 32 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_BLUE]),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(table)
    story.append(Spacer(1, 5))
    story.append(p(
        "成功任务明细：Reactive 关/开均为 Shopping 517、435、432；W4 关为 Shopping 435、432"
        "（丢失 517）；W4 开为 GitLab 807 + Shopping 517、435、432。"
    ))

    story.append(p("三、配对因果与 +10% 目标判定", "h2"))
    story.append(p(
        "世界模型效应（护栏关）：%.2f pp，配对 95%% CI [%.2f, %.2f]（W4 丢失任务 517）；"
        "世界模型效应（护栏开）：+%.2f pp，配对 95%% CI [%.2f, %.2f]（W4 新增 GitLab 807）。"
        % (
            paired["world_model_effect_guard_off"]["absolute_improvement_points"],
            paired["world_model_effect_guard_off"]["absolute_improvement_95ci_points"][0],
            paired["world_model_effect_guard_off"]["absolute_improvement_95ci_points"][1],
            paired["world_model_effect_guard_on"]["absolute_improvement_points"],
            paired["world_model_effect_guard_on"]["absolute_improvement_95ci_points"][0],
            paired["world_model_effect_guard_on"]["absolute_improvement_95ci_points"][1],
        )
    ))
    story.append(p(
        "护栏主效应：Reactive 0.00 pp；W4 +%.2f pp（CI [%.2f, %.2f]）。"
        "世界模型主效应（跨护栏平均）：%.2f pp（CI [%.2f, %.2f]）；"
        "世界模型 × 护栏交互：+%.2f pp（CI [%.2f, %.2f]）。"
        % (
            paired["guard_effect_world_model"]["absolute_improvement_points"],
            paired["guard_effect_world_model"]["absolute_improvement_95ci_points"][0],
            paired["guard_effect_world_model"]["absolute_improvement_95ci_points"][1],
            fx["world_model_main_effect_average_across_guard_levels"]["effect_points"],
            fx["world_model_main_effect_average_across_guard_levels"]["effect_95ci_points"][0],
            fx["world_model_main_effect_average_across_guard_levels"]["effect_95ci_points"][1],
            fx["world_model_by_guard_interaction_difference_in_differences"]["effect_points"],
            fx["world_model_by_guard_interaction_difference_in_differences"]["effect_95ci_points"][0],
            fx["world_model_by_guard_interaction_difference_in_differences"]["effect_95ci_points"][1],
        )
    ))
    claim_color = GREEN if claim["point_estimate_meets_target"] else RED
    story.append(p(
        "主对比（W4/护栏开 − Reactive/护栏开）：绝对 +%.2f pp，相对提升 %s；"
        "point_estimate_meets_target=%s，claim_allowed_from_frozen_holdout=%s。"
        % (
            claim["absolute_improvement_points"],
            pct(claim["relative_improvement"]),
            claim["point_estimate_meets_target"],
            claim["claim_allowed_from_frozen_holdout"],
        ),
    ))
    story.append(p(
        "诚实边界：达标由 1 个额外成功（GitLab 807，W4 4 步完成 merge request 提交、"
        "Reactive 同题 12 步失败）支撑，配对 95% CI 下界为 0；跨护栏的世界模型主效应仍为 0，"
        "护栏开增益被护栏关丢失 517 抵消。结论表述为“点估计达标、证据有限”，不夸大。",
    ))

    story.append(p("四、开发集与策略改进（护栏开）", "h2"))
    story.append(p(
        "第三轮开发集 30 题（与全部历史任务零重叠）：Reactive %d/%d（%.1f%%）、W4 %d/%d（%.1f%%），"
        "配对差 0 绝对 pp；2 题（GitLab 168、Shopping 313）因 fuzzy_match 评测需外部 API 而阻塞，"
        "不计入分母。策略改进使 Shopping 从 round-2 holdout 全零提升到开发集 2 个真实成功"
        "（118 搜索流程、516 加心愿单）。改进版本：v1 产品搜索/加购与完成信号终止、v2 短语提取与"
        "循环恢复前置、v3 修复 “in a subreddit” 解析为论坛名 a、v4 搜索提交动作护栏保护（W4 Shopping 118 恢复）。"
        % (dev_r["successes"], dev_r["episodes"], 100 * dev_r["success_rate"],
           dev_w["successes"], dev_w["episodes"], 100 * dev_w["success_rate"])
    ))

    story.append(p("五、AndroidWorld 迁移扩展（P1，CPU/模拟器）", "h2"))
    story.append(p(
        "W4 从 7 任务 × 1 episode 扩展到 7 任务 × 5 episode = 35 集，统一重置 + ADB 系统状态判读："
        "总体 %d/%d = %.1f%%，Wilson 95%% CI [%.1f%%, %.1f%%]。wifi_on/wifi_off 各 4/5、"
        "open_chrome/open_gmail 各 5/5；动作执行率 100%%。迁移检查证据增强，但仍非统计充分的跨平台证明。"
        % (
            android_o["successes"], android_o["episodes"], 100 * android_o["success_rate"],
            100 * android_o["wilson_95ci"][0], 100 * android_o["wilson_95ci"][1],
        )
    ))

    story.append(p("六、多步动力学修正（P1，GPU）", "h2"))
    story.append(p(
        "加入 persistence 与 learned-delta 双对照：learned-delta（一步残差 MLP，验证 MSE 3.04e-05）"
        "H3 MSE 6.7e-05，约为 persistence（2.08e-04）的 1/3。残差动力学世界模型重训后"
        "H1 4.5e-05 优于 persistence 9.5e-05；H2/H3 漂移较发布版减半但仍高于 persistence，"
        "“H2/H3 不劣于 persistence”门槛未达成，如实记录为负结果；learned-delta 累积是当前最稳候选。"
    ))

    story.append(p("七、安全部署加固（P2）", "h2"))
    story.append(p(
        "推理服务新增可选 TLS（证书/私钥）、客户端 IP 白名单、每 IP 令牌桶限流与异常脱敏"
        "（完整错误仅服务端记录），默认 127.0.0.1 绑定与 2 MB 请求体限制保留；含 3 项限流单测。"
    ))

    story.append(p("八、证据索引", "h2"))
    for label, path in [
        ("第三套 2×2 分析", "data/reports/webarena_p0_round3_2x2_analysis.json"),
        ("第三套冻结清单", "configs/webarena_p0_round3_holdout_frozen.json"),
        ("开发集分析", "data/reports/webarena_p0_round3_dev_analysis.json"),
        ("AndroidWorld 扩展", "data/reports/androidworld_task_eval_w4_round3_analysis.json"),
        ("多步动力学残差评测", "data/reports/phase3_multistep_residual_round3_gpu.json"),
        ("round-2 轨迹诊断", "data/reports/webarena_p0_round2_failure_diagnosis.json"),
    ]:
        story.append(p(f"• {label}：{path}", "small"))
    story.append(Spacer(1, 4))
    story.append(p(
        "报告生成：%s（Asia/Shanghai）" % datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M"),
        "small",
    ))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="大创第三轮补充报告",
    )
    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    build()
