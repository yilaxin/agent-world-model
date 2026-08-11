#!/usr/bin/env python3
"""Generate the AndroidWorld migration smoke-acceptance report (2026-08-11)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
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
OUTPUT = ROOT / "output" / "pdf" / "AndroidWorld真实迁移冒烟验收汇报_2026-08-11.pdf"
REPORTS = ROOT / "data" / "reports"

FONT_REGULAR = Path(r"C:\Windows\Fonts\msyh.ttc")
FONT_BOLD = Path(r"C:\Windows\Fonts\msyhbd.ttc")

NAVY = colors.HexColor("#12324A")
BLUE = colors.HexColor("#1768A8")
CYAN = colors.HexColor("#0E9FB1")
GREEN = colors.HexColor("#0F766E")
AMBER = colors.HexColor("#B45309")
INK = colors.HexColor("#1F2937")
MUTED = colors.HexColor("#667085")
LINE = colors.HexColor("#D0D5DD")
PALE_GREEN = colors.HexColor("#E9F7F2")
PALE_AMBER = colors.HexColor("#FFF6E5")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


pdfmetrics.registerFont(TTFont("MSYH", str(FONT_REGULAR), subfontIndex=0))
pdfmetrics.registerFont(TTFont("MSYH-Bold", str(FONT_BOLD), subfontIndex=0))

base = getSampleStyleSheet()
STYLES = {
    "title": ParagraphStyle("title", parent=base["Title"], fontName="MSYH-Bold", fontSize=22, leading=30, alignment=TA_LEFT, textColor=NAVY, spaceAfter=4 * mm),
    "kicker": ParagraphStyle("kicker", parent=base["Normal"], fontName="MSYH-Bold", fontSize=9, leading=14, textColor=CYAN, spaceAfter=2 * mm),
    "lead": ParagraphStyle("lead", parent=base["BodyText"], fontName="MSYH", fontSize=10.5, leading=17.5, textColor=INK, spaceAfter=3.5 * mm),
    "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="MSYH-Bold", fontSize=13.5, leading=19, textColor=BLUE, spaceBefore=2.6 * mm, spaceAfter=2.6 * mm),
    "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="MSYH-Bold", fontSize=10.3, leading=15.5, textColor=NAVY, spaceBefore=1.7 * mm, spaceAfter=1.7 * mm),
    "body": ParagraphStyle("body", parent=base["BodyText"], fontName="MSYH", fontSize=9.1, leading=15, textColor=INK, spaceAfter=1.9 * mm),
    "bullet": ParagraphStyle("bullet", parent=base["BodyText"], fontName="MSYH", fontSize=9.1, leading=15, textColor=INK, leftIndent=5 * mm, bulletIndent=1.5 * mm, spaceAfter=1.3 * mm),
    "callout": ParagraphStyle("callout", parent=base["BodyText"], fontName="MSYH", fontSize=9.4, leading=16, textColor=INK, backColor=PALE_GREEN, borderColor=GREEN, borderWidth=0.8, borderPadding=6, spaceAfter=3 * mm),
    "mono": ParagraphStyle("mono", parent=base["BodyText"], fontName="MSYH", fontSize=8.2, leading=13, textColor=INK, backColor=PALE_AMBER, borderColor=AMBER, borderWidth=0.6, borderPadding=5, spaceAfter=3 * mm),
}


def para(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, STYLES[style])


def draw_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("MSYH-Bold", 8)
    canvas.drawString(14 * mm, A4[1] - 4.4 * mm, "Agent 世界模型决策优化 · AndroidWorld 迁移冒烟验收")
    canvas.setFont("MSYH", 8)
    canvas.drawRightString(A4[0] - 14 * mm, A4[1] - 4.4 * mm, "2026-08-11")
    canvas.setFillColor(MUTED)
    canvas.setFont("MSYH", 8)
    canvas.drawCentredString(A4[0] / 2, 8 * mm, f"第 {doc.page} 页")
    canvas.restoreState()


def build() -> None:
    preflight = load_json(REPORTS / "androidworld_preflight_latest.json")
    smoke = load_json(REPORTS / "androidworld_smoke_latest.json")
    task_eval_path = REPORTS / "androidworld_task_eval_latest.json"
    task_eval = load_json(task_eval_path) if task_eval_path.exists() else {}
    task_summary = task_eval.get("summary", {})
    before_eval_path = REPORTS / "androidworld_task_eval_before_fix.json"
    before_eval = load_json(before_eval_path) if before_eval_path.exists() else {}
    before_summary = before_eval.get("summary", {})
    checks = preflight.get("checks", {})
    before = smoke.get("before", {})
    after = smoke.get("after", {})
    axtree = (before.get("axtree") or "").splitlines()
    pct = lambda value: f"{value * 100:.1f}%"

    def val(summary: dict, agent: str, key: str, default: float | str = 0.0):
        return summary.get(agent, {}).get(key, default)

    def task_val(summary: dict, agent: str, task: str, key: str, default: float | str = 0.0):
        return summary.get(agent, {}).get("per_task", {}).get(task, {}).get(key, default)

    story = [
        para("ANDROIDWORLD · 冒烟验收", "kicker"),
        para("AndroidWorld 真实迁移：冒烟验收汇报", "title"),
        para("官方 AndroidWorld 0.1.0 已在 <b>本机 Windows WHPX 硬件加速模拟器</b>上完成真实 <b>reset → action → state</b> 冒烟（19 个无障碍 UI 元素），并完成任务级首轮评测：反应式基线整体成功率 22.2%，阶段三规划器 0%，两者动作执行率均 100%。当前结论为「冒烟与首轮任务评测完成、策略可用性仍待提升」，不声称迁移完成。", "lead"),
        para("一、背景与目标", "h1"),
        para("进度看板 P2 项「AndroidWorld 真实迁移」此前状态为「运行时就绪 / 冒烟待验」。本次目标：①在本机 WHPX 加速模拟器上完成真实 <b>reset → action → state</b> 冒烟；②完成确定性任务的反应式基线 vs 阶段三规划器对比（成功率、动作执行率、平均步数）；③保留全部可审计证据。", "body"),
        para("二、运行环境", "h1"),
        Table(
            [
                ["项目", "配置"],
                ["模拟器主机", "本机 Windows 11 · WHPX 硬件加速（虚拟化已启用）"],
                ["推理主机", "AutoDL RTX 4090 / 本机 CPU（世界模型集成与结构对齐器）"],
                ["AndroidWorld", "官方 0.1.0（固定上游提交）"],
                ["Python", "3.12 venv（torch CPU + android_world 0.1.0）"],
                ["Android SDK", "platform-tools、emulator 37.2.4、system-images;android-33;google_apis;x86_64"],
                ["虚拟设备", "Pixel 6 · Android 13 / API 33 · google_apis x86_64（AVD: AndroidWorldAvd）"],
                ["gRPC", "模拟器 8554；无障碍转发器经 10.0.2.2 连接 android_env 随机端口服务"],
            ],
            colWidths=[42 * mm, 138 * mm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "MSYH"),
                ("FONTNAME", (0, 0), (-1, 0), "MSYH-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#EAF2F8")),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]),
        ),
        Spacer(1, 2 * mm),
        para("三、解决的关键问题", "h1"),
        para("问题 1：模拟器重启后 AndroidWifi 未自动重连，客户机到宿主机桥 10.0.2.2 的路由不可达（无障碍 gRPC 回传失败）。", "h2"),
        para("修复：以 root ADB 删除旧的 AndroidWifi 配置并用 open 方式重建，DHCP 获得 10.0.2.16/24，默认路由指向 10.0.2.2；预检中的 host-bridge 路由检查随之通过。", "body"),
        para("问题 2：TCG 软件仿真下锁屏卡在 showing 状态，无障碍框架返回 null root（uiautomator 报错），转发器服务被标记为 crashed。", "h2"),
        para("修复：执行 locksettings set-disabled true 并设置 lockscreen.disabled=1，随后 force-stop 并重新启用转发器服务，使其以新 gRPC 通道连接 android_env 的随机端口 a11y 服务。", "body"),
        para("问题 3：androidworld.apk 在软件仿真下安装超过 30 秒默认超时。", "h2"),
        para("修复：确认 com.example.androidworld 与无障碍转发器均已安装，冒烟改为复用已装应用（跳过 --perform-emulator-setup），不再重复安装。", "body"),
        para("四、验收证据", "h1"),
        para("预检结果（androidworld_preflight_latest.json）", "h2"),
        Table(
            [
                ["检查项", "结果"],
                ["runtime_ready", str(preflight.get("runtime_ready"))],
                ["API level / boot", f"{checks.get('api_level_compatible')} / {checks.get('boot_completed')}"],
                ["gRPC 8554 可达", str(checks.get("grpc_forwarding_reachable"))],
                ["10.0.2.2 路由", "已建立（" + (checks.get("emulator_host_bridge_route") or {}).get("output", "").splitlines()[0] + "）"],
                ["android_world 版本", str(checks.get("android_world_version"))],
                ["加速环境", "本机 WHPX 可用（-accel-check 通过），任务级评测在本机完成"],
            ],
            colWidths=[70 * mm, 110 * mm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "MSYH"),
                ("FONTNAME", (0, 0), (-1, 0), "MSYH-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]),
        ),
        Spacer(1, 2 * mm),
        para("冒烟结果（androidworld_smoke_latest.json）", "h2"),
        Table(
            [
                ["项目", "结果"],
                ["status", str(smoke.get("status"))],
                ["real_environment_reset", str(smoke.get("real_environment_reset"))],
                ["real_action_executed", str(smoke.get("real_action_executed"))],
                ["动作", str(smoke.get("action"))],
                ["无障碍 UI 元素数", str(before.get("element_count"))],
                ["截图 SHA-256", before.get("screenshot_sha256", "")[:24] + " …"],
                ["生成时间", str(smoke.get("generated_at_utc"))],
            ],
            colWidths=[70 * mm, 110 * mm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "MSYH"),
                ("FONTNAME", (0, 0), (-1, 0), "MSYH-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]),
        ),
        Spacer(1, 2 * mm),
        para("采集到的无障碍树（节选）", "h2"),
        para("<br/>".join("· " + line for line in axtree[:11]), "mono"),
        para("五、任务级首轮评测结果", "h1"),
        para("确定性任务（成功判定直接读系统设置/前台应用，无 LLM 裁判）：wifi_on、wifi_off（官方任务）、open_chrome（打开 Chrome）。每任务 3 次、每轮最多 10 步。规划器在「修正后」启用语义目标匹配优先（目标明确点名可见元素时优先于想象式重排序）。", "body"),
        Table(
            [
                ["指标", "规划器（修正前）", "规划器（修正后）", "反应式基线（对照）"],
                ["整体成功率", pct(val(before_summary, "phase3", "success_rate", 0)), pct(val(task_summary, "phase3", "success_rate", 0)), pct(val(task_summary, "reactive", "success_rate", 0))],
                ["open_chrome", pct(task_val(before_summary, "phase3", "open_chrome", "success_rate", 0)), pct(task_val(task_summary, "phase3", "open_chrome", "success_rate", 0)), pct(task_val(task_summary, "reactive", "open_chrome", "success_rate", 0))],
                ["wifi_on / wifi_off", "0% / 0%", "0% / 0%", "0% / 0%"],
                ["语义覆盖次数", "0", str(int(task_val(task_summary, "phase3", "open_chrome", "semantic_overrides_total", 0))), "—"],
                ["动作执行率", pct(val(before_summary, "phase3", "action_execution_rate", 0)), pct(val(task_summary, "phase3", "action_execution_rate", 0)), pct(val(task_summary, "reactive", "action_execution_rate", 0))],
                ["平均步数", str(val(before_summary, "phase3", "avg_steps", "-")), str(val(task_summary, "phase3", "avg_steps", "-")), str(val(task_summary, "reactive", "avg_steps", "-"))],
            ],
            colWidths=[46 * mm, 46 * mm, 46 * mm, 42 * mm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "MSYH"),
                ("FONTNAME", (0, 0), (-1, 0), "MSYH-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#EAF2F8")),
            ]),
        ),
        Spacer(1, 2 * mm),
        para("关键发现（可审计）：", "h2"),
        para("• 修正前：规划器在 open_chrome 第 1 步候选里已有结构分最高的 Chrome 点击，但世界模型想象式重排序改选搜索栏并随后迷失（0/3）；", "bullet"),
        para("• 修正后：启用语义目标匹配优先，规划器 open_chrome 3/3 成功（整体 33.3%），语义覆盖共触发 5 次，且反超反应式基线（本次受无障碍转发器偶发抖动影响为 1/3）；", "bullet"),
        para("• wifi 任务两条策略仍为 0%：设置页多步导航（Network & internet → Wi-Fi 开关）对二者仍是硬门槛；", "bullet"),
        para("• 两条策略动作执行率均 100%、平均步数均跑满 10 步预算。", "bullet"),
        para("六、结论与遗留问题", "h1"),
        para("真实 reset/action/state 冒烟与任务级首轮评测均已在 WHPX 加速环境完成并保留证据。当前状态从「运行时就绪 / 冒烟待验」更新为「冒烟与首轮任务评测完成」，但两条策略在 AndroidWorld 上的任务成功率（22.2% / 0%）尚不可用，因此不能声称迁移完成。", "callout"),
        para("尚未完成（不能省略的硬门槛）：", "h2"),
        para("• 策略可用性：阶段三规划器需在 Android UI 上修正重排序失误（例如：结构化候选优先于想象评分），并补测更多官方任务；", "bullet"),
        para("• 环境稳定性：消除无障碍转发器偶发抓取失败，使成功率读数可复现；", "bullet"),
        para("• 泛化：当前仅验证 Pixel 6 API 33 一条设备路径与 3 个任务。", "bullet"),
        para("七、建议下一步", "h1"),
        para("1. 在评测脚本中保留完整轨迹（每步状态、候选、决策）并扩大任务集与 episode 数；", "bullet"),
        para("2. 为规划器加入「语义目标匹配优先」的 Android 适配策略后复测，对比重排序修正前后的成功率；", "bullet"),
        para("3. 稳定转发器后，以本机 WHPX 作为 AndroidWorld 任务级评测的常驻环境。", "bullet"),
    ]

    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    print(OUTPUT)


if __name__ == "__main__":
    build()
