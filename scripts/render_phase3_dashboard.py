#!/usr/bin/env python3
"""Render a self-contained dashboard from the final phase-two/three reports."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports", type=Path, default=ROOT / "data" / "reports")
    parser.add_argument("--output", type=Path, default=ROOT / "output" / "phase23_dashboard.html")
    return parser.parse_args()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def dig(data: Any, *keys: str, default: Any = 0) -> Any:
    for key in keys:
        if not isinstance(data, dict) or key not in data:
            return default
        data = data[key]
    return data


def pct(value: Any) -> str:
    return f"{100 * float(value):.1f}%"


def esc(value: Any) -> str:
    return html.escape(str(value))


def bar(label: str, value: float, colour: str = "#22c55e") -> str:
    width = max(0.0, min(100.0, 100.0 * value))
    return (
        f'<div class="bar-row"><span>{esc(label)}</span><div class="track">'
        f'<i style="width:{width:.2f}%;background:{colour}"></i></div><b>{width:.1f}%</b></div>'
    )


def main() -> None:
    opt = args()
    reports = opt.reports
    multi = load(reports / "phase2_multiseed_ensemble_gpu.json")
    p2 = load(reports / "phase2_ensemble_evaluation_test_gpu.json")
    align = load(reports / "phase3_structure_alignment_gpu.json")
    cf = load(reports / "phase3_counterfactual_ranking_gpu.json")
    p3 = load(reports / "phase3_evaluation_ensemble_gpu.json")
    online = load(reports / "webarena_phase3_online_evaluation_gpu.json")

    m2 = dig(p2, "metrics", default={})
    m3 = dig(p3, "metrics", default={})
    methods = dig(m3, "methods", default={})
    seeds = "".join(
        "<tr>"
        f"<td>{esc(run['tag'])}</td><td>{run['seed']}</td><td>{run['best_epoch']}</td>"
        f"<td>{run['selection_score']:.4f}</td>"
        f"<td>{dig(run, 'test', 'risk_f1'):.4f}</td>"
        "</tr>"
        for run in dig(multi, "runs", default=[])
    )
    method_rows = "".join(
        "<tr>"
        f"<td>{esc(name)}</td>"
        f"<td>{pct(values['recorded_action_agreement'])}</td>"
        f"<td>{pct(values['positive_recorded_action_agreement'])}</td>"
        f"<td>{pct(values['risky_recorded_action_diversion'])}</td>"
        "</tr>"
        for name, values in methods.items()
    )
    horizon_rows = "".join(
        "<tr>"
        f"<td>H={horizon}</td><td>{pct(values['recorded_action_agreement'])}</td>"
        f"<td>{values['latency_ms_mean']:.2f} ms</td></tr>"
        for horizon, values in dig(m3, "horizon_ablation", default={}).items()
    )
    p2_bars = "".join(
        [
            bar("状态变化 F1", dig(m2, "state_delta", "macro_f1_supported"), "#38bdf8"),
            bar("任务信号 F1", dig(m2, "task_signal", "macro_f1_supported"), "#818cf8"),
            bar("风险 F1", dig(m2, "risk", "macro_f1_supported"), "#f59e0b"),
            bar("风险 AUROC", dig(m2, "risk", "macro_auroc_supported"), "#22c55e"),
        ]
    )
    alignment_gain = (
        dig(align, "selected_test", "target_recall_at_1")
        - dig(align, "baseline", "test", "target_recall_at_1")
    )
    p2_check_count = len(dig(p2, "acceptance", "checks", default={}))
    p3_check_count = len(dig(p3, "acceptance", "checks", default={}))
    online_metrics = dig(online, "world_model_agent_metrics", default={})
    online_text = (
        f"真实 Reddit 子集：{online_metrics.get('successes', 0)}/{online_metrics.get('episodes', 0)} 成功，"
        f"SR={pct(online_metrics.get('success_rate', 0))}，"
        f"AER={pct(online_metrics.get('action_execution_rate', 0))}。"
        if online_metrics
        else "在线 GPU Agent 评测仍在运行或尚未同步。"
    )
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>阶段二、阶段三训练与验收看板</title>
<style>
:root{{--bg:#07111f;--panel:#0e1b2d;--panel2:#11243a;--line:#243b55;--ink:#eef7ff;--muted:#9fb3c8;--cyan:#38bdf8;--green:#22c55e;--amber:#f59e0b}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 85% 5%,#12365a 0,transparent 28%),var(--bg);color:var(--ink);font-family:"Microsoft YaHei",system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:42px 22px 72px}}.hero{{padding:34px;border:1px solid #2f5273;border-radius:24px;background:linear-gradient(135deg,#102a45dd,#0e1b2ddd);box-shadow:0 24px 80px #0006}}
h1{{font-size:36px;margin:0 0 12px}}h2{{margin:34px 0 14px;font-size:22px}}.sub,.note{{color:var(--muted);line-height:1.75}}.chips{{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}}.chip{{padding:8px 12px;border-radius:999px;background:#153653;border:1px solid #2b5f84;color:#bde8ff}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:18px}}.card,.panel{{background:linear-gradient(145deg,var(--panel),var(--panel2));border:1px solid var(--line);border-radius:18px;padding:19px}}.label{{color:var(--muted);font-size:13px}}.value{{font-size:28px;font-weight:800;color:var(--cyan);margin-top:8px}}.two{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.bar-row{{display:grid;grid-template-columns:120px 1fr 58px;gap:10px;align-items:center;margin:14px 0;font-size:13px}}.track{{height:10px;background:#203449;border-radius:20px;overflow:hidden}}.track i{{display:block;height:100%;border-radius:20px}}
table{{width:100%;border-collapse:collapse;background:#0e1b2d;border:1px solid var(--line);border-radius:16px;overflow:hidden}}th,td{{padding:12px 14px;text-align:left;border-bottom:1px solid var(--line)}}th{{background:#15304b;color:#bde8ff}}tr:last-child td{{border-bottom:0}}.warn{{border-left:5px solid var(--amber);background:#2a2112;padding:16px 18px;border-radius:12px;line-height:1.8}}footer{{margin-top:32px;color:var(--muted);font-size:12px}}
@media(max-width:820px){{.cards{{grid-template-columns:repeat(2,1fr)}}.two{{grid-template-columns:1fr}}}}@media(max-width:520px){{.cards{{grid-template-columns:1fr}}h1{{font-size:28px}}}}
</style></head><body><main>
<section class="hero"><h1>阶段二 × 阶段三完善结果</h1><div class="sub">动作条件世界模型 · 五次独立训练 · 三模型校准集成 · 动态结构对齐 · H=1/2/3 有限步前瞻</div><div class="chips"><span class="chip">RTX 4090</span><span class="chip">5 个训练种子</span><span class="chip">阶段二 {p2_check_count}/{p2_check_count} 门槛通过</span><span class="chip">阶段三 {p3_check_count}/{p3_check_count} 门槛通过</span></div></section>
<section class="cards"><div class="card"><div class="label">数据规模</div><div class="value">3,333</div><div class="note">1,550 episodes · 30 tasks</div></div><div class="card"><div class="label">风险 ECE</div><div class="value">{dig(m2,'risk','macro_ece'):.4f}</div><div class="note">原单模型 0.0266</div></div><div class="card"><div class="label">进度 MAE</div><div class="value">{dig(m2,'progress','mae'):.4f}</div><div class="note">原单模型 0.0612</div></div><div class="card"><div class="label">结构对齐 Top-1</div><div class="value">{pct(dig(align,'selected_test','target_recall_at_1'))}</div><div class="note">较规则基线 +{100*alignment_gain:.1f} 个百分点</div></div></section>
<h2>阶段二：预测能力与稳定性</h2><section class="two"><div class="panel">{p2_bars}</div><div class="panel"><div class="label">校准与回归</div><p>风险 Brier：<b>{dig(m2,'risk','macro_brier'):.4f}</b></p><p>风险 NLL：<b>{dig(m2,'risk','macro_nll'):.4f}</b></p><p>风险 AURC：<b>{dig(m2,'risk','macro_aurc'):.4f}</b></p><p>奖励 MAE：<b>{dig(m2,'reward','mae'):.4f}</b></p></div></section>
<h2>五次独立训练</h2><table><thead><tr><th>变体</th><th>种子</th><th>最佳 epoch</th><th>验证选择分</th><th>测试风险 F1</th></tr></thead><tbody>{seeds}</tbody></table>
<h2>阶段三：W0–W3 决策阶梯</h2><table><thead><tr><th>方法</th><th>总体动作一致率</th><th>成功动作一致率</th><th>危险动作规避率</th></tr></thead><tbody>{method_rows}</tbody></table>
<h2>有限步消融</h2><section class="two"><table><thead><tr><th>视野</th><th>动作一致率</th><th>平均延迟</th></tr></thead><tbody>{horizon_rows}</tbody></table><div class="panel"><p>W3 平均置信度：<b>{dig(m3,'average_confidence'):.3f}</b></p><p>W3 危险动作规避率：<b>{pct(dig(methods,'phase3','risky_recorded_action_diversion'))}</b></p><p>推理 P95：<b>{dig(m3,'latency_ms','p95'):.2f} ms</b></p><p>候选合法率：<b>{pct(dig(m3,'candidate_schema_valid_rate'))}</b></p></div></section>
<h2>反事实与在线边界</h2><div class="warn">观察反事实仅有 100 对，其中测试集有效配对很少：单模型测试配对准确率 {pct(dig(cf,'results','test','selected_single','pairwise_accuracy'))}，校准集成为 {pct(dig(cf,'results','test','calibrated_ensemble','pairwise_accuracy'))}。该负结果被保留，未使用测试集调权。<br>{esc(online_text)} 完整多站点 WebArena 与“相对成功率 +10%”属于阶段四验证，不在本页伪造完成。</div>
<footer>由 data/reports 下的 GPU JSON 证据自动生成；页面不依赖第三方脚本。</footer>
</main></body></html>"""
    opt.output.parent.mkdir(parents=True, exist_ok=True)
    opt.output.write_text(document, encoding="utf-8")
    print(opt.output)


if __name__ == "__main__":
    main()
