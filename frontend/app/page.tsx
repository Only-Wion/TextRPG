import { GameShell } from "../components/game-shell";
import { getGameStateView } from "../lib/api";

export default async function GamePage() {
  const state = await getGameStateView();
  return <GameShell state={state} />;
}
