import { redirect } from "next/navigation";

import { AuthShell } from "../../components/auth-shell";
import { getServerAccessToken } from "../../lib/auth";

export default async function RegisterPage() {
  const token = await getServerAccessToken();
  if (token) {
    redirect("/sessions");
  }

  return <AuthShell mode="register" />;
}
