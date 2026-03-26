import { redirect } from "next/navigation";
import { GameShell } from "../components/game-shell";
import { getCurrentUser, getGameStateView } from "../lib/api";
import { getServerAccessToken } from "../lib/auth";

export default async function GamePage() {
  const token = await getServerAccessToken();
  if (!token) {
    redirect("/login");
  }
  const [state, currentUser] = await Promise.all([getGameStateView(), getCurrentUser()]);
  if (!currentUser) {
    redirect("/login");
  }
  return <GameShell currentUser={currentUser} state={state} />;
}
