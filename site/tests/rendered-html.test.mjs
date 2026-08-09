import assert from "node:assert/strict";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  return worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
}

test("renders the phase-two and phase-three evidence dashboard", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);
  const output = await response.text();
  assert.match(output, /阶段二 × 阶段三完善与验收/);
  assert.match(output, /问题收口状态/);
  assert.match(output, /真实连续轨迹：H=1\/2\/3/);
  assert.match(output, /0 \/ 5/);
  assert.match(output, /当前未通过/);
  assert.doesNotMatch(output, /Your site is taking shape|SkeletonPreview/);
});
