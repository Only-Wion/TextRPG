import { redirect } from "next/navigation";
import { SetupShell } from "../../components/setup-shell";
import { getCurrentUser, getLLMSettings, getPacks, getSetupBootstrapView } from "../../lib/api";
import { getServerAccessToken } from "../../lib/auth";

export default async function SetupPage() {
  const token = await getServerAccessToken();
  if (!token) {
    redirect("/login");
  }
  const [setupView, packs, llmSettings, currentUser] = await Promise.all([
    getSetupBootstrapView(),
    getPacks(),
    getLLMSettings(),
    getCurrentUser(),
  ]);
  if (!currentUser) {
    redirect("/login");
  }

  return <SetupShell currentUser={currentUser} setupView={setupView} packs={packs} llmSettings={llmSettings} />;
}
