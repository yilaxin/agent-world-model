import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "阶段二、阶段三训练与验收看板",
  description: "动作条件世界模型的数据、训练、反事实排序与有限步决策验收状态。",
};

const seedRuns = [
  ["risk_balanced_b", "101", "28", "0.8118", "0.9273"],
  ["base_a", "17", "36", "0.8058", "0.8774"],
  ["base_b", "42", "35", "0.8058", "0.9074"],
  ["risk_balanced_a", "29", "35", "0.8022", "0.8824"],
  ["regularized", "73", "40", "0.7990", "0.8939"],
];

const issueRows = [
  ["P0", "观察反事实", "100 对旧数据", "3600 对采集方案、成对排序损失和配对 Bootstrap 已实现", "待 GPU 环境执行"],
  ["P1", "人工复核", "启发式标签为主", "已导出 300 条高风险复核队列；仅 approved 标签可回灌", "0 条已批准，待人工填写"],
  ["P1", "H=2/3 累积偏差", "H2=124、H3=59", "真实连续轨迹评估与专用多步/终止失败采集已接入", "新数据门未通过"],
  ["P0", "WebArena 在线成功率", "5 个任务 SR=0%", "论坛任务查询候选、回车提交与 12 步预算已加入", "须在线重评；+10% 属阶段四"],
  ["P2", "AndroidWorld", "仅适配器", "增强 ADB/模拟器/KVM/gRPC 预检及迁移手册", "缺 ADB、模拟器和运行包"],
  ["外部", "GitHub / Sites", "曾缺 remote / 项目 ID", "GitHub remote 与 Sites 项目 ID 已绑定", "已解决"],
];

const horizons = [
  ["H=1", "231", "0.000244", "34", "0"],
  ["H=2", "124", "0.000350", "11", "0"],
  ["H=3", "59", "0.000460", "5", "0"],
];

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return <article className="metric-card"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

function Status({ value }: { value: string }) {
  const kind = value === "已解决" ? "ok" : value.includes("待") || value.includes("须") ? "pending" : "blocked";
  return <span className={`status ${kind}`}>{value}</span>;
}

export default function Home() {
  return (
    <main>
      <section className="hero">
        <p className="eyebrow">AGENT WORLD MODEL · PROPOSAL 33.0</p>
        <h1>阶段二 × 阶段三完善与验收</h1>
        <p className="subtitle">联合预测状态变化、进度、风险与终止信号，并以 1–3 步短期推演、长期结果、不确定性和结构一致性完成候选动作排序。页面严格区分历史 GPU 结果、当前代码完成度和仍需真实环境执行的工作。</p>
        <div className="chips"><span>历史 GPU：RTX 4090</span><span>5 次独立训练</span><span>本轮新增成对排序</span><span>真实连续 H=1/2/3 评估</span></div>
      </section>

      <section className="metric-grid" aria-label="核心状态">
        <Metric label="旧版训练规模" value="3,333" note="1,550 episodes · 30 tasks" />
        <Metric label="人工复核队列" value="300" note="待审核，不计作人工标签" />
        <Metric label="旧反事实规模" value="100 对" note="新版目标 3,600 对" />
        <Metric label="真实 H=3 测试窗" value="59" note="门槛 100，当前未通过" />
      </section>

      <h2>问题收口状态</h2>
      <div className="table-wrap"><table><thead><tr><th>优先级</th><th>问题</th><th>已验证事实</th><th>本轮完成</th><th>当前结论</th></tr></thead><tbody>{issueRows.map((row) => <tr key={row[1]}><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td className="wrap">{row[3]}</td><td><Status value={row[4]} /></td></tr>)}</tbody></table></div>

      <h2>已验证的历史多种子训练</h2>
      <p className="section-note">以下数值来自 2026-08-08 的 GPU 报告；本轮含成对排序的新模型尚未在 GPU 上跑完，因而没有覆盖这些历史数值。</p>
      <div className="table-wrap"><table><thead><tr><th>变体</th><th>种子</th><th>最佳 epoch</th><th>验证选择分</th><th>测试风险 F1</th></tr></thead><tbody>{seedRuns.map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody></table></div>

      <section className="split evidence">
        <article className="panel detail-list"><span className="panel-label">阶段二历史测试</span><p>状态变化 F1 <b>99.1%</b></p><p>任务信号 F1 <b>98.5%</b></p><p>风险 F1 <b>90.5%</b></p><p>风险 AUROC <b>99.4%</b></p></article>
        <article className="panel detail-list"><span className="panel-label">阶段三历史代理指标</span><p>候选合法率 <b>100%</b></p><p>安全动作 Recall@K <b>95.0%</b></p><p>结构对齐 Top-1 <b>82.9%</b></p><p>真实 WebArena SR <b>0 / 5</b></p></article>
      </section>

      <h2>真实连续轨迹：H=1/2/3</h2>
      <div className="table-wrap"><table><thead><tr><th>视野</th><th>测试窗口</th><th>潜状态 MSE</th><th>终止结尾</th><th>严重失败结尾</th></tr></thead><tbody>{horizons.map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody></table></div>
      <section className="warning"><b>诚实边界</b><p>H3 误差相对 H1 仍在设置的 4 倍上限内，但 H3 样本、长视野终止和严重失败覆盖均未达新门槛。反事实扩大、多步失败采集和 WebArena 受控候选必须在真实环境执行后，才可以把状态改成“已解决”。AndroidWorld 的适配器与预检不等于完成真实迁移。</p></section>

      <footer><span>Agent 世界模型决策优化</span><span>更新于 2026-08-09 · 证据来自仓库 JSON 报告与本地验收</span></footer>
    </main>
  );
}
