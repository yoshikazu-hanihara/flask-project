/*  static/js/fixed-presets.js
   ──────────────────────────────────────────────
   プリセットボタンを動的に生成し、クリックすると
   入力フォームに一括で値を投入して 'preset‑applied'
   イベントを発火させる。

   ・ボタンを増やしたいときは PRESETS 配列に
     { name: "...", data: { inputName: 値, ... } } を
     追加するだけで OK
   ・auto‑calc.js 側で
       form.addEventListener('preset-applied', updateCalculation);
     を登録しておくことで、投入直後に再計算される
   ──────────────────────────────────────────────
*/

document.addEventListener("DOMContentLoaded", () => {
  /* === ① 固定プリセット定義 ===================================== */
  const PRESETS = [
    {
      name: "MMD六角皿S",
      img : "img/mmd_s.png",
      data: {
        sales_price:           380,
        order_quantity:        1000,
        product_weight:        200,
        mold_unit_price:       2500,
        mold_count:            2,
        glaze_cost:            8500,
        poly_count:            650,
        kiln_count:            1760,
        gas_unit_price:        140,
        loss_defective:        0.1,
        sawaimono_work:        700,
        seisojiken_work:       200,
        soyakeire_work:        250,
        soyakebarimono_work:   300,
        hassui_kakouchin_work: 200,
        shiyu_work:            100,
        kamairi_time:          8,
        kamadashi_time:        4,
        hamasuri_time:         3,
        kenpin_time:           6
      }
    },
    {
      name: "ネンド様フェイブ",
      img : "img/nendosama_fave.png",
      data: {
        sales_price:           450,
        order_quantity:        1000,
        product_weight:        7,
        mold_unit_price:       3500,
        mold_count:            10,
        glaze_cost:            8500,
        poly_count:            5000,
        kiln_count:            52800,
        gas_unit_price:        140,
        loss_defective:        0.15,
        sawaimono_work:        800,
        seisojiken_work:       200,
        soyakeire_work:        300,
        soyakebarimono_work:   400,
        hassui_kakouchin_work: 200,
        shiyu_work:            200,
        kamairi_time:          8,
        kamadashi_time:        4,
        hamasuri_time:         3,
        kenpin_time:           6
      }
    }
  ];
  /* =============================================================== */

  const bar  = document.getElementById("preset-bar");
  const form = document.getElementById("calc-form");
  if (!bar || !form) return;

  /* ボタン生成 */
  PRESETS.forEach(preset => {
    const btn = document.createElement("button");
    btn.className = "preset-btn";
    btn.innerHTML = `
      <img src="{{ url_for('static', filename='') }}${preset.img}" alt="${preset.name}">
      <span>${preset.name}</span>
    `;
    btn.addEventListener("click", () => applyPreset(preset.data));
    bar.appendChild(btn);
  });

  /* 値の一括投入 → sales_price に input イベントを発火 */
  function applyPreset(data) {
    Object.entries(data).forEach(([k, v]) => {
      const el = form.querySelector(`[name="${k}"]`);
      if (!el) return;
      if (el.type === "radio") {
        form.querySelectorAll(`[name="${k}"]`).forEach(r => {
          r.checked = Number(r.value) === Number(v);
        });
      } else if (el.type === "checkbox") {
        el.checked = Boolean(v);
      } else {
        el.value = v;
      }
    });
    const trigger = form.querySelector('[name="sales_price"]');
    if (trigger) trigger.dispatchEvent(new Event("input", { bubbles: true }));
  }
});
