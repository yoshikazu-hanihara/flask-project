document.addEventListener('DOMContentLoaded', function(){
  const form = document.getElementById('calc-form');

  // 数値をカンマ区切りにする関数
  function numberWithCommas(x) {
      return x.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function updateCalculation(){
    const formData = new FormData(form);
    fetch('/dashboard/calculate', {
      method: 'POST',
      body: formData
    })
    .then(response => {
      if (!response.ok) {
        return response.json().then(data => { throw data; });
      }
      return response.json();
    })
    .then(data => {
      // 全体結果の更新（カンマ＋円付き）
      document.getElementById('production_plus_sales_display').innerText =
          "製造原価＋販売管理費: " + numberWithCommas(data.production_plus_sales) + "円";
      document.getElementById('profit_amount_display').innerText =
          "利益額（1個あたり）: " + numberWithCommas(data.profit_amount) + "円";
      document.getElementById('profit_amount_total_display').innerText =
          "利益額（合計）: " + numberWithCommas(data.profit_amount_total) + "円";
      document.getElementById('profit_ratio_display').innerText =
          "利益率: " + numberWithCommas(data.profit_ratio.toFixed(2)) + "%";
      document.getElementById('raw_material_cost_ratio_display').innerText =
          "原材料費原価率: " + numberWithCommas(data.raw_material_cost_ratio.toFixed(2)) + "%";
      document.getElementById('manufacturing_cost_ratio_display').innerText =
          "製造販管費原価率: " + numberWithCommas(data.manufacturing_cost_ratio.toFixed(2)) + "%";
      document.getElementById('sales_admin_cost_ratio_display').innerText =
          "販売管理費率: " + numberWithCommas(data.sales_admin_cost_ratio.toFixed(2)) + "%";
      document.getElementById('yield_coefficient_display').innerText =
          "歩留まり係数: " + numberWithCommas(data.yield_coefficient);

      document.getElementById('manufacturing_cost_total_display').innerText =
          "製造販管費合計: " + numberWithCommas(data.manufacturing_cost_total) + "円";
      document.getElementById('sales_admin_cost_total_display').innerText =
          "販売管理費（1個あたり）: " + numberWithCommas(data.sales_admin_cost_total) + "円";

      // 材料費各項目の更新（カンマ＋円付き）
      document.getElementById('dohdai_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.dohdai_cost) + "円";
      document.getElementById('kata_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.kata_cost) + "円";
      document.getElementById('drying_fuel_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.drying_fuel_cost) + "円";
      document.getElementById('bisque_fuel_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.bisque_fuel_cost) + "円";
      document.getElementById('hassui_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.hassui_cost) + "円";
      document.getElementById('paint_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.paint_cost) + "円";
      document.getElementById('logo_copper_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.logo_copper_cost) + "円";
      document.getElementById('glaze_material_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.glaze_material_cost) + "円";
      document.getElementById('main_firing_gas_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.main_firing_gas_cost) + "円";
      document.getElementById('transfer_sheet_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.transfer_sheet_cost) + "円";

      // 材料費項目-小計（円付き）
      document.getElementById('genzairyousyoukei_coefficient_display').innerText =
          "材料費項目-小計: " + numberWithCommas(data.genzairyousyoukei_coefficient) + "円";
      document.getElementById('raw_material_cost_total_display').innerText =
          "原材料費合計: " + numberWithCommas(data.raw_material_cost_total) + "円";

      // 製造販管費各項目の更新（カンマ＋円付き）
      document.getElementById('chumikin_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.chumikin_cost) + "円";
      document.getElementById('shiagechin_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.shiagechin_cost) + "円";
      document.getElementById('haiimonochin_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.haiimonochin_cost) + "円";
      document.getElementById('seisojiken_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.seisojiken_cost) + "円";
      document.getElementById('soyakeire_dashi_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.soyakeire_dashi_cost) + "円";
      document.getElementById('soyakebarimono_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.soyakebarimono_cost) + "円";
      document.getElementById('doban_hari_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.doban_hari_cost) + "円";
      document.getElementById('hassui_kakouchin_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.hassui_kakouchin_cost) + "円";
      document.getElementById('shiyu_hiyou_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.shiyu_hiyou_cost) + "円";
      document.getElementById('shiyu_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.shiyu_cost) + "円";
      document.getElementById('kamairi_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.kamairi_cost) + "円";
      document.getElementById('kamadashi_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.kamadashi_cost) + "円";
      document.getElementById('hamasuri_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.hamasuri_cost) + "円";
      document.getElementById('kenpin_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.kenpin_cost) + "円";
      document.getElementById('print_kakouchin_cost_display').innerText =
          "合計金額: " + numberWithCommas(data.print_kakouchin_cost) + "円";

      // 製造項目-小計（円付き）
      document.getElementById('seizousyoukei_coefficient_display').innerText =
          "製造項目-小計: " + numberWithCommas(data.seizousyoukei_coefficient) + "円";
    })
    .catch(error => {
      const msg = "入力項目が不十分です";
      document.querySelectorAll('[id$="_display"]').forEach(el => {
        el.innerText = el.innerText.split(':')[0] + ': ' + msg;
      });
    });
  }

  // 入力項目にイベントリスナーを設定
  const inputs = form.querySelectorAll('input');
  inputs.forEach(input => {
    input.addEventListener('input', updateCalculation);
    input.addEventListener('change', updateCalculation);
  });
});
