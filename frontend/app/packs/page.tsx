import { redirect } from "next/navigation";
import { PacksShell } from "../../components/packs-shell";
import { getCurrentUser, getPacks } from "../../lib/api";
import { getServerAccessToken } from "../../lib/auth";

export default async function PacksPage() {
  const token = await getServerAccessToken();
  if (!token) {
    redirect("/login");
  }
  const [packs, currentUser] = await Promise.all([getPacks(), getCurrentUser()]);
  if (!currentUser) {
    redirect("/login");
  }
  return <PacksShell currentUser={currentUser} packs={packs} />;
}
