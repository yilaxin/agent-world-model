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
    "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="MSYH-Bold", fontSize=13, leading=18.5, textColor=BLUE, spaceBefore=2.2 * mm, spaceAfter=2.2 * mm),
    "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="MSYH-Bold", fontSize=10.2, leading=15, textColor=NAVY, spaceBefore=1.4 * mm, spaceAfter=1.4 * mm),
    "body": ParagraphStyle("body", parent=base["BodyText"], fontName="MSYH", fontSize=9, leading=14.5, textColor=INK, spaceAfter=1.6 * mm),
    "bullet": ParagraphStyle("bullet", parent=base["BodyText"], fontName="MSYH", fontSize=9, leading=14.5, textColor=INK, leftIndent=5 * mm, bulletIndent=1.5 * mm, spaceAfter=1 * mm),
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
    wifi_seq_path = REPORTS / "androidworld_task_eval_wifi_sequence.json"
    wifi_seq = load_json(wifi_seq_path) if wifi_seq_path.exists() else {}
    wifi_seq_summary = wifi_seq.get("summary", {})
    wifi_seq_ep10_path = REPORTS / "androidworld_task_eval_wifi_sequence_ep10.json"
    wifi_seq_ep10 = load_json(wifi_seq_ep10_path) if wifi_seq_ep10_path.exists() else {}
    wifi_seq_ep10_summary = wifi_seq_ep10.get("summary", {})
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
        para("• 网络：模拟器重启后 AndroidWifi 未自动重连、到宿主机桥 10.0.2.2 路由不可达 → 重建 WiFi 配置，DHCP 恢复 10.0.2.16/24；", "bullet"),
        para("• 锁屏：TCG/WHPX 下锁屏卡在 showing 导致无障碍框架拿不到根节点、转发器崩溃 → locksettings set-disabled true + 重启转发器服务；", "bullet"),
        para("• 安装/路径：androidworld.apk 安装超时与中文路径乱码 → 复用已装应用、SDK/AVD 迁移到 ASCII 路径、截图像素改为 Unicode 安全写入。", "bullet"),
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
        para("<br/>".join("· " + line for line in axtree[:6]), "mono"),
        para("五、任务级评测结果（扩展任务集）", "h1"),
        para("确定性任务（成功判定直接读系统设置/前台应用，无 LLM 裁判）：wifi_on、wifi_off（官方任务）+ 5 个打开应用任务（Chrome/日历/图库/信息/Gmail；相册因 AVD 无 Google 账号会跳 GMS 错误页，替换为无需账号的图库）。每任务 5 次、每轮最多 12 步；启用语义目标匹配、设置序列导航与启动器翻页策略。", "body"),
        Table(
            [
                ["任务", "反应式基线", "阶段三规划器"],
                ["整体成功率", pct(val(task_summary, "reactive", "success_rate", 0)), pct(val(task_summary, "phase3", "success_rate", 0))],
                ["open_chrome", pct(task_val(task_summary, "reactive", "open_chrome", "success_rate", 0)), pct(task_val(task_summary, "phase3", "open_chrome", "success_rate", 0))],
                ["open_messages", pct(task_val(task_summary, "reactive", "open_messages", "success_rate", 0)), pct(task_val(task_summary, "phase3", "open_messages", "success_rate", 0))],
                ["open_gmail", pct(task_val(task_summary, "reactive", "open_gmail", "success_rate", 0)), pct(task_val(task_summary, "phase3", "open_gmail", "success_rate", 0))],
                ["open_gallery", pct(task_val(task_summary, "reactive", "open_gallery", "success_rate", 0)), pct(task_val(task_summary, "phase3", "open_gallery", "success_rate", 0))],
                ["open_calendar", pct(task_val(task_summary, "reactive", "open_calendar", "success_rate", 0)), pct(task_val(task_summary, "phase3", "open_calendar", "success_rate", 0))],
                ["wifi_on", pct(task_val(task_summary, "reactive", "wifi_on", "success_rate", 0)), pct(task_val(task_summary, "phase3", "wifi_on", "success_rate", 0))],
                ["wifi_off", pct(task_val(task_summary, "reactive", "wifi_off", "success_rate", 0)), pct(task_val(task_summary, "phase3", "wifi_off", "success_rate", 0))],
                ["动作执行率", pct(val(task_summary, "reactive", "action_execution_rate", 0)), pct(val(task_summary, "phase3", "action_execution_rate", 0))],
                ["平均步数", str(val(task_summary, "reactive", "avg_steps", "-")), str(val(task_summary, "phase3", "avg_steps", "-"))],
                ["语义覆盖次数", "0", str(sum(int(task_val(task_summary, "phase3", t, "semantic_overrides_total", 0)) for t in ["open_chrome", "open_photos", "open_messages", "open_gmail"]))],
                ["转发器恢复次数", str(sum(int(task_val(task_summary, "reactive", t, "recoveries_total", 0)) for t in task_summary.get("reactive", {}).get("per_task", {}))), str(sum(int(task_val(task_summary, "phase3", t, "recoveries_total", 0)) for t in task_summary.get("phase3", {}).get("per_task", {})))],
                ["稀疏状态步数", str(sum(int(task_val(task_summary, "reactive", t, "sparse_states_total", 0)) for t in task_summary.get("reactive", {}).get("per_task", {}))), str(sum(int(task_val(task_summary, "phase3", t, "sparse_states_total", 0)) for t in task_summary.get("phase3", {}).get("per_task", {})))],
            ],
            colWidths=[70 * mm, 55 * mm, 55 * mm],
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
        para("• 最终 7 任务 × 5 次：反应式基线整体 91.4%，阶段三规划器 91.4%（此前 42.9% / 45.7%），动作执行率均 100%、平均步数均跑满 12 步预算；", "bullet"),
        para("• 启动器翻页策略修复日历（0%→80%，进入应用抽屉查找）与信息（规划器 0%→100%）；图库替换相册后两条策略均 100%（相册在无 Google 账号的 AVD 上会跳 GMS 错误页，属环境阻塞）；", "bullet"),
        para("• 设置序列导航后 wifi 任务 10 次复测 70–90%（本次 5 次复测 wifi_off 反应式/规划器 80%/100%、wifi_on 80%/60%）；", "bullet"),
        para("• 稳定性：转发器快速恢复（重启后立即重播 gRPC 配置）加进程健康检查，全程无崩溃，每任务恢复 0–1 次、稀疏状态步数 0–5；逐步骤轨迹已落盘。", "bullet"),
        para("六、序列级导航（wifi 多步任务）", "h1"),
        para("针对「进入设置 → Network & internet → Internet → Wi-Fi 开关」的多步导航，新增 opt-in 的序列策略（settings_sequence）：识别目标分区行、未知子页自动返回、开关点击防重复，并记录每步轨迹（状态、动作、决策）到 JSONL。稳定复测每任务 10 次、每轮最多 12 步。", "body"),
        Table(
            [
                ["任务", "无序列（基线）", "启用序列导航"],
                ["wifi_on · 反应式", pct(task_val(task_summary, "reactive", "wifi_on", "success_rate", 0)), pct(task_val(wifi_seq_ep10_summary, "reactive", "wifi_on", "success_rate", 0))],
                ["wifi_off · 反应式", pct(task_val(task_summary, "reactive", "wifi_off", "success_rate", 0)), pct(task_val(wifi_seq_ep10_summary, "reactive", "wifi_off", "success_rate", 0))],
                ["wifi_on · 规划器", pct(task_val(task_summary, "phase3", "wifi_on", "success_rate", 0)), pct(task_val(wifi_seq_ep10_summary, "phase3", "wifi_on", "success_rate", 0))],
                ["wifi_off · 规划器", pct(task_val(task_summary, "phase3", "wifi_off", "success_rate", 0)), pct(task_val(wifi_seq_ep10_summary, "phase3", "wifi_off", "success_rate", 0))],
                ["动作执行率", "100%", "100%"],
                ["序列决策步数", "—", "78–96 / 任务"],
            ],
            colWidths=[70 * mm, 55 * mm, 55 * mm],
            style=TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "MSYH"),
                ("FONTNAME", (0, 0), (-1, 0), "MSYH-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#EAF2F8")),
            ]),
        ),
        Spacer(1, 2 * mm),
        para("结论：序列级语义支持把 wifi 任务从 0–20% 提升到 70–90%（10 次稳定复测），且两条策略同时受益；逐步骤轨迹已保存（40 个 JSONL）。剩余失败主要来自无障碍转发器偶发抓取失败（每任务稀疏状态步数 4–9、恢复 2–3 次）。", "callout"),
        para("七、结论与遗留问题", "h1"),
        para("本机 WHPX 上已完成冒烟、7 任务扩展评测与 wifi 序列级导航实验：反应式基线整体 42.9%、规划器 45.7%，启用序列导航后 wifi 任务 60–80%。策略在简单打开应用与设置多步导航两类任务上均已具备可用性，但部分任务（日历、信息）与转发器稳定性仍是硬门槛，不能声称迁移完成。", "callout"),
        para("尚未完成（不能省略的硬门槛）：", "h2"),
        para("• 策略缺口：日历（按钮不在默认主页，需要翻页）与信息（规划器 12 次语义覆盖仍未进入前台）两条任务仍为 0%；", "bullet"),
        para("• 环境稳定性：无障碍转发器偶发抓取失败仍会吞掉部分 episode，需进一步稳定（如转发器进程健康监控）；", "bullet"),
        para("• 泛化：当前仅验证 Pixel 6 API 33 一条设备路径。", "bullet"),
        para("建议下一步：", "h2"),
        para("① 为日历任务加入首页翻页（swipe）支持，为信息任务排查点击目标与前台判定；", "bullet"),
        para("② 把序列导航策略扩展到亮度等其它官方设置任务，并扩大 episode 数到 10 以进一步压稳读数；", "bullet"),
        para("③ 稳定转发器后，以本机 WHPX 作为 AndroidWorld 任务级评测的常驻环境。", "bullet"),
    ]

    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    print(OUTPUT)


if __name__ == "__main__":
    build()
