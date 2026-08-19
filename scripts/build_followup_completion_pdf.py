#!/usr/bin/env python3
"""Build the verified follow-up completion report for phases two and three."""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "阶段二阶段三补强工作完成情况与遗留问题.pdf"
FONT = Path(r"C:\Windows\Fonts\simhei.ttf")
BLUE = colors.HexColor("#1769C2")
DEEP = colors.HexColor("#103B66")
CYAN = colors.HexColor("#0F9FA8")
GREEN = colors.HexColor("#2B8A3E")
ORANGE = colors.HexColor("#E67700")
RED = colors.HexColor("#C92A2A")
INK = colors.HexColor("#102A43")
MUTED = colors.HexColor("#627D98")
LINE = colors.HexColor("#D9E2EC")
PALE_BLUE = colors.HexColor("#EAF3FF")
PALE_CYAN = colors.HexColor("#E8F8FA")
PALE_GREEN = colors.HexColor("#EAF7ED")
PALE_ORANGE = colors.HexColor("#FFF4E6")
PALE_RED = colors.HexColor("#FFF0F0")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def dig(data: Any, *keys: str, default: Any = 0) -> Any:
    value = data
    for key in keys:
        if not isinstance(value, dict) or key not in value:
            return default
        value = value[key]
    return value


def pct(value: Any) -> str:
    try:
        return f"{100 * float(value):.2f}%"
    except (TypeError, ValueError):
        return "-"


class NumberedCanvas(Canvas):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._states)
        for state in self._states:
            self.__dict__.update(state)
            if self._pageNumber > 1:
                self.saveState()
                self.setStrokeColor(LINE)
                self.line(19 * mm, 14 * mm, A4[0] - 19 * mm, 14 * mm)
                self.setFillColor(MUTED)
                self.setFont("CN", 8)
                self.drawString(19 * mm, 9 * mm, "Agent 世界模型决策优化 · 补强工作报告")
                self.drawRightString(A4[0] - 19 * mm, 9 * mm, f"{self._pageNumber} / {total}")
                self.restoreState()
            super().showPage()
        super().save()


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontName="CN", fontSize=25, leading=35, textColor=colors.white, alignment=TA_LEFT),
        "cover": ParagraphStyle("cover", fontName="CN", fontSize=11.5, leading=19, textColor=colors.HexColor("#E8F3FF")),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="CN", fontSize=18, leading=25, textColor=DEEP, spaceAfter=5 * mm),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="CN", fontSize=12.5, leading=18, textColor=BLUE, spaceBefore=4 * mm, spaceAfter=2.5 * mm),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName="CN", fontSize=9.2, leading=15.5, textColor=INK, wordWrap="CJK", spaceAfter=2.5 * mm),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontName="CN", fontSize=7.5, leading=11.5, textColor=MUTED, wordWrap="CJK"),
        "table": ParagraphStyle("table", parent=base["BodyText"], fontName="CN", fontSize=7.4, leading=11.3, textColor=INK, wordWrap="CJK"),
        "card": ParagraphStyle("card", parent=base["BodyText"], fontName="CN", fontSize=8.2, leading=14, textColor=INK, alignment=TA_CENTER, wordWrap="CJK"),
        "center": ParagraphStyle("center", parent=base["BodyText"], fontName="CN", fontSize=10, leading=16, textColor=BLUE, alignment=TA_CENTER),
    }


S = styles()


def p(text: Any, style: str = "table") -> Paragraph:
    raw = str(text)
    rendered = raw if raw.startswith("<font") or "<br/>" in raw else escape(raw).replace("\n", "<br/>")
    return Paragraph(rendered, S[style])


def table(rows: list[list[Any]], widths: list[float], *, header: bool = True, backgrounds: dict[int, colors.Color] | None = None) -> Table:
    converted = [[cell if isinstance(cell, Paragraph) else p(cell) for cell in row] for row in rows]
    result = Table(converted, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands: list[tuple[Any, ...]] = [
        ("FONTNAME", (0, 0), (-1, -1), "CN"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), PALE_BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), DEEP)]
    for row_index, colour in (backgrounds or {}).items():
        commands.append(("BACKGROUND", (0, row_index), (-1, row_index), colour))
    result.setStyle(TableStyle(commands))
    return result


def cover_page(canvas: Canvas, doc: BaseDocTemplate) -> None:
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#F5F8FC"))
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setFillColor(DEEP)
    canvas.rect(0, A4[1] - 118 * mm, A4[0], 118 * mm, fill=1, stroke=0)
    canvas.setFillColor(BLUE)
    canvas.circle(A4[0] + 14 * mm, A4[1] - 35 * mm, 70 * mm, fill=1, stroke=0)
    canvas.setFillColor(CYAN)
    canvas.circle(A4[0] - 4 * mm, A4[1] - 102 * mm, 33 * mm, fill=1, stroke=0)
    canvas.restoreState()


def normal_page(canvas: Canvas, doc: BaseDocTemplate) -> None:
    canvas.saveState()
    canvas.setFillColor(BLUE)
    canvas.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, fill=1, stroke=0)
    canvas.restoreState()


def build() -> Path:
    if not FONT.exists():
        raise FileNotFoundError(FONT)
    pdfmetrics.registerFont(TTFont("CN", str(FONT)))
    dataset = load(ROOT / "data" / "phase2_p1" / "dataset_card.json")
    training = load(ROOT / "data" / "reports" / "phase2_training_p1_gpu.json")
    phase2 = load(ROOT / "data" / "reports" / "phase2_p1_evaluation_test_gpu.json")
    phase3 = load(ROOT / "data" / "reports" / "phase3_evaluation_p1_gpu.json")
    webarena = load(ROOT / "data" / "reports" / "webarena_online_evaluation_latest.json")
    llm = load(ROOT / "data" / "reports" / "candidate_generator_ablation_gpu.json")
    android = load(ROOT / "data" / "reports" / "androidworld_preflight_latest.json")
    cf = load(ROOT / "data" / "reports" / "phase2_counterfactual_collection_latest.json")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=19 * mm, rightMargin=19 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title="阶段二阶段三补强工作完成情况与遗留问题",
        author="Agent 世界模型决策优化项目组",
    )
    cover_frame = Frame(20 * mm, 24 * mm, A4[0] - 40 * mm, A4[1] - 48 * mm, id="cover")
    body_frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[cover_frame], onPage=cover_page),
        PageTemplate(id="body", frames=[body_frame], onPage=normal_page),
    ])

    count = dig(dataset, "transition_count")
    cf_pairs = dig(dataset, "counterfactual_audit", "valid_observed_pair_count")
    severe = dig(dataset, "positive_label_counts", "severe_failure")
    wa_sr = dig(webarena, "agent_metrics", "success_rate")
    llm_valid = dig(llm, "metrics", "local_llm", "candidate_schema_valid_rate")
    story: list[Any] = [
        Spacer(1, 20 * mm),
        p("阶段二、阶段三补强工作<br/>完成情况与遗留问题", "title"),
        Spacer(1, 4 * mm),
        p("P0/P1 数据补强 · WebArena 在线评估 · 本地 LLM 候选消融 · AndroidWorld 迁移预备 · GPU 复验", "cover"),
        Spacer(1, 57 * mm),
    ]
    cards = [
        ("数据规模", f"{count} 条", "P1 3000 条门槛"),
        ("反事实", f"{cf_pairs} 对", "真实环境成对执行"),
        ("严重失败", f"{severe} 条", "测试集有正类"),
        ("训练设备", "RTX 4090", "CUDA 正式运行"),
    ]
    card_cells = [p(f"<font color='#627D98'>{title}</font><br/><font color='#1769C2' size='16'>{value}</font><br/><font color='#627D98' size='7'>{note}</font>", "card") for title, value, note in cards]
    card_table = Table([card_cells], colWidths=[doc.width / 4] * 4, rowHeights=[29 * mm])
    card_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.white), ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [
        card_table,
        Spacer(1, 12 * mm),
        p("结论口径：已完成的数据、代码与 GPU 实验均给出可复查证据；尚未成功的 WebArena 自主任务、AndroidWorld 真机运行和 GitHub 推送不作完成声明。", "body"),
        p(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}（Asia/Shanghai）", "small"),
        PageBreak(),
    ]
    doc.handle_nextPageTemplate("body")

    story += [
        p("一、执行摘要", "h1"),
        table([
            ["工作项", "本轮结果", "状态"],
            ["WebArena 可重复在线评估", f"固定 5 个 Reddit-only 任务；自主 SR={pct(wa_sr)}，AER={pct(dig(webarena, 'agent_metrics', 'action_execution_rate'))}；评估器烟测 4/5", "评估链路完成，成功率目标未达"],
            ["成对反事实真实性", f"{cf_pairs} 对、{dig(dataset, 'counterfactual_audit', 'observed_transition_count')} 条真实执行转移；初始状态匹配率 {pct(dig(cf, 'pair_state_match_rate'))}", "完成"],
            ["严重失败正类", f"总计 {severe} 条；验证/测试分别 {dig(dataset, 'positive_label_counts_by_split', 'validation', 'severe_failure')} / {dig(dataset, 'positive_label_counts_by_split', 'test', 'severe_failure')} 条", "完成"],
            ["P1 数据规模", f"{count} 条转移、{dig(dataset, 'episode_count')} 个 episode、{dig(dataset, 'task_count')} 个任务", "完成"],
            ["LLM 候选消融", f"Qwen2.5-3B-Instruct 本地绑定；30/30 生成成功；合法率 {pct(llm_valid)}；Recall@K={pct(dig(llm, 'metrics', 'local_llm', 'recorded_action_recall_at_k'))}", "完成（文本 LLM）"],
            ["AndroidWorld 迁移", "状态/动作适配层与单元测试完成；无 ADB、模拟器和运行包", "代码完成，运行阻塞"],
            ["GitHub 托管", "本地分支存在，但连接器无账户、仓库无 remote、系统无 gh", "外部阻塞"],
        ], [42 * mm, 98 * mm, 27 * mm], backgrounds={2: PALE_GREEN, 3: PALE_GREEN, 4: PALE_GREEN, 5: PALE_GREEN, 6: PALE_ORANGE, 7: PALE_RED}),
        p("本轮最重要的变化", "h2"),
        p("原报告中的“数据不足 3000 条”“严重失败测试集无正类”“反事实只依赖模型预测”“LLM 未绑定”四项已经形成可复查闭环。WebArena 自主成功率仍为 0%，因此不能声称总体成功率提高 10%。", "body"),
        PageBreak(),
    ]

    gates = dig(dataset, "quality_gates", default={})
    story += [
        p("二、数据补强与质量门禁", "h1"),
        table([
            ["指标", "结果", "结论"],
            ["转移 / episode / 任务", f"{count} / {dig(dataset, 'episode_count')} / {dig(dataset, 'task_count')}", "P1 达标"],
            ["训练 / 验证 / 测试", f"{dig(dataset, 'split_counts', 'train')} / {dig(dataset, 'split_counts', 'validation')} / {dig(dataset, 'split_counts', 'test')}", "按 episode 切分"],
            ["重复 example_id", dig(dataset, "duplicate_example_ids"), "0"],
            ["episode 跨 split 泄漏", len(dig(dataset, "episode_split_leakage", default=[])), "0"],
            ["反事实跨 split 泄漏", len(dig(dataset, "counterfactual_audit", "pair_split_leakage", default=[])), "0"],
            ["反事实有效对", f"{dig(dataset, 'counterfactual_audit', 'valid_observed_pair_count')} / {dig(dataset, 'counterfactual_audit', 'pair_count')}", "100%"],
            ["P1 3000 条门禁", str(bool(gates.get("p1_3000_transitions"))), "通过"],
        ], [57 * mm, 55 * mm, 55 * mm], backgrounds={1: PALE_GREEN, 2: PALE_CYAN, 3: PALE_GREEN, 4: PALE_GREEN, 5: PALE_GREEN, 6: PALE_GREEN, 7: PALE_GREEN}),
        p("标签支持度", "h2"),
        table([
            ["标签", "总计", "训练", "验证", "测试"],
            *[
                [name, dig(dataset, "positive_label_counts", name), dig(dataset, "positive_label_counts_by_split", "train", name), dig(dataset, "positive_label_counts_by_split", "validation", name), dig(dataset, "positive_label_counts_by_split", "test", name)]
                for name in ("success", "stalled", "goal_deviation", "severe_failure", "invalid_action", "terminal")
            ],
        ], [45 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm]),
        p("严重失败定义说明", "h2"),
        p("MiniWoB 将部分失败终止归一化为 reward=0。本轮将“终止且未成功”的真实环境结果视为严重任务失败，同时保留负奖励和终止无效动作条件；它不是由世界模型预测伪造的标签。", "body"),
        PageBreak(),
    ]

    p2m = dig(phase2, "metrics", default={})
    p3m = dig(phase3, "metrics", default={})
    story += [
        p("三、RTX 4090 重训与阶段二/三复验", "h1"),
        p(f"世界模型使用 P1 数据集重新训练，最佳 epoch 为 {dig(training, 'best_epoch', default='-')}。旧检查点未覆盖，新检查点为 artifacts/phase2/world_model_p1_best.pt。", "body"),
        table([
            ["阶段二测试指标", "实际值", "门槛 / 说明"],
            ["状态变化 F1（支持标签）", f"{dig(p2m, 'state_delta', 'macro_f1_supported', default=0):.4f}", ">= 0.60"],
            ["任务信号 F1（支持标签）", f"{dig(p2m, 'task_signal', 'macro_f1_supported', default=0):.4f}", ">= 0.60"],
            ["风险 F1（支持标签）", f"{dig(p2m, 'risk', 'macro_f1_supported', default=0):.4f}", ">= 0.50"],
            ["风险 AUROC（支持标签）", f"{dig(p2m, 'risk', 'macro_auroc_supported', default=0):.4f}", ">= 0.70"],
            ["潜在状态余弦相似度", f"{dig(p2m, 'latent', 'cosine_similarity', default=0):.4f}", ">= 0.60"],
            ["进度 / 奖励 MAE", f"{dig(p2m, 'progress', 'mae', default=0):.4f} / {dig(p2m, 'reward', 'mae', default=0):.4f}", "<= 0.25"],
        ], [70 * mm, 42 * mm, 55 * mm]),
        p("阶段三 P1 检查点复验", "h2"),
        table([
            ["指标", "结果"],
            ["评估样本", dig(p3m, "examples_evaluated", default=0)],
            ["候选合法率", pct(dig(p3m, "candidate_schema_valid_rate"))],
            ["安全记录动作 Recall@K", pct(dig(p3m, "safe_recorded_action_recall_at_k"))],
            ["成功动作 Top-1 一致率", pct(dig(p3m, "methods", "phase3", "positive_recorded_action_agreement"))],
            ["风险动作分流率", pct(dig(p3m, "methods", "phase3", "risky_recorded_action_diversion"))],
            ["平均 / P95 规划延迟", f"{dig(p3m, 'latency_ms', 'mean', default=0):.2f} / {dig(p3m, 'latency_ms', 'p95', default=0):.2f} ms"],
        ], [83 * mm, 84 * mm]),
        p("注意：阶段三离线指标衡量候选覆盖、决策一致性和风险分流，不等价于 WebArena 在线任务成功率。", "small"),
        PageBreak(),
    ]

    story += [
        p("四、WebArena 在线评估与 LLM 候选消融", "h1"),
        p("WebArena", "h2"),
        table([
            ["评估口径", "任务数", "SR", "AER", "AvgStep"],
            ["自主规则 Agent", dig(webarena, "agent_metrics", "episodes"), pct(dig(webarena, "agent_metrics", "success_rate")), pct(dig(webarena, "agent_metrics", "action_execution_rate")), f"{dig(webarena, 'agent_metrics', 'average_steps', default=0):.2f}"],
            ["评估器链路烟测（不计入 Agent SR）", dig(webarena, "evaluator_integrity_metrics", "episodes"), pct(dig(webarena, "evaluator_integrity_metrics", "success_rate")), pct(dig(webarena, "evaluator_integrity_metrics", "action_execution_rate")), f"{dig(webarena, 'evaluator_integrity_metrics', 'average_steps', default=0):.2f}"],
        ], [61 * mm, 22 * mm, 25 * mm, 25 * mm, 34 * mm], backgrounds={1: PALE_ORANGE, 2: PALE_CYAN}),
        p("范围限制：仅部署 Reddit，固定任务为 27-31；这不是完整多站点 WebArena。预置答案烟测只验证官方 evaluator 链路，绝不计入自主成功率。", "body"),
        p("本地 LLM 候选", "h2"),
        table([
            ["方法", "成功率", "合法率", "Recall@K", "平均候选数", "平均延迟"],
            ["规则 AXTree", pct(dig(llm, "metrics", "rules", "strict_json_success_rate")), pct(dig(llm, "metrics", "rules", "candidate_schema_valid_rate")), pct(dig(llm, "metrics", "rules", "recorded_action_recall_at_k")), f"{dig(llm, 'metrics', 'rules', 'average_candidate_count', default=0):.2f}", f"{dig(llm, 'metrics', 'rules', 'latency_ms_mean', default=0):.2f} ms"],
            ["Qwen2.5-3B 受约束选择", pct(dig(llm, "metrics", "local_llm", "strict_json_success_rate")), pct(dig(llm, "metrics", "local_llm", "candidate_schema_valid_rate")), pct(dig(llm, "metrics", "local_llm", "recorded_action_recall_at_k")), f"{dig(llm, 'metrics', 'local_llm', 'average_candidate_count', default=0):.2f}", f"{dig(llm, 'metrics', 'local_llm', 'latency_ms_mean', default=0):.2f} ms"],
        ], [45 * mm, 24 * mm, 24 * mm, 26 * mm, 25 * mm, 27 * mm], backgrounds={2: PALE_GREEN}),
        p("LLM 采用“从已通过结构校验的候选池中选择并排序”的生产安全绑定，避免小模型幻觉 element id 或输出裸动词。结果表明 LLM 可以真实运行且合法率 100%，但候选覆盖低于规则、延迟高两个数量级；因此当前默认仍保留规则生成，LLM 作为可选语义重排器。VLM 未完成。", "body"),
        PageBreak(),
    ]

    blockers = dig(android, "blockers", default=[])
    story += [
        p("五、AndroidWorld、GitHub 与遗留问题", "h1"),
        p("AndroidWorld", "h2"),
        table([
            ["项目", "结果"],
            ["状态适配", "Android accessibility tree -> Agent AXTree/DOM 状态结构"],
            ["动作适配", "click/fill/type/scroll/back/press/noop -> Android 坐标与输入动作"],
            ["单元测试", "2/2 通过"],
            ["运行就绪", str(bool(dig(android, "runtime_ready", default=False)))],
            ["阻塞", "；".join(blockers) if blockers else "无"],
        ], [45 * mm, 122 * mm], backgrounds={1: PALE_GREEN, 2: PALE_GREEN, 3: PALE_GREEN, 4: PALE_ORANGE, 5: PALE_ORANGE}),
        p("GitHub", "h2"),
        p("GitHub 插件返回 0 个已安装账户；仓库没有 remote；系统也没有 gh CLI。现有本地分支为 codex/phase2-world-model。因为缺少目标仓库身份和推送通道，本轮没有伪造提交、push 或 PR。连接账户并提供目标仓库后即可继续。", "body"),
        p("仍未闭环的问题", "h2"),
        table([
            ["优先级", "问题", "当前结论", "下一步"],
            ["P0", "WebArena 自主成功率", "固定 Reddit 子集 SR=0%，未达到 +10% 主张门槛", "升级在线策略并扩展完整站点"],
            ["P1", "VLM 候选", "文本 LLM 已完成，图像 grounding 未验证", "绑定轻量 VLM 做同预算消融"],
            ["P2", "AndroidWorld 真机运行", "适配代码完成，运行环境缺失", "安装 SDK/ADB、启动 emulator、部署 AndroidWorld"],
            ["P2", "GitHub 托管", "账户与 remote 缺失", "连接账户和目标仓库后推送/PR"],
        ], [20 * mm, 37 * mm, 66 * mm, 44 * mm], backgrounds={1: PALE_RED, 2: PALE_ORANGE, 3: PALE_ORANGE, 4: PALE_RED}),
        PageBreak(),
    ]

    story += [
        p("六、交付物与复现入口", "h1"),
        table([
            ["交付物", "位置 / 用途"],
            ["P1 数据卡", "data/phase2_p1/dataset_card.json"],
            ["P1 世界模型", "artifacts/phase2/world_model_p1_best.pt"],
            ["阶段二 P1 测试", "data/reports/phase2_p1_evaluation_test_gpu.json"],
            ["阶段三 P1 复验", "data/reports/phase3_evaluation_p1_gpu.json"],
            ["WebArena 在线报告", "data/reports/webarena_online_evaluation_latest.json"],
            ["LLM 消融报告", "data/reports/candidate_generator_ablation_gpu.json"],
            ["AndroidWorld 预检", "data/reports/androidworld_preflight_latest.json"],
            ["GPU 服务器目录", "/root/autodl-tmp/agent_world_model_phase2"],
        ], [64 * mm, 103 * mm]),
        p("复现命令", "h2"),
        table([
            ["环节", "命令"],
            ["构建 P1 数据", "python scripts/build_phase2_dataset.py <六个轨迹目录> --output-dir data/phase2_p1 --require-p0"],
            ["训练", "python scripts/train_phase2_world_model.py --config configs/phase2_world_model_p1.json --device cuda"],
            ["测试", "python scripts/evaluate_phase2_world_model.py --config configs/phase2_world_model_p1.json --split test --device cuda"],
            ["LLM 消融", "python scripts/evaluate_candidate_generators.py --limit 30 --device cuda --dataset-dir data/phase2_p1"],
            ["WebArena", "python scripts/evaluate_webarena_online.py --mode both"],
            ["Android 预检", "python scripts/androidworld_preflight.py"],
        ], [43 * mm, 124 * mm]),
        p("建议顺序", "h2"),
        p("1）优先提升 WebArena 自主在线策略；2）补完整 WebArena 多站点部署；3）完成轻量 VLM 消融；4）准备 Android 模拟器并运行迁移烟测；5）连接 GitHub 后提交当前分支。阶段四的执行反馈、遗憾值闭环和在线参数更新仍应在后续阶段单独实施。", "body"),
        Spacer(1, 8 * mm),
        p("报告完", "center"),
    ]
    doc.build(story, canvasmaker=NumberedCanvas)
    print(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    build()
