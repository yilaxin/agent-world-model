#!/usr/bin/env python3
"""Build the final phase-two/phase-three progress and open-issues PDF."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

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
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "阶段二与阶段三任务进度及尚未解决问题报告.pdf"
FONT = Path(r"C:\Windows\Fonts\simhei.ttf")
BLUE = colors.HexColor("#1769C2")
DEEP_BLUE = colors.HexColor("#103B66")
CYAN = colors.HexColor("#13A8B5")
GREEN = colors.HexColor("#2F9E44")
ORANGE = colors.HexColor("#F08C00")
RED = colors.HexColor("#D9485F")
INK = colors.HexColor("#102A43")
MUTED = colors.HexColor("#627D98")
PALE_BLUE = colors.HexColor("#EAF3FF")
PALE_CYAN = colors.HexColor("#E8F8FA")
PALE_ORANGE = colors.HexColor("#FFF4E6")
LINE = colors.HexColor("#D9E2EC")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def pct(value: float) -> str:
    return f"{100 * value:.2f}%"


class NumberedCanvas(Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states = []

    def showPage(self) -> None:
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        page_count = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._draw_page_number(page_count)
            super().showPage()
        super().save()

    def _draw_page_number(self, page_count: int) -> None:
        if self._pageNumber == 1:
            return
        self.saveState()
        self.setStrokeColor(LINE)
        self.line(20 * mm, 14 * mm, A4[0] - 20 * mm, 14 * mm)
        self.setFillColor(MUTED)
        self.setFont("SimHei", 8)
        self.drawString(20 * mm, 9 * mm, "Agent 世界模型决策优化 · 阶段二/三进度报告")
        self.drawRightString(A4[0] - 20 * mm, 9 * mm, f"{self._pageNumber} / {page_count}")
        self.restoreState()


class DecisionFlow(Flowable):
    def __init__(self, width: float) -> None:
        super().__init__()
        self.width = width
        self.height = 42 * mm

    def draw(self) -> None:
        labels = [
            ("结构化状态", "任务 + AXTree/DOM"),
            ("候选生成", "规则或 LLM/VLM"),
            ("H=1～3 推演", "W0 + beam search"),
            ("综合评分", "短/长/不确定性/结构"),
            ("执行或回退", "规划/重观测/反应式"),
        ]
        gap = 6 * mm
        arrow = 5 * mm
        box_width = (self.width - 4 * (gap + arrow)) / 5
        y = 7 * mm
        for index, (title, subtitle) in enumerate(labels):
            x = index * (box_width + gap + arrow)
            self.canv.setFillColor(PALE_CYAN if index % 2 else PALE_BLUE)
            self.canv.setStrokeColor(CYAN if index % 2 else BLUE)
            self.canv.roundRect(x, y, box_width, 25 * mm, 3 * mm, fill=1, stroke=1)
            self.canv.setFillColor(INK)
            self.canv.setFont("SimHei", 9)
            self.canv.drawCentredString(x + box_width / 2, y + 16 * mm, title)
            self.canv.setFillColor(MUTED)
            self.canv.setFont("SimHei", 6.8)
            self.canv.drawCentredString(x + box_width / 2, y + 9 * mm, subtitle)
            if index < 4:
                ax = x + box_width + 1.5 * mm
                ay = y + 12.5 * mm
                self.canv.setStrokeColor(BLUE)
                self.canv.setLineWidth(1.3)
                self.canv.line(ax, ay, ax + arrow + 2 * mm, ay)
                self.canv.line(ax + arrow + 2 * mm, ay, ax + arrow, ay + 2 * mm)
                self.canv.line(ax + arrow + 2 * mm, ay, ax + arrow, ay - 2 * mm)


class ComparisonBars(Flowable):
    def __init__(self, width: float, methods: dict[str, dict]) -> None:
        super().__init__()
        self.width = width
        self.height = 64 * mm
        self.methods = methods

    def _panel(self, x: float, title: str, key: str) -> None:
        panel_width = (self.width - 10 * mm) / 2
        self.canv.setFillColor(colors.white)
        self.canv.setStrokeColor(LINE)
        self.canv.roundRect(x, 3 * mm, panel_width, 56 * mm, 3 * mm, fill=1, stroke=1)
        self.canv.setFillColor(INK)
        self.canv.setFont("SimHei", 9)
        self.canv.drawString(x + 5 * mm, 51 * mm, title)
        names = [("reactive", "反应式"), ("w0_one_step", "一步 W0"), ("phase3", "阶段三")]
        bar_x = x + 25 * mm
        max_width = panel_width - 33 * mm
        palette = [MUTED, CYAN, BLUE]
        for row, ((name, label), colour) in enumerate(zip(names, palette)):
            value = float(self.methods[name][key])
            y = 39 * mm - row * 13 * mm
            self.canv.setFillColor(MUTED)
            self.canv.setFont("SimHei", 7.5)
            self.canv.drawRightString(bar_x - 3 * mm, y + 1.8 * mm, label)
            self.canv.setFillColor(colors.HexColor("#EEF2F6"))
            self.canv.roundRect(bar_x, y, max_width, 5 * mm, 2 * mm, fill=1, stroke=0)
            self.canv.setFillColor(colour)
            self.canv.roundRect(bar_x, y, max_width * value, 5 * mm, 2 * mm, fill=1, stroke=0)
            self.canv.setFillColor(INK)
            self.canv.setFont("SimHei", 7)
            self.canv.drawRightString(x + panel_width - 4 * mm, y + 1.5 * mm, pct(value))

    def draw(self) -> None:
        self._panel(0, "已观测成功动作 Top-1 一致率", "positive_recorded_action_agreement")
        self._panel((self.width + 10 * mm) / 2, "已观测风险动作分流率", "risky_recorded_action_diversion")


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=base["Title"], fontName="SimHei", fontSize=25,
            leading=34, textColor=colors.white, alignment=TA_LEFT, spaceAfter=7 * mm,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", fontName="SimHei", fontSize=12, leading=20,
            textColor=colors.HexColor("#E5F2FF"),
        ),
        "h1": ParagraphStyle(
            "h1", parent=base["Heading1"], fontName="SimHei", fontSize=19,
            leading=25, textColor=DEEP_BLUE, spaceBefore=2 * mm, spaceAfter=5 * mm,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base["Heading2"], fontName="SimHei", fontSize=13,
            leading=18, textColor=BLUE, spaceBefore=4 * mm, spaceAfter=3 * mm,
        ),
        "body": ParagraphStyle(
            "body", parent=base["BodyText"], fontName="SimHei", fontSize=9.3,
            leading=16, textColor=INK, wordWrap="CJK", spaceAfter=2.3 * mm,
        ),
        "small": ParagraphStyle(
            "small", parent=base["BodyText"], fontName="SimHei", fontSize=7.5,
            leading=11.5, textColor=MUTED, wordWrap="CJK",
        ),
        "table": ParagraphStyle(
            "table", parent=base["BodyText"], fontName="SimHei", fontSize=7.4,
            leading=11.2, textColor=INK, wordWrap="CJK",
        ),
        "callout": ParagraphStyle(
            "callout", parent=base["BodyText"], fontName="SimHei", fontSize=9.2,
            leading=16, textColor=DEEP_BLUE, wordWrap="CJK",
        ),
    }


def P(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def make_table(data, widths, *, header=True, font_size=7.4, row_backgrounds=None) -> Table:
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), "SimHei"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size * 1.55),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), PALE_BLUE),
            ("TEXTCOLOR", (0, 0), (-1, 0), DEEP_BLUE),
        ])
    if row_backgrounds:
        for row, colour in row_backgrounds.items():
            commands.append(("BACKGROUND", (0, row), (-1, row), colour))
    table.setStyle(TableStyle(commands))
    return table


def draw_cover(canvas: Canvas, doc: BaseDocTemplate) -> None:
    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#F5F8FC"))
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setFillColor(DEEP_BLUE)
    canvas.rect(0, A4[1] - 112 * mm, A4[0], 112 * mm, fill=1, stroke=0)
    canvas.setFillColor(BLUE)
    canvas.circle(A4[0] + 20 * mm, A4[1] - 30 * mm, 72 * mm, fill=1, stroke=0)
    canvas.setFillColor(CYAN)
    canvas.circle(A4[0] - 4 * mm, A4[1] - 95 * mm, 34 * mm, fill=1, stroke=0)
    canvas.restoreState()


def draw_normal(canvas: Canvas, doc: BaseDocTemplate) -> None:
    canvas.saveState()
    canvas.setFillColor(BLUE)
    canvas.rect(0, A4[1] - 7 * mm, A4[0], 7 * mm, fill=1, stroke=0)
    canvas.restoreState()


def build() -> None:
    pdfmetrics.registerFont(TTFont("SimHei", str(FONT)))
    styles = build_styles()
    p2 = load_json(ROOT / "data" / "reports" / "phase2_evaluation_test_gpu.json")
    p2_train = load_json(ROOT / "data" / "reports" / "phase2_training_gpu.json")
    p3 = load_json(ROOT / "data" / "reports" / "phase3_evaluation_gpu.json")
    p3m = p3["metrics"]
    p3_methods = p3m["methods"]
    checkpoint = ROOT / "artifacts" / "phase2" / "world_model_best_gpu.pt"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=19 * mm, rightMargin=19 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title="阶段二与阶段三任务进度及尚未解决问题报告",
        author="Agent 世界模型决策优化项目组",
        subject="大创项目阶段二与阶段三技术进度、GPU验收和遗留问题",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    cover_frame = Frame(20 * mm, 24 * mm, A4[0] - 40 * mm, A4[1] - 48 * mm, id="cover")
    doc.addPageTemplates([
        PageTemplate(id="cover", frames=[cover_frame], onPage=draw_cover),
        PageTemplate(id="normal", frames=[frame], onPage=draw_normal),
    ])

    story = []
    story.extend([
        Spacer(1, 20 * mm),
        P("阶段二与阶段三<br/>任务进度及尚未解决问题报告", styles["title"]),
        P("动作条件世界模型 · 候选动作前瞻决策 · 完整 Agent 原型", styles["cover_sub"]),
        Spacer(1, 55 * mm),
    ])
    cards = [
        ("阶段二", "10/10", "GPU 验收门槛"),
        ("阶段三", "6/6", "GPU 验收门槛"),
        ("测试集", "231/231", "状态完整覆盖"),
        ("设备", "RTX 4090", "CUDA 正式运行"),
    ]
    card_data = []
    for title, value, note in cards:
        card_data.append(P(f"<font color='#627D98' size='8'>{title}</font><br/><font color='#1769C2' size='17'>{value}</font><br/><font color='#627D98' size='7'>{note}</font>", styles["body"]))
    card_table = Table([card_data], colWidths=[doc.width / 4] * 4, rowHeights=[27 * mm])
    card_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.extend([
        card_table,
        Spacer(1, 12 * mm),
        P("依据：《大创申报书 33.0》及阶段二、阶段三服务器实测结果", styles["body"]),
        P(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}（Asia/Shanghai）", styles["small"]),
        PageBreak(),
    ])
    doc.handle_nextPageTemplate("normal")

    story.extend([
        P("一、执行摘要", styles["h1"]),
        P("阶段二和阶段三已经形成可复现的技术链：阶段二提供动作条件的一步世界模型 W0；阶段三在其上实现候选生成、1～3 步前瞻推演、综合评分、结构一致性、有限步重排序与置信度自适应回退。两个阶段均在 RTX 4090 服务器上完成正式验收。", styles["body"]),
    ])
    summary_data = [
        [P("范围", styles["table"]), P("已完成", styles["table"]), P("仍需完成", styles["table"])],
        [P("阶段二", styles["table"]), P("1536 条转移；W0 训练；状态变化、进度、风险、终止与不确定性预测；验证/测试 10/10 通过", styles["table"]), P("扩大到 3000 条 P1 目标；补充严重失败正类；跨环境数据", styles["table"])],
        [P("阶段三", styles["table"]), P("候选生成；H=1～3 rollout；综合评分；结构约束；置信度回退；完整 Agent；GPU 比较实验", styles["table"]), P("WebArena 在线成功率；绑定 LLM/VLM；AndroidWorld 迁移", styles["table"])],
        [P("阶段边界", styles["table"]), P("每个真实动作后重新观察页面，避免把预测 latent 当真实 DOM", styles["table"]), P("反馈、遗憾度和在线参数更新属于阶段四，本报告不提前宣称", styles["table"])],
    ]
    story.extend([
        make_table(summary_data, [27 * mm, 86 * mm, 54 * mm]),
        P("核心结论", styles["h2"]),
        make_table([
            [P("阶段二", styles["table"]), P("测试集进度 MAE 0.0625；奖励 MAE 0.0641；支持标签风险 F1 0.9617；潜在状态余弦相似度 0.9631。", styles["table"])],
            [P("阶段三", styles["table"]), P("候选合法率、安全动作 Recall@K、解释完整率和有限步合规率均为 100%；成功动作 Top-1 一致率 86.36%。", styles["table"])],
            [P("审慎说明", styles["table"]), P("阶段三比较为 MiniWoB 留出轨迹上的离线代理指标，不能替代 WebArena 在线任务成功率。", styles["table"])],
        ], [30 * mm, 137 * mm], header=False, row_backgrounds={2: PALE_ORANGE}),
        P("系统总览", styles["h2"]),
        DecisionFlow(doc.width),
        PageBreak(),
    ])

    p2_metrics = p2["metrics"]
    story.extend([
        P("二、阶段二：动作条件世界模型", styles["h1"]),
        P("阶段二目标是给定状态和动作，预测下一状态及任务信号。正式模型在服务器 CUDA 环境训练，在线推断不会读取下一观测；下一状态 posterior 只作为训练目标。", styles["body"]),
        P("2.1 数据与训练", styles["h2"]),
        make_table([
            ["项目", "结果", "核验"],
            ["数据规模", "1536 条转移 / 713 个 episode / 32 个任务", "P0 通过；P1 目标未达"],
            ["数据划分", "1089 / 216 / 231", "按 episode 切分，无跨集合泄漏"],
            ["GPU", "NVIDIA GeForce RTX 4090", "PyTorch 2.1.2+cu121 / CUDA 12.1"],
            ["最佳模型", f"epoch {p2_train['best_epoch']}", "AMP + 早停 + 独立测试集"],
            ["阶段验收", "验证集 10/10；测试集 10/10", "均通过"],
        ], [33 * mm, 76 * mm, 58 * mm]),
        P("2.2 测试集关键指标", styles["h2"]),
        make_table([
            ["指标", "实际值", "验收阈值", "状态"],
            ["状态变化 F1（支持标签）", f"{p2_metrics['state_delta']['macro_f1_supported']:.4f}", "≥ 0.60", "通过"],
            ["任务信号 F1（支持标签）", f"{p2_metrics['task_signal']['macro_f1_supported']:.4f}", "≥ 0.60", "通过"],
            ["风险 F1（支持标签）", f"{p2_metrics['risk']['macro_f1_supported']:.4f}", "≥ 0.50", "通过"],
            ["风险 AUROC（支持标签）", f"{p2_metrics['risk']['macro_auroc_supported']:.4f}", "≥ 0.70", "通过"],
            ["潜在状态余弦相似度", f"{p2_metrics['latent']['cosine_similarity']:.4f}", "≥ 0.60", "通过"],
            ["进度 MAE", f"{p2_metrics['progress']['mae']:.4f}", "≤ 0.25", "通过"],
            ["奖励 MAE", f"{p2_metrics['reward']['mae']:.4f}", "≤ 0.25", "通过"],
        ], [62 * mm, 32 * mm, 35 * mm, 38 * mm], row_backgrounds={1: PALE_CYAN, 2: PALE_CYAN, 3: PALE_CYAN, 4: PALE_CYAN, 5: PALE_CYAN, 6: PALE_CYAN, 7: PALE_CYAN}),
        P("2.3 阶段二交付物", styles["h2"]),
        P("数据协议与质量门槛、语义一步模型协议、可训练潜在动力学模型、独立损失与指标、CUDA 训练/评测入口、候选动作 W0 重排序演示、服务器最佳检查点与完整报告均已落盘。", styles["body"]),
        P(f"检查点 SHA-256：<font size='7'>{sha256(checkpoint)}</font>", styles["small"]),
        PageBreak(),
    ])

    story.extend([
        P("三、阶段三：候选动作前瞻决策", styles["h1"]),
        P("阶段三把 W0 从单步预测器组合为可执行的规划 Agent。系统严格采用有限步想象：规划中的后续动作来自当前候选集；真实执行一个动作后重新观察页面、更新结构并重新规划。", styles["body"]),
        DecisionFlow(doc.width),
        P("3.1 对照申报书完成情况", styles["h2"]),
        make_table([
            ["要求", "实现摘要", "状态"],
            ["候选动作生成", "AXTree 结构生成、去重、语法与可见目标校验；严格 JSON LLM/VLM 适配器", "完成"],
            ["世界模型推演", "H=1～3 潜在状态 rollout；终止概率感知；按首动作分组 beam search", "完成"],
            ["综合评分", "Jshort + λJlong - κU + ηSstruct，各分量与逐步概率可审计", "完成"],
            ["结构一致性", "目标可见性、动作—角色兼容性、任务—元素语义重叠", "完成"],
            ["有限步重排序", "每个首动作选择最佳有限步轨迹，再做 Top-K 排序", "完成"],
            ["置信度感知", "高置信 H=3；中置信 H=1；低置信重观测；极低置信反应式回退", "完成"],
            ["完整 Agent 原型", "状态编码、候选、规划、解释与安全回退统一接口", "完成"],
        ], [35 * mm, 105 * mm, 27 * mm], row_backgrounds={1: PALE_CYAN, 2: PALE_CYAN, 3: PALE_CYAN, 4: PALE_CYAN, 5: PALE_CYAN, 6: PALE_CYAN, 7: PALE_CYAN}),
        P("3.2 主要代码", styles["h2"]),
        make_table([
            ["文件", "职责"],
            ["phase3_candidates.py", "候选动作、LLM/VLM 适配、结构一致性"],
            ["phase3_planning.py", "置信度自适应 H=1～3 前瞻规划"],
            ["phase3_agent.py", "完整 Agent 决策入口"],
            ["evaluate_phase3_planner.py", "231 条留出转移比较与验收"],
            ["run_phase3_gpu.sh", "CUDA 强校验与服务器复现"],
        ], [60 * mm, 107 * mm]),
        PageBreak(),
    ])

    story.extend([
        P("四、阶段三 GPU 评测与比较实验", styles["h1"]),
        P("评测在服务器 RTX 4090 上使用阶段二正式检查点运行。所有 231 条样本来自独立测试 split，并关联回原始 AXTree/DOM 轨迹；没有重新训练阶段二模型。", styles["body"]),
        make_table([
            ["指标", "结果", "说明"],
            ["原始状态匹配", "231/231（100%）", "测试样本全部关联原始结构"],
            ["候选合法率", pct(p3m["candidate_schema_valid_rate"]), "动作语法和目标可见性"],
            ["安全动作 Recall@K", pct(p3m["safe_recorded_action_recall_at_k"]), "排除故意风险探针"],
            ["解释完整率", pct(p3m["explanation_completeness"]), "逐步进度/奖励/风险/不确定性齐全"],
            ["H=3 / H=1", f"{p3m['horizon_distribution']['3']} / {p3m['horizon_distribution']['1']}", "由置信度自动选择"],
            ["平均置信度", f"{p3m['average_confidence']:.4f}", "231 条平均"],
            ["平均 / P95 延迟", f"{p3m['latency_ms']['mean']:.2f} / {p3m['latency_ms']['p95']:.2f} ms", "包含候选有限步规划"],
        ], [47 * mm, 46 * mm, 74 * mm]),
        P("4.1 离线代理对照", styles["h2"]),
        ComparisonBars(doc.width, p3_methods),
        make_table([
            ["方法", "成功动作 Top-1 一致率", "风险动作分流率"],
            ["反应式", pct(p3_methods["reactive"]["positive_recorded_action_agreement"]), pct(p3_methods["reactive"]["risky_recorded_action_diversion"])],
            ["一步 W0", pct(p3_methods["w0_one_step"]["positive_recorded_action_agreement"]), pct(p3_methods["w0_one_step"]["risky_recorded_action_diversion"])],
            ["阶段三", pct(p3_methods["phase3"]["positive_recorded_action_agreement"]), pct(p3_methods["phase3"]["risky_recorded_action_diversion"])],
        ], [55 * mm, 56 * mm, 56 * mm], row_backgrounds={3: PALE_CYAN}),
        Spacer(1, 3 * mm),
        make_table([[P("结果解释", styles["table"]), P("阶段三成功动作一致率比一步 W0 提高 22.72 个百分点，同时风险分流率只比一步 W0 低 0.79 个百分点。结构一致性弥补了 W0 对不同元素 ID 的不稳定偏好。", styles["table"])]], [30 * mm, 137 * mm], header=False),
        PageBreak(),
    ])

    story.extend([
        P("五、验证证据与结果位置", styles["h1"]),
        P("5.1 测试与服务器", styles["h2"]),
        make_table([
            ["验证项", "结果"],
            ["本地完整单元测试", "33/33 通过"],
            ["阶段三 GPU 单元测试", "6/6 通过"],
            ["Python 编译检查", "31 个模块/脚本通过"],
            ["阶段二 GPU 验收", "验证集 10/10，测试集 10/10"],
            ["阶段三 GPU 验收", "6/6 门槛通过"],
            ["GPU 服务器目录", "/root/autodl-tmp/agent_world_model_phase2"],
        ], [58 * mm, 109 * mm]),
        P("5.2 主要结果文件", styles["h2"]),
        make_table([
            ["文件", "用途"],
            ["artifacts/phase2/world_model_best_gpu.pt", "阶段二最佳 GPU 检查点"],
            ["data/reports/phase2_evaluation_test_gpu.json", "阶段二独立测试集指标"],
            ["data/reports/phase3_evaluation_gpu.json", "阶段三 RTX 4090 正式比较实验"],
            ["data/reports/phase3_demo_gpu.json", "单任务完整三步决策演示"],
            ["PHASE2_COMPLETION_REPORT.md", "阶段二完成报告"],
            ["PHASE3_COMPLETION_REPORT.md", "阶段三完成报告"],
            ["PHASE3_PAPER_DRAFT.md", "阶段三论文初稿"],
            ["output/phase3_dashboard.html", "浏览器可视化验收看板"],
        ], [80 * mm, 87 * mm]),
        P("5.3 复现入口", styles["h2"]),
        make_table([[P("阶段二", styles["table"]), P("bash scripts/run_phase2_gpu.sh", styles["table"])], [P("阶段三", styles["table"]), P("PYTHON_BIN=/root/miniconda3/bin/python PHASE2_CHECKPOINT=artifacts/phase2/world_model_best.pt bash scripts/run_phase3_gpu.sh", styles["table"])]], [30 * mm, 137 * mm], header=False),
        PageBreak(),
    ])

    issues = [
        ("P0", "WebArena 在线成功率", "尚未完成端到端在线评测，当前不能声称总体成功率提高 10%。", "部署 WebArena，固定任务集、预算和种子，报告 SR/AER/AvgStep。"),
        ("P0", "反事实真实性", "只有记录动作有真实结果；替代候选的收益和风险仍是模型预测。", "在环境中执行受控候选，构造带配对反事实的评测集。"),
        ("P1", "严重失败正类", "测试集 severe_failure 正类为 0，对应风险头未得到正类验证。", "补充终止性错误、破坏性操作和负奖励轨迹并重新校准。"),
        ("P1", "数据规模", "1536 条已超过 500 条 P0 门槛，但低于 3000 条 P1 目标。", "扩大任务/页面/种子覆盖，并保持 episode 级切分。"),
        ("P1", "LLM/VLM 候选", "严格适配器已完成，但没有绑定具体提供商与凭证。", "选择模型并在同一候选预算下做规则/LLM/VLM 消融。"),
        ("P2", "跨环境迁移", "AndroidWorld 小规模迁移尚未进行。", "稳定 WebArena 结果后再做小规模动作映射与迁移。"),
        ("P2", "远程代码托管", "GitHub 插件当前没有已安装账号，无法推送或创建 PR。", "连接 GitHub 账号与目标仓库后再推送当前分支。"),
    ]
    issue_rows = [["优先级", "问题", "当前影响", "建议动作"]] + [
        [P(a, styles["table"]), P(b, styles["table"]), P(c, styles["table"]), P(d, styles["table"])]
        for a, b, c, d in issues
    ]
    story.extend([
        P("六、尚未解决的问题", styles["h1"]),
        P("下表只列尚未形成实证闭环的部分。它们不影响阶段三代码原型完成，但会影响对项目最终效果的外部主张。", styles["body"]),
        make_table(issue_rows, [17 * mm, 35 * mm, 60 * mm, 55 * mm], font_size=6.8, row_backgrounds={1: colors.HexColor("#FFE3E6"), 2: colors.HexColor("#FFE3E6"), 3: PALE_ORANGE, 4: PALE_ORANGE, 5: PALE_ORANGE}),
        P("阶段边界提醒", styles["h2"]),
        make_table([[P("阶段四内容", styles["table"]), P("真实执行后的预测—现实偏差、遗憾度、在线反馈权重更新与动态重规划。本次没有把这些未完成内容写成阶段三成果。", styles["table"])]], [35 * mm, 132 * mm], header=False, row_backgrounds={0: PALE_ORANGE}),
        P("建议下一步顺序", styles["h2"]),
        P("1）先完成 WebArena 可重复在线评测；2）补严重失败与反事实数据；3）绑定 LLM/VLM 并做候选生成消融；4）进入阶段四反馈遗憾闭环；5）最后开展 AndroidWorld 迁移。", styles["body"]),
        P("交付状态", styles["h2"]),
        make_table([
            ["项目", "状态"],
            ["本地分支", "codex/phase2-world-model（含阶段二、阶段三）"],
            ["GPU 服务器", "代码、阶段二检查点、阶段三 GPU 报告已同步"],
            ["GitHub", "未推送：插件没有连接账号；不做虚假远程交付声明"],
            ["最终 PDF", str(OUTPUT.relative_to(ROOT)).replace("\\", "/")],
        ], [45 * mm, 122 * mm]),
        Spacer(1, 8 * mm),
        P("报告完", ParagraphStyle("end", parent=styles["h1"], alignment=TA_CENTER, textColor=BLUE)),
    ])

    doc.build(story, canvasmaker=NumberedCanvas)
    print(OUTPUT)


if __name__ == "__main__":
    build()
