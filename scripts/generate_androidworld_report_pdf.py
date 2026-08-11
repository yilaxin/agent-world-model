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
    checks = preflight.get("checks", {})
    before = smoke.get("before", {})
    after = smoke.get("after", {})
    axtree = (before.get("axtree") or "").splitlines()

    story = [
        para("ANDROIDWORLD · 冒烟验收", "kicker"),
        para("AndroidWorld 真实迁移：冒烟验收汇报", "title"),
        para("在 AutoDL RTX 4090 容器中完成官方 AndroidWorld 0.1.0 软件仿真设备上的真实 <b>reset → action → state</b> 冒烟测试；无障碍树含 18 个真实 UI 元素。任务级基线/规划器对比仍需 KVM 加速主机，因此本报告结论为「基础冒烟通过、任务评测待办」，不声称迁移完成。", "lead"),
        para("一、背景与目标", "h1"),
        para("进度看板 P2 项「AndroidWorld 真实迁移」此前状态为「运行时就绪 / 冒烟待验」：官方软件栈、API 33 模拟器与预检均已就绪，但真实环境交互尚未跑通。本次目标是完成真实 <b>reset → action → state</b> 冒烟并保留可审计证据（状态、动作、无障碍树、截图哈希）。", "body"),
        para("二、运行环境", "h1"),
        Table(
            [
                ["项目", "配置"],
                ["主机", "AutoDL GPU 容器（RTX 4090，软件仿真；无 /dev/kvm）"],
                ["AndroidWorld", "官方 0.1.0（固定上游提交）"],
                ["Python", "3.11.15（conda 环境 android_world）"],
                ["Android SDK", "platform-tools、emulator 37.1.11、build-tools 33.0.2、platforms;android-33"],
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
                ["/dev/kvm", "不可用（软件仿真诊断）"],
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
        para("五、结论与遗留问题", "h1"),
        para("真实 reset、真实动作执行与真实状态采集已在软件仿真设备上通过，Agent 可感知完整屏幕无障碍树。当前状态从「运行时就绪 / 冒烟待验」更新为「基础冒烟通过 / 任务评测待办」。", "callout"),
        para("尚未完成（不能省略的硬门槛）：", "h2"),
        para("• 任务级评估：至少一个确定性任务在反应式基线与阶段三规划器下对比，产出任务成功率、动作执行率、平均步数；", "bullet"),
        para("• 加速环境：容器无 /dev/kvm，软件仿真仅适合诊断；建议在 KVM 主机或 Windows WHPX 模拟器上完成正式任务评测；", "bullet"),
        para("• 真机/其他设备泛化：当前仅验证 Pixel 6 API 33 一条设备路径。", "bullet"),
        para("六、建议下一步", "h1"),
        para("1. 将模拟器迁移到 KVM 主机（或本机 WHPX），复跑预检与冒烟；", "bullet"),
        para("2. 运行 android_world 官方确定性任务，分别记录反应式基线与阶段三规划器的轨迹、奖励与终止信号；", "bullet"),
        para("3. 把任务级结果回写数据/报告 JSON，更新看板与 PDF 后再声明迁移完成。", "bullet"),
    ]

    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    doc.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    print(OUTPUT)


if __name__ == "__main__":
    build()
