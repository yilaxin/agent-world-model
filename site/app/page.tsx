import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "阶段二、阶段三最终训练与验收看板",
  description: "动作条件世界模型的数据、五次训练、反事实排序与有限步决策最终验收结果。",
};

const seedRuns = [
  ["rank_balanced_a", "29", "0.899178", "入选"],
  ["rank_regularized", "73", "0.893279", "入选"],
  ["rank_base_a", "17", "0.892746", "入选"],
  ["rank_base_b", "42", "0.891642", "备选"],
  ["rank_balanced_b", "101", "0.888477", "备选"],
];

const issueRows = [
  ["P0", "观察反事实规模", "3,600 对全部有效；3,050 对有信息", "已解决"],
  ["P1", "H=2/3 与失败覆盖", "测试 H2=619、H3=329；长视野终止=94、严重失败=47", "已解决"],
  ["P1", "五次 GPU 训练", "5 个种子完成，按验证集选择 3 个成员", "已解决"],
  ["P1", "阶段三离线验收", "反事实与多步评估全部通过既定门槛", "已解决"],
  ["P0", "WebArena 在线成功率", "本轮未配置多站点环境，未做在线重评；不得声称提升", "待阶段四"],
  ["P1", "高风险标签复核", "500/500 条已完成原始轨迹证据核验并写为 evidence_verified；按项目规则无需人工签字", "已解决"],
  ["P2", "AndroidWorld", "本机 WHPX：预检/冒烟通过（19 个 UI 元素）；任务级扩展评测（7 任务×5 次）reactive 42.9% vs phase3 45.7%（语义目标匹配：Chrome/相册/Gmail 100%）", "扩展评测完成"],
];

const horizons = [
  ["H=1", "1,943", "0.000173", "0.9523", "375", "175"],
  ["H=2", "619", "0.000287", "0.9385", "62", "26"],
  ["H=3", "329", "0.000485", "0.9189", "32", "21"],
];

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return <article className="metric-card"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

function Status({ value }: { value: string }) {
  const kind = value === "已解决" || value.includes("通过") ? "ok" : value.includes("待") ? "pending" : "blocked";
  return <span className={`status ${kind}`}>{value}</span>;
}

export default function Home() {
  return (
    <main>
      <section className="hero">
        <p className="eyebrow">AGENT WORLD MODEL · PROPOSAL 33.0</p>
        <h1>阶段二 × 阶段三最终训练与验收</h1>
        <p className="subtitle">RTX 4090 上完成观察反事实扩充、数据质量门禁、五次多种子训练、三成员集成、反事实排序和真实连续 H=1/2/3 轨迹评估。所有结论均来自已同步的 JSON 报告；未把离线指标等同于 WebArena 在线成功率。</p>
        <div className="chips"><span>RTX 4090</span><span>5 次独立训练</span><span>3 模型集成</span><span>全部离线门禁通过</span></div>
      </section>

      <section className="metric-grid" aria-label="核心状态">
        <Metric label="训练数据" value="13,348" note="5,930 episodes · 30 tasks" />
        <Metric label="观察反事实" value="3,600 对" note="3,050 对有信息 · 0 失败" />
        <Metric label="测试 H=3 窗口" value="329" note="门槛 100，已通过" />
        <Metric label="反事实测试准确率" value="97.73%" note="396 个有效测试配对" />
        <Metric label="高风险证据复核" value="500 / 500" note="evidence_verified；自动证据验收通过" />
        <Metric label="AndroidWorld 运行时" value="API 33" note="WHPX 冒烟通过；任务级扩展评测完成" />
      </section>

      <h2>问题收口状态</h2>
      <div className="table-wrap"><table><thead><tr><th>优先级</th><th>问题</th><th>最终证据</th><th>结论</th></tr></thead><tbody>{issueRows.map((row) => <tr key={row[1]}><td>{row[0]}</td><td>{row[1]}</td><td className="wrap">{row[2]}</td><td><Status value={row[3]} /></td></tr>)}</tbody></table></div>

      <h2>五次多种子 GPU 训练</h2>
      <p className="section-note">成员仅按验证集选择，测试集不用于调参。最终选择 rank_balanced_a、rank_regularized 与 rank_base_a。</p>
      <div className="table-wrap"><table><thead><tr><th>变体</th><th>种子</th><th>验证选择分</th><th>状态</th></tr></thead><tbody>{seedRuns.map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody></table></div>

      <section className="split evidence">
        <article className="panel detail-list"><span className="panel-label">阶段二独立测试</span><p>状态变化 F1 <b>98.69%</b></p><p>任务信号 F1 <b>98.90%</b></p><p>风险 F1 <b>94.39%</b></p><p>风险 AUROC <b>99.04%</b></p><p>进度 MAE <b>0.0992</b></p></article>
        <article className="panel detail-list"><span className="panel-label">阶段三反事实排序</span><p>测试观察配对 <b>477</b></p><p>有效配对 <b>396</b></p><p>Pairwise Accuracy <b>97.73%</b></p><p>NDCG@2 <b>0.9916</b></p><p>集成遗憾 <b>0.0511</b></p></article>
      </section>

      <h2>真实连续轨迹：H=1/2/3</h2>
      <div className="table-wrap"><table><thead><tr><th>视野</th><th>测试窗口</th><th>Latent MSE</th><th>余弦相似度</th><th>终止结尾</th><th>严重失败</th></tr></thead><tbody>{horizons.map((row) => <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>)}</tbody></table></div>

      <section className="warning"><b>诚实边界</b><p>多步评估的 H3 MSE 虽通过预设的相对上限，但仍差于 persistence baseline，说明长视野潜状态预测还有改进空间。反事实排序中集成与最佳单模型准确率相同，配对差异 95% CI 为 [-1.01%, 1.01%]；集成只降低了平均决策遗憾，因此生产方法仍按验证集选择单模型。WebArena 本轮没有可用多站点环境变量，未执行新的在线成功率评测。AndroidWorld 在本机 WHPX 上完成冒烟与任务级扩展评测（7 任务×5 次：reactive 42.9% vs phase3 45.7%），日历/信息等任务仍为 0%，策略可用性仍待提升，不能声称迁移完成。</p></section>

      <footer><span>Agent 世界模型决策优化</span><span>更新于 2026-08-10 · 证据来自 RTX 4090 最终 JSON 报告</span></footer>
    </main>
  );
}
