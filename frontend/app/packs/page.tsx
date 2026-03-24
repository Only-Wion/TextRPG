import { PacksShell } from "../../components/packs-shell";
import { getPacks } from "../../lib/api";

export default async function PacksPage() {
  const packs = await getPacks();
  return <PacksShell packs={packs} />;
}
