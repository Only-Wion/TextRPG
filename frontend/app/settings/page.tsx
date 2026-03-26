import { redirect } from "next/navigation";
import { SettingsShell } from "../../components/settings-shell";
import { getCurrentUser, getLLMSettings } from "../../lib/api";
import { getServerAccessToken } from "../../lib/auth";

export default async function SettingsPage() {
  const token = await getServerAccessToken();
  if (!token) {
    redirect("/login");
  }
  const [settings, currentUser] = await Promise.all([getLLMSettings(), getCurrentUser()]);
  if (!currentUser) {
    redirect("/login");
  }
  return <SettingsShell currentUser={currentUser} settings={settings} />;
}
