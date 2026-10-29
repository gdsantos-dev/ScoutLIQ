import { tr } from "./i18n";
let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(tr(message));
    this.status = status;
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  timeoutMs = 20000,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch("/api" + path, {
      method,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch {
    throw new ApiError(
      method === "GET"
        ? "Sem conexão com o servidor. Confira sua rede e tente novamente."
        : "Resultado não confirmado. Atualize os dados antes de repetir a ação.",
      0,
    );
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new ApiError(
      method === "GET"
        ? "Resposta inesperada do servidor."
        : "Resultado não confirmado. Atualize os dados antes de repetir a ação.",
      response.status,
    );
  }
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth/"))
      window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(
      typeof data.detail === "string"
        ? data.detail
        : "Confira os campos informados.",
      response.status,
    );
  }
  return data as T;
}
