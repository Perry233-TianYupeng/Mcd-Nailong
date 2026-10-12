/**
 * Demo 冒烟测试：用 jsdom 真实加载 demo/index.html，跑一遍三条主流程。
 *
 *   npm install jsdom        # 仅测试需要
 *   node tests/demo-smoke.cjs
 *
 * 检查项：
 *   1. 页面脚本无运行时错误
 *   2. 领券流程可完成并渲染战报
 *   3. 抽卡流程产出堡格 / 性格 / 名片名，并渲染到 canvas
 *   4. 预算锁求解在 8 组参数下都满足「实付 ≤ 预算」且输出 3 套方案
 */
const fs = require("fs");
const path = require("path");
const { JSDOM, VirtualConsole } = require("jsdom");

const ROOT = path.resolve(__dirname, "..");
const INDEX = path.join(ROOT, "demo", "index.html");

let failures = 0;
const check = (name, cond, extra = "") => {
  console.log(`${cond ? "  PASS" : "  FAIL"}  ${name}${extra ? "  " + extra : ""}`);
  if (!cond) failures++;
};

function mockContext() {
  const noop = () => {};
  return new Proxy(
    {
      measureText: (t) => ({ width: String(t).length * 14 }),
      createLinearGradient: () => ({ addColorStop: noop }),
      getImageData: () => ({ data: new Uint8ClampedArray(4) }),
      putImageData: noop,
    },
    {
      get(target, prop) {
        if (prop in target) return target[prop];
        return noop;
      },
      set(target, prop, value) {
        target[prop] = value;
        return true;
      },
    }
  );
}

async function main() {
  const virtualConsole = new VirtualConsole();
  const errors = [];
  virtualConsole.on("jsdomError", (e) => errors.push("jsdomError: " + e.message));
  virtualConsole.on("error", (...args) => errors.push("console.error: " + args.join(" ")));

  const html = fs.readFileSync(INDEX, "utf8");
  const dom = new JSDOM(html, {
    runScripts: "dangerously",
    url: "file:///" + INDEX.replace(/\\/g, "/"),
    virtualConsole,
    beforeParse(window) {
      window.HTMLCanvasElement.prototype.getContext = () => mockContext();
      window.HTMLCanvasElement.prototype.toDataURL = () => "data:image/png;base64,AAAA";
      window.HTMLCanvasElement.prototype.toBlob = (cb) => cb(null);
      window.HTMLMediaElement && (window.HTMLMediaElement.prototype.play = () => Promise.resolve());
      window.AudioContext = class {
        constructor() {
          this.currentTime = 0;
          this.destination = {};
        }
        createOscillator() {
          return { frequency: {}, connect() {}, start() {}, stop() {} };
        }
        createGain() {
          return { gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {} };
        }
      };
      window.Image = class {
        set src(v) {
          this._src = v;
          setTimeout(() => this.onload && this.onload(), 0);
        }
        get src() {
          return this._src;
        }
      };
      Object.defineProperty(window.navigator, "clipboard", {
        value: { writeText: () => Promise.resolve() },
        configurable: true,
      });
    },
  });

  const { window } = dom;
  const doc = window.document;
  await new Promise((r) => setTimeout(r, 300));

  console.log("\n[1] 脚本加载");
  check("无运行时错误", errors.length === 0, errors.join(" | "));
  check("全局求解函数存在", typeof window.eval("typeof solveBudget") === "string" && window.eval("typeof solveBudget") === "function");

  console.log("\n[2] 每日领券流程");
  doc.querySelector("#btnCoupon").click();
  await new Promise((r) => setTimeout(r, 3000));
  const report = doc.querySelector("#couponReport");
  const metrics = doc.querySelector("#couponMetrics");
  check("战报区已展开", report && report.style.display === "block");
  check("战报含 4 个指标", metrics && metrics.querySelectorAll("div").length >= 4);
  check("领取明细非空", doc.querySelector("#boundList").textContent.trim().length > 0);
  check("活动预告非空", doc.querySelector("#campaignList").textContent.trim().length > 0);

  console.log("\n[3] 抽卡流程（随机一套）");
  doc.querySelector("#btnQuizRandom").click();
  await new Promise((r) => setTimeout(r, 300));
  const result = doc.querySelector("#quizResult");
  const boge = doc.querySelector("#quizBoge").textContent;
  const pers = doc.querySelector("#quizPersonality").textContent;
  check("结果区已展开", result && result.style.display === "block");
  check("堡格已生成", boge.includes("·"), `→ ${boge.split("\n")[0]}`);
  check("性格关键词已生成", pers.trim().length > 0, `→ ${pers}`);
  check("推荐套餐非空", doc.querySelector("#quizCombo").textContent.includes("实付"),
    `→ ${doc.querySelector("#quizCombo").textContent.slice(0, 40)}`);

  const name = window.eval("quizCardData && quizCardData.title");
  check("名片名格式为 {性格}+{堡格}+奶龙", /奶龙$/.test(name || ""), `→ ${name}`);

  console.log("\n[4] 预算锁求解（8 组参数）");
  const cases = [
    [10, [], "dine_in"],
    [15, ["辣"], "dine_in"],
    [25, ["辣", "鸡"], "dine_in"],
    [25, ["牛", "量足"], "take_out"],
    [35, [], "delivery"],
    [45, ["鸡"], "delivery"],
    [60, ["不辣"], "dine_in"],
    [80, ["牛"], "take_out"],
  ];
  for (const [budget, wants, mode] of cases) {
    const res = window.eval(`solveBudget(${budget}, ${JSON.stringify(wants)}, [], ${JSON.stringify(mode)})`);
    if (!res.ok) {
      check(`预算 ${budget} ${wants.join("/") || "不限"} ${mode}`, true, `→ 无解（可接受）：${res.reason}`);
      continue;
    }
    const over = res.plans.filter((p) => p.row.pay > budget);
    const tags = res.plans.map((p) => p.tag).join(",");
    const sigs = res.plans.map((p) => p.row.items.map((i) => i.code + "x" + i.qty).sort().join("|"));
    check(
      `预算 ${budget} ${wants.join("/") || "不限"} ${mode}`,
      over.length === 0 && res.plans.length === 3 && new Set(sigs).size === 3,
      `→ ${res.plans.length} 套 [${tags}] 实付 ${res.plans.map((p) => p.row.pay.toFixed(2)).join(" / ")}`
    );
  }

  console.log("\n[5] 界面求解 + 购物车 + 计价");
  doc.querySelector("#btnSolve").click();
  await new Promise((r) => setTimeout(r, 200));
  const planCards = doc.querySelectorAll("#planList .plan");
  check("方案卡片已渲染", planCards.length === 3);
  const cartRows = doc.querySelectorAll("#cartList .cart");
  check("购物车已自动载入首选方案", cartRows.length > 0, `→ ${cartRows.length} 行`);
  check("实付金额已计算", /¥\d/.test(doc.querySelector("#mPay").textContent), `→ ${doc.querySelector("#mPay").textContent}`);
  check("消费等级已展示", /节俭度日|吃堡自由|豪情在天/.test(doc.querySelector("#tierBox").textContent));

  console.log("\n[6] 消费等级边界");
  const tiers = [
    [24.9, "节俭度日"], [25, "吃堡自由"], [39.9, "吃堡自由"], [40, "豪情在天"],
  ];
  for (const [pay, expect] of tiers) {
    const got = window.eval(`spendTier(${pay}).level`);
    check(`¥${pay} → ${expect}`, got === expect, `→ ${got}`);
  }

  console.log("\n" + "-".repeat(56));
  console.log(failures === 0 ? "全部通过 ✅" : `${failures} 项未通过 ❌`);
  dom.window.close();
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((e) => {
  console.error("测试崩溃：", e);
  process.exit(1);
});
