import { SessionsShell } from "../../components/sessions-shell";
import { getSessionManagerView } from "../../lib/api";

export default async function SessionsPage() {
  const view = await getSessionManagerView();
  return <SessionsShell view={view} />;
}
