import { SettingsShell } from "../../components/settings-shell";
import { getLLMSettings } from "../../lib/api";

export default async function SettingsPage() {
  const settings = await getLLMSettings();
  return <SettingsShell settings={settings} />;
}
