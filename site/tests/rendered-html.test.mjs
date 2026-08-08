import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(new Request("http://localhost/", { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
}

test("renders the phase-two and phase-three evidence dashboard", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const output = await response.text();
  assert.match(output, /阶段二 × 阶段三完善结果/);
  assert.match(output, /五次独立训练/);
  assert.match(output, /阶段三：W0–W3 决策阶梯/);
  assert.match(output, /30\/30 动作执行成功/);
  assert.doesNotMatch(output, /Your site is taking shape|SkeletonPreview/);
});
