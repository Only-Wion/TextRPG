import { redirect } from "next/navigation";
import { SettingsShell } from "../../components/settings-shell";
import { getCurrentUser, getSettingsOverview } from "../../lib/api";
import { getServerAccessToken } from "../../lib/auth";

export default async function SettingsPage() {
  const token = await getServerAccessToken();
  if (!token) {
    redirect("/login");
  }
  const [overview, currentUser] = await Promise.all([getSettingsOverview(), getCurrentUser()]);
  if (!currentUser) {
    redirect("/login");
  }
  return <SettingsShell currentUser={currentUser} overview={overview} />;
}
