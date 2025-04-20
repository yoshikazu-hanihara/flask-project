// static/js/fixed-presets.js
document.addEventListener("DOMContentLoaded", () => {
  /* --- ① ここに必要なプリセットを並べるだけ --- */
  const PRESETS = [
    {
      name: "MMD六角皿S",
      data: {
        sales_price: 380,
        order_quantity: 1000,
        product_weight: 200,
        mold_unit_price: 2500,
        mold_count: 2,
        glaze_cost: 8500,
        poly_count: 650,
        kiln_count: 1760,
        gas_unit_price: 140,
        loss_defective: 0.1,
        sawaimono_work: 700,
        seisojiken_work: 200,
        soyakeire_work: 250,
        soyakebarimono_work: 300,
        hassui_kakouchin_work: 200,
        shiyu_work: 100,
        kamairi_time: 8,
        kamadashi_time: 4,
        hamasuri_time: 3,
        kenpin_time: 6
      }
    },
    {
      name: "ネンド様フェイブ",
      data: {
        sales_price: 450,
        order_quantity: 1000,
        product_weight: 7,
        mold_unit_price: 3500,
        mold_count: 10,
        glaze_cost: 8500,
        poly_count: 5000,
        kiln_count: 52800,
        gas_unit_price: 140,
        loss_defective: 0.15,
        sawaimono_work: 800,
        seisojiken_work: 200,
        soyakeire_work: 300,
        soyakebarimono_work: 400,
        hassui_kakouchin_work: 200,
        shiyu_work: 200,
        kamairi_time: 8,
        kamadashi_time: 4,
        hamasuri_time: 3,
        kenpin_time: 6
      }
    }
  ];
  /* --- ↑ここを増減させるだけでボタンが増える --- */

  /* ② ボタン描画 */
  const bar = document.getElementById("preset-bar");
  if (!bar) return;   // テンプレに該当要素が無いときはスキップ

  PRESETS.forEach(preset => {
    const btn = document.createElement("button");
    btn.className = "btn";
    btn.textContent = preset.name;
    btn.addEventListener("click", () => applyPreset(preset.data));
    bar.appendChild(btn);
  });

  /* ③ ボタンクリック時の一括入力 */
  function applyPreset(data) {
    const form = document.getElementById("calc-form");
    Object.entries(data).forEach(([k, v]) => {
      const el = form.querySelector(`[name="${k}"]`);
      if (!el) return;

      if (el.type === "radio") {
        // 今回の data は数値入力だけなのでほぼ通らないが念のため
        form.querySelectorAll(`[name="${k}"]`).forEach(r => {
          r.checked = Number(r.value) === Number(v);
        });
      } else if (el.type === "checkbox") {
        el.checked = Boolean(v);
      } else {
        el.value = v;
      }
    });
    /* フォーム側の input/change 監視を活かして再計算を発火 */
    form.dispatchEvent(new Event("input", { bubbles: true }));
  }
});
