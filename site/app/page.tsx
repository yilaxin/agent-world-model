import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "阶段二、阶段三训练与验收看板",
  description: "动作条件世界模型的多种子训练、校准集成与有限步决策实验结果。",
};

const seeds = [
  ["risk_balanced_b", "101", "28", "0.8118", "0.9273"],
  ["base_a", "17", "36", "0.8058", "0.8774"],
  ["base_b", "42", "35", "0.8058", "0.9074"],
  ["risk_balanced_a", "29", "35", "0.8022", "0.8824"],
  ["regularized", "73", "40", "0.7990", "0.8939"],
];

const methods = [
  ["B0 · reactive", "64.1%", "74.0%", "45.8%"],
  ["W0 · one-step", "34.2%", "68.8%", "65.8%"],
  ["W1 · structure", "34.0%", "68.8%", "65.5%"],
  ["W2 · multiscale", "21.2%", "58.4%", "88.7%"],
  ["W3 · adaptive", "35.7%", "64.9%", "66.5%"],
];

const horizons = [
  ["H=1", "35.3%", "5.32 ms"],
  ["H=2", "23.9%", "13.58 ms"],
  ["H=3", "21.2%", "34.45 ms"],
];

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return <article className="metric-card"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

function Bar({ label, value, colour }: { label: string; value: number; colour: string }) {
  return <div className="bar-row"><span>{label}</span><div className="track"><i style={{ width: `${value}%`, background: colour }} /></div><b>{value.toFixed(1)}%</b></div>;
}

export default function Home() {
  return (
    <main>
      <section className="hero">
        <p className="eyebrow">AGENT WORLD MODEL · VERIFIED GPU RUN</p>
        <h1>阶段二 × 阶段三完善结果</h1>
        <p className="subtitle">动作条件世界模型 · 五次独立训练 · 三模型校准集成 · 动态结构对齐 · H=1/2/3 有限步前瞻</p>
        <div className="chips"><span>RTX 4090</span><span>5 个训练种子</span><span>阶段二 12/12 门槛通过</span><span>阶段三 6/6 门槛通过</span></div>
      </section>

      <section className="metric-grid" aria-label="核心指标">
        <Metric label="数据规模" value="3,333" note="1,550 episodes · 30 tasks" />
        <Metric label="风险 ECE" value="0.0104" note="原单模型 0.0266" />
        <Metric label="进度 MAE" value="0.0543" note="原单模型 0.0612" />
        <Metric label="结构对齐 Top-1" value="82.9%" note="规则基线 63.9%" />
      </section>

      <h2>阶段二：预测能力与稳定性</h2>
      <section className="split">
        <article className="panel bars">
          <Bar label="状态变化 F1" value={99.1} colour="#38bdf8" />
          <Bar label="任务信号 F1" value={98.5} colour="#818cf8" />
          <Bar label="风险 F1" value={90.5} colour="#f59e0b" />
          <Bar label="风险 AUROC" value={99.4} colour="#22c55e" />
        </article>
        <article className="panel detail-list"><span className="panel-label">校准与回归</span><p>风险 Brier <b>0.0121</b></p><p>风险 NLL <b>0.0440</b></p><p>风险 AURC <b>0.0039</b></p><p>奖励 MAE <b>0.0564</b></p></article>
      </section>

      <h2>五次独立训练</h2>
      <div className="table-wrap"><table><thead><tr><th>变体</th><th>种子</th><th>最佳 epoch</th><th>验证选择分</th><th>测试风险 F1</th></tr></thead><tbody>{seeds.map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody></table></div>

      <h2>阶段三：W0–W3 决策阶梯</h2>
      <div className="table-wrap"><table><thead><tr><th>方法</th><th>总体动作一致率</th><th>成功动作一致率</th><th>危险动作规避率</th></tr></thead><tbody>{methods.map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody></table></div>

      <h2>有限步消融</h2>
      <section className="split"><div className="table-wrap"><table><thead><tr><th>视野</th><th>动作一致率</th><th>平均延迟</th></tr></thead><tbody>{horizons.map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody></table></div><article className="panel detail-list"><span className="panel-label">W3 运行特征</span><p>平均置信度 <b>0.690</b></p><p>危险动作规避率 <b>66.5%</b></p><p>推理 P95 <b>64.03 ms</b></p><p>候选合法率 <b>100%</b></p></article></section>

      <h2>边界与遗留问题</h2>
      <section className="warning"><b>结果诚实边界</b><p>观察反事实仅有 100 对；测试有效配对中，单模型准确率为 61.5%，校准集成为 53.8%，未用测试集调权。GPU Agent 已贯通本机真实 Reddit/WebArena：30/30 动作执行成功，但 5 个固定任务自主成功率仍为 0%。完整多站点 WebArena 与“相对 SR +10%”需在阶段四验证。</p></section>

      <footer><span>Agent 世界模型决策优化</span><span>生成于 2026-08-08 · 证据来自 GPU JSON 报告</span></footer>
    </main>
  );
}
