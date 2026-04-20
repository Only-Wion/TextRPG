"use client";

import { useState } from "react";

import {
  getCoinConsumptions,
  redeemCoins,
  updateLLMPlanSelection,
} from "../lib/api";
import type {
  AuthUser,
  CoinConsumptionRecord,
  SettingsOverview,
} from "../lib/api-contract";
import { AppSidebar } from "./app-sidebar";

type SettingsShellProps = {
  overview: SettingsOverview;
  currentUser: AuthUser;
};

export function SettingsShell({ overview, currentUser }: SettingsShellProps) {
  const [plans] = useState(overview.plans ?? []);
  const [selectedPlanId, setSelectedPlanId] = useState(overview.selected_plan_id ?? "");
  const [coinBalance, setCoinBalance] = useState(Number(overview.coin_balance ?? 0));
  const [redeemKey, setRedeemKey] = useState("");
  const [consumptions, setConsumptions] = useState<CoinConsumptionRecord[]>([]);

  const [isSavingPlan, setIsSavingPlan] = useState(false);
  const [isRedeeming, setIsRedeeming] = useState(false);
  const [isLoadingConsumptions, setIsLoadingConsumptions] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  async function handleSavePlanSelection() {
    if (!selectedPlanId) {
      setErrorMessage("请选择一个模型方案。");
      return;
    }

    setIsSavingPlan(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      await updateLLMPlanSelection({ plan_id: selectedPlanId });
      setSuccessMessage("模型方案已保存。后续对话将使用该方案。");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "保存模型方案失败。");
    } finally {
      setIsSavingPlan(false);
    }
  }

  async function handleRedeem() {
    if (!redeemKey.trim()) {
      setErrorMessage("请输入兑换密钥。");
      return;
    }
    setIsRedeeming(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const result = await redeemCoins({ redeem_key: redeemKey.trim() });
      setCoinBalance(Number(result.balance_after ?? coinBalance));
      setRedeemKey("");
      setSuccessMessage(`兑换成功，到账 ${Number(result.coins_added ?? 0).toFixed(2)} 代币。`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "兑换失败。");
    } finally {
      setIsRedeeming(false);
    }
  }

  async function handleLoadConsumptions() {
    setIsLoadingConsumptions(true);
    setErrorMessage(null);
    try {
      const rows = await getCoinConsumptions(100);
      setConsumptions(rows ?? []);
      if (!rows || rows.length === 0) {
        setSuccessMessage("暂无消耗记录。");
      }
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "加载消耗记录失败。");
    } finally {
      setIsLoadingConsumptions(false);
    }
  }

  function jumpToConsumptionSection() {
    const target = document.getElementById("coin-consumption-section");
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  return (
    <main className="light-app-shell">
      <div className="light-app-frame">
        <AppSidebar activePath="/settings" currentUser={currentUser} />

        <section className="light-main">
          <header className="light-topbar">
            <h1 className="light-page-title">Settings</h1>
          </header>

          <div className="light-stack">
            <section className="light-card settings-form-card">
              <div className="settings-field">
                <label className="settings-label" htmlFor="coin-balance">
                  当前代币余额
                </label>
                <div className="settings-check" id="coin-balance">
                  {coinBalance.toFixed(2)}
                </div>
              </div>

              <div className="settings-field">
                <label className="settings-label" htmlFor="redeem-key">
                  兑换密钥
                </label>
                <input
                  className="light-input"
                  id="redeem-key"
                  onChange={(event) => setRedeemKey(event.target.value)}
                  placeholder="输入购买后获得的密钥"
                  value={redeemKey}
                />
              </div>

              <div className="settings-check">固定档位：1元 / 6元 / 18元 / 30元</div>

              <button className="light-action-button archive" disabled={isRedeeming} onClick={handleRedeem} type="button">
                {isRedeeming ? "兑换中..." : "兑换代币"}
              </button>

              <div className="light-section-title">可选模型方案</div>
              {plans.map((plan) => (
                <label className="toggle-row" key={plan.plan_id}>
                  <input
                    checked={selectedPlanId === plan.plan_id}
                    onChange={() => setSelectedPlanId(plan.plan_id)}
                    type="radio"
                  />
                  <span>
                    {plan.name} | {plan.description} | 输入 {plan.input_tokens_per_coin} token/币 | 输出 {plan.output_tokens_per_coin} token/币
                  </span>
                </label>
              ))}

              <button className="light-action-button new" disabled={isSavingPlan} onClick={handleSavePlanSelection} type="button">
                {isSavingPlan ? "保存中..." : "保存模型方案"}
              </button>

              <button className="light-action-button" onClick={jumpToConsumptionSection} type="button">
                跳转到消耗记录
              </button>

              {errorMessage ? <div className="light-error-banner">{errorMessage}</div> : null}
              {successMessage ? <div className="light-success-banner">{successMessage}</div> : null}
            </section>

            <section className="light-card" id="coin-consumption-section">
              <h2 className="light-card-title">消耗记录</h2>
              <button className="light-action-button" disabled={isLoadingConsumptions} onClick={handleLoadConsumptions} type="button">
                {isLoadingConsumptions ? "加载中..." : "刷新记录"}
              </button>
              <pre className="settings-json">
                {JSON.stringify(consumptions, null, 2)}
              </pre>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}
