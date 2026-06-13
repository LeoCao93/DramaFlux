import type { ApiEndpoint } from "./catalog";

export type RequestValue = string | number | boolean | null | undefined;
export type CustomQueryParameterType = "string" | "boolean";

export interface CustomQueryParameter {
  id: string;
  name: string;
  type: CustomQueryParameterType;
  value: string;
}

export interface ApiRequest {
  method: "GET";
  url: string;
}

export interface ExecuteRequestOptions {
  timeoutMs?: number;
  signal?: AbortSignal;
}

export interface ApiRequestResult {
  status: number;
  statusText: string;
  ok: boolean;
  elapsedMs: number;
  body: unknown;
  contentType: string;
}

const DEFAULT_TIMEOUT_MS = 15_000;
const MAX_TEXT_LENGTH = 20_000;

function hasValue(value: RequestValue): boolean {
  return value !== undefined && value !== null && value !== "";
}

function normalizeText(value: RequestValue): string {
  return String(value).trim();
}

export function validateCustomQueryParameters(
  endpoint: ApiEndpoint,
  parameters: CustomQueryParameter[],
): Record<string, string> {
  const errors: Record<string, string> = {};
  const reserved = new Set(endpoint.parameters.map(({ name }) => name));
  const accepted = new Set<string>();

  for (const parameter of parameters) {
    const name = parameter.name.trim();
    if (!name) {
      continue;
    }
    if (reserved.has(name)) {
      errors[parameter.id] = "参数名与接口参数重复";
      continue;
    }
    if (accepted.has(name)) {
      errors[parameter.id] = "参数名与其他自定义参数重复";
      continue;
    }
    accepted.add(name);
  }

  return errors;
}

export function buildRequest(
  endpoint: ApiEndpoint,
  values: Record<string, RequestValue>,
  customParameters: CustomQueryParameter[] = [],
): ApiRequest {
  let url = endpoint.path;
  const query = new URLSearchParams();

  for (const parameter of endpoint.parameters) {
    const value = values[parameter.name];
    const missing =
      !hasValue(value) || (typeof value === "string" && value.trim() === "");

    if (parameter.required && missing) {
      throw new Error(`缺少必填参数：${parameter.name}`);
    }
    if (missing) {
      continue;
    }

    if (parameter.location === "path") {
      url = url.replace(
        `{${parameter.name}}`,
        encodeURIComponent(String(value)),
      );
    } else {
      query.set(parameter.name, String(value));
    }
  }

  const customErrors = validateCustomQueryParameters(endpoint, customParameters);
  for (const parameter of customParameters) {
    const name = parameter.name.trim();
    const value = parameter.value.trim();
    if (!name || !value || customErrors[parameter.id]) {
      continue;
    }
    query.set(name, value);
  }

  const queryString = query.toString();
  return {
    method: endpoint.method,
    url: queryString ? `${url}?${queryString}` : url,
  };
}

function isJsonContentType(contentType: string): boolean {
  const mediaType = contentType.split(";", 1)[0].trim().toLowerCase();
  return mediaType === "application/json" || mediaType.endsWith("+json");
}

export async function executeRequest(
  request: ApiRequest,
  options: ExecuteRequestOptions = {},
): Promise<ApiRequestResult> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  let timedOut = false;

  const abortFromExternalSignal = () =>
    controller.abort(options.signal?.reason);
  if (options.signal?.aborted) {
    abortFromExternalSignal();
  } else {
    options.signal?.addEventListener("abort", abortFromExternalSignal, {
      once: true,
    });
  }

  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const startedAt = performance.now();

  try {
    const response = await fetch(request.url, {
      method: request.method,
      signal: controller.signal,
    });
    const contentType = response.headers.get("content-type") ?? "";
    const body = isJsonContentType(contentType)
      ? await response.json()
      : (await response.text()).slice(0, MAX_TEXT_LENGTH);

    return {
      status: response.status,
      statusText: response.statusText,
      ok: response.ok,
      elapsedMs: performance.now() - startedAt,
      body,
      contentType,
    };
  } catch (error) {
    if (timedOut) {
      throw new Error(`请求超时：${timeoutMs}ms`, { cause: error });
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
    options.signal?.removeEventListener("abort", abortFromExternalSignal);
  }
}
