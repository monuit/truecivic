const TRUECIVIC_HOST = "https://truecivic.ca";

export function toTrueCivicUrl(path: string): string {
  if (!path) {
    return TRUECIVIC_HOST;
  }
  try {
    return new URL(path).toString();
  } catch {
    const normalized = path.startsWith("/") ? path : `/${path}`;
    return `${TRUECIVIC_HOST}${normalized}`;
  }
}
