// static/js/preset-autofill.js
document.addEventListener("DOMContentLoaded", () => {
    const bar = document.getElementById("preset-bar");
    if (!bar) return;        // テンプレートにタグが無い場合は無視
  
    fetch("/dashboard/presets")
      .then(res => res.json())
      .then(list => {
        list.forEach(p => {
          const btn = document.createElement("button");
          btn.className = "btn";
          btn.textContent = p.name;
          btn.onclick = () => applyPreset(p.data);
          bar.appendChild(btn);
        });
      })
      .catch(console.error); // 取得失敗時は何もしない
  });
  
  function applyPreset(data) {
    const form = document.getElementById("calc-form");
    Object.entries(data).forEach(([k, v]) => {
      const el = form.querySelector(`[name="${k}"]`);
      if (el) el.value = v;
    });
    // 既にフォーム側に input/change リスナーがあるので
    // 任意のフィールドでイベントを発火して再計算を誘発
    form.dispatchEvent(new Event("input", { bubbles: true }));
  }
  