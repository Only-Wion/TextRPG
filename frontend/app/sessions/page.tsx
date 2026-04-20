import { redirect } from "next/navigation";
import { SessionsShell } from "../../components/sessions-shell";
import { getCurrentUser, getPacks, getSessionManagerView } from "../../lib/api";
import { getServerAccessToken } from "../../lib/auth";

export default async function SessionsPage() {
  const token = await getServerAccessToken();
  if (!token) {
    redirect("/login");
  }
  const [view, availablePacks, currentUser] = await Promise.all([
    getSessionManagerView(),
    getPacks(),
    getCurrentUser(),
  ]);
  if (!currentUser) {
    redirect("/login");
  }
  return <SessionsShell availablePacks={availablePacks} currentUser={currentUser} view={view} />;
}
