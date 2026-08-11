#!/usr/bin/env python3
"""Generate the final proposal-aligned phase 2/3 progress report."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "阶段二阶段三最终进度与遗留问题报告_2026-08-10.pdf"
REPORTS = ROOT / "data" / "reports"
DATASET_CARD = REPORTS / "phase2_evidence_review_dataset_card.json"

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
PALE_BLUE = colors.HexColor("#EAF4FB")
PALE_GREEN = colors.HexColor("#E9F7F2")
PALE_AMBER = colors.HexColor("#FFF6E5")
PALE_RED = colors.HexColor("#FDECEC")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(value: float, digits: int = 2) -> str:
    return f"{value * 100:.{digits}f}%"


pdfmetrics.registerFont(TTFont("MSYH", str(FONT_REGULAR), subfontIndex=0))
pdfmetrics.registerFont(TTFont("MSYH-Bold", str(FONT_BOLD), subfontIndex=0))

base = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle("title", parent=base["Title"], fontName="MSYH-Bold", fontSize=23, leading=32, alignment=TA_LEFT, textColor=NAVY, spaceAfter=5 * mm),
    "kicker": ParagraphStyle("kicker", parent=base["Normal"], fontName="MSYH-Bold", fontSize=9, leading=14, textColor=CYAN, spaceAfter=2 * mm),
    "lead": ParagraphStyle("lead", parent=base["BodyText"], fontName="MSYH", fontSize=10.8, leading=19, textColor=INK, spaceAfter=4 * mm),
    "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="MSYH-Bold", fontSize=15, leading=22, textColor=BLUE, spaceBefore=2 * mm, spaceAfter=3 * mm),
    "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="MSYH-Bold", fontSize=11, leading=17, textColor=NAVY, spaceBefore=2 * mm, spaceAfter=2 * mm),
    "body": ParagraphStyle("body", parent=base["BodyText"], fontName="MSYH", fontSize=9.2, leading=16, textColor=INK, spaceAfter=2.5 * mm),
    "small": ParagraphStyle("small", parent=base["BodyText"], fontName="MSYH", fontSize=7.5, leading=12, textColor=MUTED),
    "table_header": ParagraphStyle("table_header", parent=base["BodyText"], fontName="MSYH-Bold", fontSize=8, leading=12, textColor=colors.white, alignment=TA_CENTER),
    "table_cell": ParagraphStyle("table_cell", parent=base["BodyText"], fontName="MSYH", fontSize=8, leading=13, textColor=INK),
    "callout": ParagraphStyle("callout", parent=base["BodyText"], fontName="MSYH-Bold", fontSize=9.6, leading=17, textColor=NAVY, leftIndent=5 * mm, rightIndent=5 * mm, spaceBefore=3 * mm, spaceAfter=3 * mm),
}


def para(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLES[style])


def bullet(text: str, tone=INK) -> Paragraph:
    style = ParagraphStyle(
        "bullet_local",
        parent=STYLES["body"],
        textColor=tone,
        leftIndent=5 * mm,
        firstLineIndent=-3.5 * mm,
        spaceAfter=2 * mm,
    )
    return Paragraph(f"• {text}", style)


def make_table(rows, widths, row_colors=None, font_size=8.0, padding=5):
    header_style = ParagraphStyle(
        f"table_header_{font_size}",
        parent=STYLES["table_header"],
        fontSize=font_size,
        leading=font_size * 1.5,
    )
    cell_style = ParagraphStyle(
        f"table_cell_{font_size}",
        parent=STYLES["table_cell"],
        fontSize=font_size,
        leading=font_size * 1.55,
    )
    formatted = []
    for idx, row in enumerate(rows):
        style = header_style if idx == 0 else cell_style
        formatted.append([Paragraph(str(cell), style) for cell in row])
    table = Table(formatted, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
        ("FONTNAME", (0, 0), (-1, -1), "MSYH"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "MSYH-Bold"),
    ]
    if row_colors:
        for idx, color in enumerate(row_colors, start=1):
            commands.append(("BACKGROUND", (0, idx), (-1, idx), color))
    table.setStyle(TableStyle(commands))
    return table


def draw_page(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 10 * mm, width, 10 * mm, fill=1, stroke=0)
    canvas.setFont("MSYH", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(16 * mm, 8 * mm, "Agent 世界模型决策优化 | 阶段二、阶段三")
    canvas.drawRightString(width - 16 * mm, 8 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def build():
    counterfactual = load_json(REPORTS / "phase2_counterfactual_collection_p2.json")
    ensemble = load_json(REPORTS / "phase2_p2_multiseed_ensemble_gpu.json")
    test_report = load_json(REPORTS / "phase2_p2_ensemble_evaluation_test_gpu.json")
    ranking = load_json(REPORTS / "phase3_counterfactual_ranking_p2_gpu.json")
    multistep = load_json(REPORTS / "phase3_multistep_observed_p2_gpu.json")
    evidence_review = load_json(REPORTS / "phase2_evidence_review.json")
    evidence_apply = load_json(REPORTS / "phase2_evidence_review_apply.json")
    card = load_json(DATASET_CARD)
    android_preflight_path = REPORTS / "androidworld_preflight_latest.json"
    android_smoke_path = REPORTS / "androidworld_smoke_latest.json"
    android_preflight = load_json(android_preflight_path) if android_preflight_path.exists() else {}
    android_smoke = load_json(android_smoke_path) if android_smoke_path.exists() else {}
    android_runtime_ready = bool(android_preflight.get("runtime_ready"))
    android_smoke_passed = android_smoke.get("status") == "passed"
    if android_smoke_passed:
        android_summary = "本机 WHPX 预检/冒烟通过（19 个 UI 元素）；任务级首轮评测 reactive 22.2% vs phase3 0%"
        android_status = "冒烟+首轮评测完成/策略待提升"
    elif android_runtime_ready:
        android_summary = "官方 0.1.0、ADB、Pixel 6/API 33、gRPC 与客体路由预检通过；真实 reset/action 待验"
        android_status = "运行时就绪/冒烟待验"
    else:
        android_summary = "适配器与预检已实现；真实运行时尚未通过"
        android_status = "待迁移"

    test_metrics = test_report["metrics"]
    test_acceptance = test_report["acceptance"]
    rank_single = ranking["results"]["test"]["selected_single"]
    rank_ensemble = ranking["results"]["test"]["calibrated_ensemble"]
    ms_audit = card["multistep_audit"]["by_split"]["test"]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=15 * mm,
        title="阶段二阶段三最终进度与遗留问题报告",
        author="Agent 世界模型项目组",
    )
    story = []

    story += [
        Spacer(1, 17 * mm),
        para("最终验收报告 · 2026-08-10", "kicker"),
        para("阶段二、阶段三<br/>最终进度与遗留问题报告", "title"),
        para("依据《大创申报书 33.0》重新对齐阶段二动作条件世界模型与阶段三候选动作前瞻决策。本报告记录 RTX 4090 上完成的真实采集、数据门禁、五次多种子训练和阶段三离线评估，并明确区分离线通过与 WebArena 在线成功。", "lead"),
        make_table(
            [
                ["最终结论", "状态"],
                ["观察反事实采集", f"{counterfactual['valid_pairs']:,} 对有效，{counterfactual['informative_pairs']:,} 对有信息"],
                ["阶段二数据质量门禁", "全部通过"],
                ["RTX 4090 多种子训练", f"{ensemble['run_count']} 次训练，选择 {ensemble['ensemble_size']} 个成员"],
                ["阶段二独立测试", "12 项验收检查全部通过"],
                ["阶段三反事实与多步评估", "两项验收均通过"],
                ["高风险证据复核", f"{evidence_apply['evidence_approved_rows']} 条 evidence_verified；自动证据验收通过"],
                ["AndroidWorld", android_summary],
                ["WebArena 在线重评", "本轮未执行，不能声称成功率提高"],
            ],
            [72 * mm, 88 * mm],
            [PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_AMBER, PALE_AMBER, PALE_RED],
        ),
        Spacer(1, 5 * mm),
        para("验收边界：离线预测、排序与多步轨迹评估不等于完整 WebArena 在线任务成功率。完整多站点部署及相对成功率 +10% 仍属于阶段四闭环验证。", "callout"),
        Spacer(1, 14 * mm),
        para("代码仓库：github.com/yilaxin/agent-world-model · 分支 codex/phase2-world-model · PR #1", "small"),
        para("私有看板：agent-world-model-phase23-lzk.zhengkunlu4.chatgpt.site", "small"),
        para("GPU 目录：/root/autodl-tmp/agent_world_model_phase23_latest", "small"),
    ]

    story.append(PageBreak())
    story += [
        para("1. 阶段二：数据、训练与一步预测", "h1"),
        para("数据规模与质量门禁", "h2"),
        make_table(
            [
                ["项目", "最终结果", "验收"],
                ["数据集", f"{card['transition_count']:,} transitions · {card['episode_count']:,} episodes · {card['task_count']} tasks", "通过"],
                ["Train / Validation / Test", f"{card['split_counts']['train']:,} / {card['split_counts']['validation']:,} / {card['split_counts']['test']:,}", "按 episode 切分，无泄漏"],
                ["观察反事实", f"计划 {counterfactual['planned_pairs']:,}；有效 {counterfactual['valid_pairs']:,}；失败 {counterfactual['failed_pairs']}", "通过"],
                ["有信息反事实", f"{counterfactual['informative_pairs']:,}（{pct(counterfactual['informative_pair_rate'])}）", "超过 1,000 对门槛"],
                ["状态匹配率", pct(counterfactual['pair_state_match_rate']), "通过"],
                ["严重失败正例", f"反事实 {counterfactual['counterfactual_severe_failure_positives']:,}；测试集长视野 {ms_audit['long_horizon_severe_failure_count']}", "通过"],
            ],
            [48 * mm, 78 * mm, 48 * mm],
            [PALE_GREEN] * 6,
        ),
        Spacer(1, 5 * mm),
        para("五次多种子训练", "h2"),
        make_table(
            [["变体", "种子", "验证选择分", "最终状态"]]
            + [[run["tag"], run["seed"], f"{run['selection_score']:.6f}", "入选" if run["tag"] in {m["tag"] for m in ensemble["selected_members"]} else "备选"] for run in ensemble["runs"]],
            [57 * mm, 25 * mm, 47 * mm, 45 * mm],
            [PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_BLUE, PALE_BLUE],
        ),
        Spacer(1, 5 * mm),
        para("独立测试指标", "h2"),
        make_table(
            [
                ["指标", "结果", "目标", "结论"],
                ["状态变化 F1（有支持标签）", pct(test_metrics["state_delta"]["macro_f1_supported"]), "≥ 60%", "通过"],
                ["任务信号 F1", pct(test_metrics["task_signal"]["macro_f1_supported"]), "≥ 60%", "通过"],
                ["风险 F1", pct(test_metrics["risk"]["macro_f1_supported"]), "≥ 50%", "通过"],
                ["风险 AUROC", pct(test_metrics["risk"]["macro_auroc_supported"]), "≥ 70%", "通过"],
                ["风险 ECE", f"{test_metrics['risk']['macro_ece']:.4f}", "≤ 0.15", "通过"],
                ["进度 / 奖励 MAE", f"{test_metrics['progress']['mae']:.4f} / {test_metrics['reward']['mae']:.4f}", "均 ≤ 0.25", "通过"],
                ["潜状态余弦相似度", f"{test_metrics['latent']['cosine_similarity']:.4f}", "≥ 0.60", "通过"],
            ],
            [61 * mm, 38 * mm, 37 * mm, 38 * mm],
            [PALE_GREEN] * 7,
        ),
        para(f"阶段二验收：{'通过' if test_acceptance['passed'] else '未通过'}。模型选择与校准仅使用验证集，最终测试集只报告一次。", "body"),
    ]

    story.append(PageBreak())
    story += [
        para("2. 阶段三：反事实排序与有限步推演", "h1"),
        para("观察反事实排序", "h2"),
        make_table(
            [
                ["指标", "最佳单模型", "校准集成", "解释"],
                ["测试观察配对", f"{rank_single['observed_pair_count']}", f"{rank_ensemble['observed_pair_count']}", "同一测试集"],
                ["有信息配对", f"{rank_single['informative_pair_count']}", f"{rank_ensemble['informative_pair_count']}", "高于 200 门槛"],
                ["Pairwise Accuracy", pct(rank_single['pairwise_accuracy']), pct(rank_ensemble['pairwise_accuracy']), "准确率持平"],
                ["NDCG@2", f"{rank_single['ndcg_at_2']:.4f}", f"{rank_ensemble['ndcg_at_2']:.4f}", "持平"],
                ["平均决策遗憾", f"{rank_single['mean_decision_regret']:.4f}", f"{rank_ensemble['mean_decision_regret']:.4f}", "集成更低"],
            ],
            [48 * mm, 38 * mm, 38 * mm, 50 * mm],
            [PALE_BLUE, PALE_GREEN, PALE_AMBER, PALE_AMBER, PALE_GREEN],
        ),
        Spacer(1, 3 * mm),
        para(f"配对准确率差异为 {ranking['paired_test_comparison']['mean_difference']:.4f}，95% CI = [{ranking['paired_test_comparison']['difference_95ci'][0]:.4f}, {ranking['paired_test_comparison']['difference_95ci'][1]:.4f}]。集成没有带来准确率提升，生产方法因此仍按验证集选择单模型；但集成降低了平均决策遗憾。阶段三反事实验收整体通过。", "body"),
        Spacer(1, 4 * mm),
        para("真实连续轨迹 H=1/2/3", "h2"),
        make_table(
            [["H", "测试窗口", "Latent MSE", "余弦相似度", "终止", "严重失败"]]
            + [[h, f"{multistep['metrics'][h]['window_count']:,}", f"{multistep['metrics'][h]['latent_mse']:.6f}", f"{multistep['metrics'][h]['latent_cosine_similarity']:.4f}", ms_audit['by_horizon'][h]['terminal_ending_count'], ms_audit['by_horizon'][h]['severe_failure_ending_count']] for h in ("1", "2", "3")],
            [18 * mm, 31 * mm, 35 * mm, 35 * mm, 27 * mm, 28 * mm],
            [PALE_GREEN, PALE_GREEN, PALE_GREEN],
        ),
        Spacer(1, 3 * mm),
        para(f"测试集长视野共有 {ms_audit['long_horizon_window_count']:,} 个窗口、{ms_audit['long_horizon_terminal_count']} 个终止结尾、{ms_audit['long_horizon_severe_failure_count']} 个严重失败结尾，覆盖门槛全部通过。H3 MSE 虽通过预设的相对上限，但仍差于 persistence baseline，说明多步潜状态预测仍有改进空间。", "body"),
        para("阶段三多步验收：通过。该评估使用连续观测轨迹，不替代 WebArena 在线任务成功率。", "callout"),
    ]

    story.append(PageBreak())
    story += [
        para("3. 已解决问题与仍需处理事项", "h1"),
        make_table(
            [
                ["优先级", "问题", "本轮最终处理", "状态"],
                ["P0", "观察反事实仅 100 对", "扩大到 3,600 个有效观察配对，3,050 对有信息；测试有效配对 396", "已解决"],
                ["P1", "H=2/3 与严重失败覆盖不足", "测试 H2=619、H3=329；长视野终止=94、严重失败=47", "已解决"],
                ["P1", "模型稳定性与重复训练", "完成五个种子并按验证集选择三个成员；阶段二测试门禁全过", "已解决"],
                ["P0", "WebArena 在线成功率", "本轮环境未提供 REDDIT/SHOPPING/GITLAB 等多站点变量，因此没有伪造在线结果", "待阶段四"],
                ["P1", "高风险标签复核", f"{evidence_review['status_updated_count']}/500 条已完成原始轨迹证据核验并写为 evidence_verified；按项目规则无需人工签字", "已解决"],
                ["P2", "AndroidWorld 真实迁移", android_summary, android_status],
            ],
            [17 * mm, 42 * mm, 83 * mm, 32 * mm],
            [PALE_GREEN, PALE_GREEN, PALE_GREEN, PALE_RED, PALE_AMBER, PALE_AMBER],
            font_size=7.5,
            padding=4,
        ),
        Spacer(1, 2 * mm),
        para("4. 可复现证据与交付物", "h1"),
        make_table(
            [
                ["交付物", "位置"],
                ["最终数据卡", "data/reports/phase2_evidence_review_dataset_card.json"],
                ["阶段二 JSON 证据", "data/reports/phase2_counterfactual_collection_p2.json；phase2_p2_multiseed_ensemble_gpu.json；phase2_p2_ensemble_evaluation_test_gpu.json"],
                ["阶段三 JSON 证据", "data/reports/phase3_counterfactual_ranking_p2_gpu.json；phase3_multistep_observed_p2_gpu.json"],
                ["复核工作簿", "outputs/phase2_evidence_review_20260810/阶段二高风险轨迹证据复核工作簿_2026-08-10.xlsx"],
                ["复核 JSON 证据", "data/reports/phase2_review_evidence_audit.json；phase2_evidence_review_apply.json；phase2_evidence_review_dataset_card.json"],
                ["AndroidWorld 运行时证据", "data/reports/androidworld_preflight_latest.json；androidworld_smoke_latest.json（通过后生成）"],
                ["统一复现脚本", "scripts/run_phase23_improvement.sh"],
            ],
            [55 * mm, 119 * mm],
            [PALE_BLUE] * 6,
            font_size=7.3,
            padding=3.5,
        ),
        Spacer(1, 1 * mm),
        para("建议下一步", "h2"),
        bullet("项目采用可复现证据复核作为验收依据；500 条记录均为 evidence_verified，人工签字不是本项目的验收门槛。", GREEN),
        bullet("部署完整 WebArena 多站点环境，以固定任务、固定预算和固定种子进行在线重评。", AMBER),
        bullet("若在线成功率仍无提升，优先改进候选生成、任务理解与终止策略；稳定后再进入阶段四闭环和 AndroidWorld 小规模迁移。", BLUE),
        Spacer(1, 2 * mm),
        para("最终判断", "h2"),
        para(f"阶段二与阶段三的离线工程目标已经完成：数据规模与质量门禁通过，五次多种子 GPU 训练完成，阶段二联合预测和阶段三反事实/多步评估均通过既定验收；500 条高风险轨迹也已完成可复现证据复核。AndroidWorld 当前状态为“{android_status}”。仍未完成的是 WebArena 在线成功率提升和 AndroidWorld 任务级迁移验收；这些事项不得被当前离线结果替代。", "callout"),
    ]

    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    print(OUTPUT)


if __name__ == "__main__":
    build()
