import { SetupShell } from "../../components/setup-shell";
import { getLLMSettings, getPacks, getSetupBootstrapView } from "../../lib/api";

export default async function SetupPage() {
  const [setupView, packs, llmSettings] = await Promise.all([
    getSetupBootstrapView(),
    getPacks(),
    getLLMSettings(),
  ]);

  return <SetupShell setupView={setupView} packs={packs} llmSettings={llmSettings} />;
}
