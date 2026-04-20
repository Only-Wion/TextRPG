import { redirect } from "next/navigation";

import { CardDesignerShell } from "../../components/card-designer-shell";
import { getCurrentUser, getDesignerPacks } from "../../lib/api";
import { getServerAccessToken } from "../../lib/auth";

export default async function CardDesignerPage() {
  const token = await getServerAccessToken();
  if (!token) {
    redirect("/login");
  }

  const [packs, currentUser] = await Promise.all([getDesignerPacks(), getCurrentUser()]);
  if (!currentUser) {
    redirect("/login");
  }

  return <CardDesignerShell currentUser={currentUser} packs={packs} />;
}
