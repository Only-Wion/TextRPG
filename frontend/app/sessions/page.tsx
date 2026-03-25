import { SessionsShell } from "../../components/sessions-shell";
import { getPacks, getSessionManagerView } from "../../lib/api";

export default async function SessionsPage() {
  const [view, availablePacks] = await Promise.all([getSessionManagerView(), getPacks()]);
  return <SessionsShell availablePacks={availablePacks} view={view} />;
}
