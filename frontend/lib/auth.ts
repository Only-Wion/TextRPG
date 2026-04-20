export const ACCESS_TOKEN_COOKIE = "textrpg_token";

export async function getServerAccessToken(): Promise<string | null> {
  const { cookies } = await import("next/headers");
  return (await cookies()).get(ACCESS_TOKEN_COOKIE)?.value ?? null;
}

export function getClientAccessToken(): string | null {
  if (typeof document === "undefined") {
    return null;
  }

  const entry = document.cookie
    .split("; ")
    .find((item) => item.startsWith(`${ACCESS_TOKEN_COOKIE}=`));
  return entry ? decodeURIComponent(entry.split("=")[1] ?? "") : null;
}

export function persistClientAccessToken(token: string): void {
  if (typeof document === "undefined") {
    return;
  }

  document.cookie = `${ACCESS_TOKEN_COOKIE}=${encodeURIComponent(token)}; path=/; max-age=${60 * 60 * 24 * 14}; samesite=lax`;
}

export function clearClientAccessToken(): void {
  if (typeof document === "undefined") {
    return;
  }

  document.cookie = `${ACCESS_TOKEN_COOKIE}=; path=/; max-age=0; samesite=lax`;
}
