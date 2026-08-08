#!/usr/bin/env python3
"""Build the final verified phase-two/three multirun PDF report."""

from __future__ import annotations

import json
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "阶段二阶段三多次训练完善报告.pdf"
FONT = Path(r"C:\Windows\Fonts\simhei.ttf")
INK = colors.HexColor("#102A43")
MUTED = colors.HexColor("#627D98")
BLUE = colors.HexColor("#1769C2")
DEEP = colors.HexColor("#103B66")
CYAN = colors.HexColor("#0F9FA8")
GREEN = colors.HexColor("#2B8A3E")
ORANGE = colors.HexColor("#E67700")
RED = colors.HexColor("#C92A2A")
LINE = colors.HexColor("#D9E2EC")
PALE_BLUE = colors.HexColor("#EAF3FF")
PALE_GREEN = colors.HexColor("#EAF7ED")
PALE_ORANGE = colors.HexColor("#FFF4E6")
PALE_RED = colors.HexColor("#FFF0F0")


def load(name: str) -> dict[str, Any]:
    path = ROOT / "data" / "reports" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def dig(data: Any, *keys: str, default: Any = 0) -> Any:
    for key in keys:
        if not isinstance(data, dict) or key not in data:
            return default
        data = data[key]
    return data


def pct(value: Any) -> str:
    return f"{100 * float(value):.1f}%"


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
                self.drawString(19 * mm, 9 * mm, "Agent 世界模型决策优化 · 阶段二/三多次训练报告")
                self.drawRightString(A4[0] - 19 * mm, 9 * mm, f"{self._pageNumber} / {total}")
                self.restoreState()
            super().showPage()
        super().save()


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", fontName="CN", fontSize=25, leading=36, textColor=colors.white),
        "cover": ParagraphStyle("cover", fontName="CN", fontSize=11, leading=19, textColor=colors.HexColor("#E8F3FF")),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="CN", fontSize=18, leading=25, textColor=DEEP, spaceAfter=5 * mm),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="CN", fontSize=12.5, leading=18, textColor=BLUE, spaceBefore=4 * mm, spaceAfter=2.5 * mm),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName="CN", fontSize=9.2, leading=15.5, textColor=INK, wordWrap="CJK", spaceAfter=2.5 * mm),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontName="CN", fontSize=7.5, leading=11.5, textColor=MUTED, wordWrap="CJK"),
        "table": ParagraphStyle("table", parent=base["BodyText"], fontName="CN", fontSize=7.5, leading=11.5, textColor=INK, wordWrap="CJK"),
        "card": ParagraphStyle("card", parent=base["BodyText"], fontName="CN", fontSize=8.3, leading=14, textColor=INK, alignment=TA_CENTER, wordWrap="CJK"),
    }


S = styles()


def p(text: Any, style: str = "table") -> Paragraph:
    raw = str(text)
    rendered = raw if raw.startswith("<font") or "<br/>" in raw else escape(raw).replace("\n", "<br/>")
    return Paragraph(rendered, S[style])


def tbl(rows: list[list[Any]], widths: list[float], backgrounds: dict[int, Any] | None = None) -> Table:
    result = Table([[cell if isinstance(cell, Paragraph) else p(cell) for cell in row] for row in rows], colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("FONTNAME", (0, 0), (-1, -1), "CN"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), .5, LINE), ("BACKGROUND", (0, 0), (-1, 0), PALE_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), DEEP), ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for index, colour in (backgrounds or {}).items():
        commands.append(("BACKGROUND", (0, index), (-1, index), colour))
    result.setStyle(TableStyle(commands))
    return result


def cover(canvas: Canvas, doc: BaseDocTemplate) -> None:
    canvas.saveState(); canvas.setFillColor(colors.HexColor("#F5F8FC")); canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setFillColor(DEEP); canvas.rect(0, A4[1] - 120 * mm, A4[0], 120 * mm, fill=1, stroke=0)
    canvas.setFillColor(BLUE); canvas.circle(A4[0] + 14 * mm, A4[1] - 36 * mm, 70 * mm, fill=1, stroke=0)
    canvas.setFillColor(CYAN); canvas.circle(A4[0] - 5 * mm, A4[1] - 103 * mm, 34 * mm, fill=1, stroke=0); canvas.restoreState()


def normal(canvas: Canvas, doc: BaseDocTemplate) -> None:
    canvas.saveState(); canvas.setFillColor(BLUE); canvas.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, fill=1, stroke=0); canvas.restoreState()


def build() -> Path:
    if not FONT.exists(): raise FileNotFoundError(FONT)
    pdfmetrics.registerFont(TTFont("CN", str(FONT)))
    multi = load("phase2_multiseed_ensemble_gpu.json")
    p2 = load("phase2_ensemble_evaluation_test_gpu.json")
    align = load("phase3_structure_alignment_gpu.json")
    cf = load("phase3_counterfactual_ranking_gpu.json")
    p3 = load("phase3_evaluation_ensemble_gpu.json")
    online = load("webarena_phase3_online_evaluation_gpu.json")
    m2, m3 = dig(p2, "metrics", default={}), dig(p3, "metrics", default={})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=19*mm, rightMargin=19*mm, topMargin=18*mm, bottomMargin=20*mm, title="阶段二阶段三多次训练完善报告", author="Agent 世界模型决策优化项目组")
    doc.addPageTemplates([PageTemplate(id="cover", frames=[Frame(20*mm,24*mm,A4[0]-40*mm,A4[1]-48*mm,id="cover")], onPage=cover), PageTemplate(id="body", frames=[Frame(doc.leftMargin,doc.bottomMargin,doc.width,doc.height,id="body")], onPage=normal)])
    story: list[Any] = [Spacer(1,20*mm), p("阶段二、阶段三多次训练<br/>完善与复核报告", "title"), Spacer(1,4*mm), p("动作条件世界模型 · 五次独立训练 · 三模型校准集成 · 动态结构对齐 · 有限步候选决策", "cover"), Spacer(1,57*mm)]
    cards = [("训练次数","5 次","种子 17/29/42/73/101"),("数据规模","3,333 条","1,550 episodes"),("风险 ECE","0.0104","原单模型 0.0266"),("结构 Top-1","82.9%","规则基线 63.9%")]
    card_cells=[p(f"<font color='#627D98'>{a}</font><br/><font color='#1769C2' size='16'>{b}</font><br/><font color='#627D98' size='7'>{c}</font>","card") for a,b,c in cards]
    card_table=Table([card_cells],colWidths=[doc.width/4]*4,rowHeights=[29*mm]); card_table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.white),("BOX",(0,0),(-1,-1),.6,LINE),("INNERGRID",(0,0),(-1,-1),.6,LINE),("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story += [card_table,Spacer(1,11*mm),p("结论：阶段二测试门槛 12/12 通过，阶段三工程门槛 6/6 通过。校准、回归和结构对齐明显改善；观察反事实集成排序与真实 WebArena 成功率未改善，均作为遗留问题保留。","body"),p(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}（Asia/Shanghai）","small"),PageBreak()]
    doc.handle_nextPageTemplate("body")

    seed_rows=[["变体","种子","最佳 epoch","验证选择分","测试风险 F1"]]+[[r["tag"],r["seed"],r["best_epoch"],f"{r['selection_score']:.4f}",f"{dig(r,'test','risk_f1'):.4f}"] for r in dig(multi,"runs",default=[])]
    story += [p("一、阶段二：五次独立训练与校准集成","h1"),p("数据集共 3,333 条转移、1,550 个 episode、30 个任务，按 episode 切分为训练/验证/测试 2,342/476/515，无跨 split 泄漏。仅使用验证集选择前三个成员。","body"),tbl(seed_rows,[44*mm,20*mm,28*mm,38*mm,37*mm]),p("集成测试指标","h2"),tbl([["指标","原单模型","新集成","结论"],["风险 ECE","0.0266",f"{dig(m2,'risk','macro_ece'):.4f}","改善 60.9%"],["进度 MAE","0.0612",f"{dig(m2,'progress','mae'):.4f}","改善 11.3%"],["奖励 MAE","0.0620",f"{dig(m2,'reward','mae'):.4f}","改善 9.0%"],["状态变化 F1","0.9887",f"{dig(m2,'state_delta','macro_f1_supported'):.4f}","提升"],["风险 AUROC","0.9936",f"{dig(m2,'risk','macro_auroc_supported'):.4f}","提升"],["风险 F1","0.9074",f"{dig(m2,'risk','macro_f1_supported'):.4f}","略降"]],[48*mm,34*mm,34*mm,51*mm],{1:PALE_GREEN,2:PALE_GREEN,3:PALE_GREEN,4:PALE_GREEN,5:PALE_GREEN,6:PALE_ORANGE}),p("最佳单模型种子 101 的测试风险 F1 为 0.9273；因此保留它作为分类 champion，三模型集成主要用于概率校准、不确定性估计和安全门控。","small"),PageBreak()]

    methods=dig(m3,"methods",default={})
    method_rows=[["阶梯","总体动作一致率","成功动作一致率","危险动作规避率"]]+[[name,pct(v["recorded_action_agreement"]),pct(v["positive_recorded_action_agreement"]),pct(v["risky_recorded_action_diversion"])] for name,v in methods.items()]
    horizons=dig(m3,"horizon_ablation",default={})
    horizon_rows=[["视野","动作一致率","平均延迟"]]+[[f"H={h}",pct(v["recorded_action_agreement"]),f"{v['latency_ms_mean']:.2f} ms"] for h,v in horizons.items()]
    story += [p("二、阶段三：结构对齐与有限步前瞻","h1"),p(f"动态结构对齐器测试 Top-1 从 {pct(dig(align,'baseline','test','target_recall_at_1'))} 提升到 {pct(dig(align,'selected_test','target_recall_at_1'))}，MRR 从 {dig(align,'baseline','test','mrr'):.4f} 提升到 {dig(align,'selected_test','mrr'):.4f}，Recall@3 保持 100%。","body"),tbl(method_rows,[42*mm,42*mm,42*mm,41*mm],{5:PALE_GREEN}),p("H=1/2/3 消融","h2"),tbl(horizon_rows,[45*mm,58*mm,64*mm]),p(f"515/515 条测试状态成功匹配，候选合法率 {pct(dig(m3,'candidate_schema_valid_rate'))}，安全动作 Recall@k={pct(dig(m3,'safe_recorded_action_recall_at_k'))}，解释完整率 {pct(dig(m3,'explanation_completeness'))}。W3 平均置信度 {dig(m3,'average_confidence'):.3f}，推理平均/P95={dig(m3,'latency_ms','mean'):.2f}/{dig(m3,'latency_ms','p95'):.2f} ms。","body"),p("消融结论：H=2/3 在当前数据上累积模型偏差并降低动作一致率，因此 W3 使用置信度自适应视野，不把更深想象默认视为更优。","small"),PageBreak()]

    online_m=dig(online,"world_model_agent_metrics",default={})
    story += [p("三、反事实、在线评测与诚实边界","h1"),p("观察反事实排序","h2"),tbl([["方法","验证配对准确率","测试配对准确率","测试 NDCG@2","测试 RankFlip"],["最佳单模型",pct(dig(cf,'results','validation','selected_single','pairwise_accuracy')),pct(dig(cf,'results','test','selected_single','pairwise_accuracy')),f"{dig(cf,'results','test','selected_single','ndcg_at_2'):.4f}",pct(dig(cf,'results','test','selected_single','rank_flip_rate'))],["校准集成",pct(dig(cf,'results','validation','calibrated_ensemble','pairwise_accuracy')),pct(dig(cf,'results','test','calibrated_ensemble','pairwise_accuracy')),f"{dig(cf,'results','test','calibrated_ensemble','ndcg_at_2'):.4f}",pct(dig(cf,'results','test','calibrated_ensemble','rank_flip_rate'))]],[43*mm,34*mm,34*mm,30*mm,26*mm],{1:PALE_ORANGE,2:PALE_RED}),p("验证集两种方法同为 90%，测试有效配对很少，集成反而更差。报告保留该负结果，未使用测试集调权。","small"),p("真实 WebArena Reddit 在线贯通","h2"),tbl([["指标","结果"],["固定任务","27–31，共 5 个"],["执行动作",f"{int(online_m.get('episodes',0)*online_m.get('average_steps',0))} 步"],["动作执行率",pct(online_m.get('action_execution_rate',0))],["自主成功率",pct(online_m.get('success_rate',0))],["运行失败",str(len(dig(online,'failures',default=[])))]],[63*mm,104*mm],{3:PALE_GREEN,4:PALE_RED}),p("在线链路已经把本机 BrowserGym/WebArena、SSH 转发和 GPU 三模型集成真正连通；但规则候选尚不能完成可靠的信息检索、答案生成和终止。完整多站点 WebArena 与相对 SR +10% 属于阶段四。","body"),PageBreak()]

    story += [p("四、交付物、复现入口与遗留问题","h1"),tbl([["交付物","位置"],["五个世界模型","artifacts/phase2/multiseed/"],["三模型集成清单","artifacts/phase2/world_model_ensemble_p1.json"],["结构对齐模型","artifacts/phase3/structure_aligner_best.pt"],["阶段二集成测试","data/reports/phase2_ensemble_evaluation_test_gpu.json"],["阶段三完整评测","data/reports/phase3_evaluation_ensemble_gpu.json"],["在线 WebArena 报告","data/reports/webarena_phase3_online_evaluation_gpu.json"],["结果看板","output/phase23_dashboard.html 与 site/"],["GPU 服务器","/root/autodl-tmp/agent_world_model_phase2"]],[55*mm,112*mm]),p("复现入口","h2"),tbl([["环节","命令"],["五次训练","python scripts/train_phase2_multiseed.py --config configs/phase2_world_model_multiseed.json --device cuda"],["结构训练","python scripts/train_structure_alignment.py --config configs/phase3_structure_alignment.json --device cuda"],["反事实","python scripts/evaluate_counterfactual_ranking.py --dataset-dir data/phase2_p1 --device cuda"],["阶段三","python scripts/evaluate_phase3_planner.py --config configs/phase3_planner.json --dataset-dir data/phase2_p1 --device cuda"]],[35*mm,132*mm]),p("尚未解决","h2"),tbl([["优先级","问题","下一步"],["P0","真实 WebArena SR 仍为 0%","补语义检索/作答/终止策略，扩展完整站点"],["P0","观察反事实仅 100 对，集成排序变差","扩充同状态受控替代动作"],["P1","H=2/3 累积偏差","增加多步真实轨迹和失败标签"],["P1","启发式标签占比高","人工核验并加入 WebArena 真实结果"],["P2","AndroidWorld 无真实运行环境","准备 ADB、模拟器和运行包"],["外部","GitHub 无账号/remote；Sites 未返回项目 ID","连接账户后继续发布"]],[20*mm,68*mm,79*mm],{1:PALE_RED,2:PALE_RED,3:PALE_ORANGE,4:PALE_ORANGE,5:PALE_ORANGE,6:PALE_RED}),Spacer(1,6*mm),p("报告完","body")]
    doc.build(story,canvasmaker=NumberedCanvas)
    print(OUTPUT)
    return OUTPUT


if __name__ == "__main__": build()
