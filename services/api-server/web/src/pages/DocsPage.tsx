import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { apiCatalog, type ApiEndpoint } from "../api/catalog";
import {
  buildRequest,
  executeRequest,
  type ApiRequestResult,
  type CustomQueryParameter,
} from "../api/client";
import PlatformIcon from "../components/PlatformIcon";
import SyntaxCodeBlock from "../components/SyntaxCodeBlock";

type DocTab = "api" | "errors" | "debug";

const docTabs: Array<{ id: DocTab; label: string }> = [
  { id: "api", label: "API文档" },
  { id: "errors", label: "错误码参照" },
  { id: "debug", label: "在线调试" },
];

function initialValues(endpoint: ApiEndpoint): Record<string, string> {
  return Object.fromEntries(
    endpoint.parameters.map((parameter) => [
      parameter.name,
      String(parameter.defaultValue ?? parameter.example ?? ""),
    ]),
  );
}

function pretty(value: unknown) {
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function codeLines(value: unknown) {
  return pretty(value).split("\n");
}

function formatBytes(value: unknown) {
  const bytes = new TextEncoder().encode(pretty(value)).length;
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(2)} KB`;
}

function inlineExample(value: unknown) {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value == null) {
    return "—";
  }
  return "object";
}

function createCustomParameter(id: string): CustomQueryParameter {
  return { id, name: "", type: "string", value: "" };
}

export default function DocsPage() {
  const hashId = window.location.hash.slice(1);
  const firstEndpoint =
    apiCatalog.find((endpoint) => endpoint.id === hashId) ?? apiCatalog[1];

  const [selected, setSelected] = useState(firstEndpoint);
  const [values, setValues] = useState(() => initialValues(firstEndpoint));
  const [activeParameterNames, setActiveParameterNames] = useState<string[]>(
    () => firstEndpoint.parameters.map(({ name }) => name),
  );
  const [customParameters, setCustomParameters] = useState<CustomQueryParameter[]>([]);
  const [query, setQuery] = useState("");
  const [activeTab, setActiveTab] = useState<DocTab>("api");
  const [result, setResult] = useState<ApiRequestResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [favorite, setFavorite] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const nextCustomId = useRef(1);

  const filtered = useMemo(
    () =>
      apiCatalog.filter((endpoint) =>
        `${endpoint.title} ${endpoint.path}`.toLowerCase().includes(query.toLowerCase()),
      ),
    [query],
  );

  const groupedEndpoints = useMemo(() => {
    const groups = [...new Set(filtered.map((endpoint) => endpoint.group))];
    return groups.map((group) => ({
      group,
      endpoints: filtered.filter((endpoint) => endpoint.group === group),
    }));
  }, [filtered]);

  const visibleParameters = useMemo(
    () =>
      selected.parameters.filter((parameter) =>
        activeParameterNames.includes(parameter.name),
      ),
    [activeParameterNames, selected.parameters],
  );

  const customErrors = useMemo(() => {
    const errors: Record<string, string> = {};
    const reserved = new Set(selected.parameters.map(({ name }) => name));
    const accepted = new Set<string>();

    for (const parameter of customParameters) {
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
  }, [customParameters, selected.parameters]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const chooseEndpoint = (endpoint: ApiEndpoint) => {
    abortRef.current?.abort();
    setSelected(endpoint);
    setValues(initialValues(endpoint));
    setActiveParameterNames(endpoint.parameters.map(({ name }) => name));
    setCustomParameters([]);
    setResult(null);
    setError("");
    setFavorite(false);
    setActiveTab("api");
    window.history.replaceState(null, "", `/docs#${endpoint.id}`);
  };

  const removeBuiltInParameter = (name: string) => {
    setActiveParameterNames((names) => names.filter((item) => item !== name));
    setValues((current) => {
      const next = { ...current };
      delete next[name];
      return next;
    });
  };

  const addCustomParameter = () => {
    const id = `custom-${nextCustomId.current++}`;
    setCustomParameters((rows) => [...rows, createCustomParameter(id)]);
  };

  const updateCustomParameter = (id: string, patch: Partial<CustomQueryParameter>) => {
    setCustomParameters((rows) =>
      rows.map((row) => (row.id === id ? { ...row, ...patch } : row)),
    );
  };

  const removeCustomParameter = (id: string) => {
    setCustomParameters((rows) => rows.filter((row) => row.id !== id));
  };

  const sendRequest = async () => {
    setError("");
    setResult(null);

    try {
      const request = buildRequest(selected, values, customParameters);
      const controller = new AbortController();
      abortRef.current?.abort();
      abortRef.current = controller;
      setLoading(true);
      setResult(await executeRequest(request, { signal: controller.signal }));
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") {
        return;
      }
      setError(reason instanceof Error ? reason.message : "请求失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  };

  const copyText = (value: string) => {
    if (navigator.clipboard) void navigator.clipboard.writeText(value);
  };

  const parameterRows = [
    { label: "接口地址", value: selected.path, copyable: true },
    { label: "返回格式", value: "application/json" },
    { label: "请求方式", value: selected.method },
    { label: "参数数量", value: `${selected.parameters.length} 项` },
  ];

  const responseEnvelope = [
    {
      name: "code",
      type: "int",
      required: true,
      description: "业务状态码",
      example: 200,
    },
    {
      name: "message",
      type: "string",
      required: true,
      description: "返回说明",
      example: "success",
    },
    {
      name: "data",
      type: "object",
      required: true,
      description: "实际返回数据",
      example: selected.successExample,
    },
    {
      name: "cached",
      type: "boolean",
      required: false,
      description: "是否命中缓存",
      example: false,
    },
    {
      name: "request_id",
      type: "string",
      required: false,
      description: "请求追踪 ID",
      example: "request-id-0001",
    },
  ];

  return (
    <div className="docs-page">
      <h1 className="visually-hidden">接口文档</h1>

      <aside className="docs-sidebar" aria-label="接口目录">
        <label className="docs-search">
          <span aria-hidden="true">⌕</span>
          <input
            aria-label="搜索API文档"
            placeholder="搜索API文档..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <kbd>⌘K</kbd>
        </label>

        <div className="docs-navigation">
          {groupedEndpoints.map(({ group, endpoints }) => (
            <section className="endpoint-group" key={group}>
              <h2>
                {group}
                <span>⌄</span>
              </h2>
              {endpoints.map((endpoint) => (
                <button
                  aria-pressed={selected.id === endpoint.id}
                  className={selected.id === endpoint.id ? "is-selected" : ""}
                  key={endpoint.id}
                  onClick={() => chooseEndpoint(endpoint)}
                  type="button"
                >
                  <span>{endpoint.method}</span>
                  <strong>{endpoint.title}</strong>
                  {selected.id === endpoint.id && <b>›</b>}
                </button>
              ))}
            </section>
          ))}
        </div>

        <div className="docs-help">
          <span>
            <PlatformIcon name="document" />
          </span>
          <div>
            <strong>需要帮助？</strong>
            <a href="#guide">查看开发指南</a>
          </div>
          <b>›</b>
        </div>
      </aside>

      <main className="docs-workbench">
        <header className="docs-overview">
          <div className="docs-overview-head">
            <div className="docs-overview-title">
              <h2>{selected.title}</h2>
              <span className="method-badge">{selected.method}</span>
              <code>{selected.path}</code>
            </div>
            <div className="docs-overview-actions">
              <button
                onClick={() => copyText(`${selected.method} ${selected.path}`)}
                type="button"
              >
                复制接口信息
              </button>
              <button
                aria-pressed={favorite}
                onClick={() => setFavorite((value) => !value)}
                type="button"
              >
                {favorite ? "已收藏" : "添加到收藏"}
              </button>
            </div>
          </div>
          <p>{selected.description}</p>

          <div className="docs-summary-grid">
            <div className="docs-summary-card">
              <span>接口分组</span>
              <strong>{selected.group}</strong>
              <small>当前选中的产品模块</small>
            </div>
            <div className="docs-summary-card">
              <span>请求方式</span>
              <strong>{selected.method}</strong>
              <small>保持与后端路由一致</small>
            </div>
            <div className="docs-summary-card">
              <span>请求参数</span>
              <strong>{selected.parameters.length}</strong>
              <small>支持路径、查询和自定义参数</small>
            </div>
            <div className="docs-summary-card">
              <span>错误码</span>
              <strong>{selected.errorCodes.length}</strong>
              <small>已对齐最新 main 分支</small>
            </div>
          </div>

          <div className="docs-toolbar">
            <Link className="primary-action" to="/pricing">
              立即购买
            </Link>
            <button className="secondary-action" type="button">
              免费测试
            </button>
          </div>
        </header>

        <nav className="docs-tabs" role="tablist" aria-label="文档分类">
          {docTabs.map((tab) => (
            <button
              aria-selected={activeTab === tab.id}
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              role="tab"
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <section className="docs-section">
          {activeTab === "api" && (
            <div className="docs-tab-content">
              <section className="docs-panel">
                <h3>接口地址</h3>
                <div className="docs-doclist">
                  {parameterRows.map((item) => (
                    <div className="docs-doc-item" key={item.label}>
                      <span>{item.label}</span>
                      <div>
                        <strong>{item.value}</strong>
                        {item.copyable && (
                          <button
                            className="docs-inline-button"
                            type="button"
                            onClick={() => copyText(item.value)}
                          >
                            复制
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                  <div className="docs-doc-item">
                    <span>请求示例</span>
                    <div>
                      <code>
                        {selected.method} {selected.path}
                      </code>
                    </div>
                  </div>
                </div>
              </section>

              <section className="docs-panel">
                <h3>请求 Header</h3>
                <div className="docs-table">
                  <div className="docs-table-row docs-table-head">
                    <span>名称</span>
                    <span>值</span>
                    <span>说明</span>
                    <span>示例值</span>
                    <span>备注</span>
                  </div>
                  <div className="docs-table-row">
                    <code>Authorization</code>
                    <span>Bearer API_KEY</span>
                    <span>鉴权信息</span>
                    <span>Bearer xxx</span>
                    <span>必填</span>
                  </div>
                  <div className="docs-table-row">
                    <code>Content-Type</code>
                    <span>application/json</span>
                    <span>内容类型</span>
                    <span>application/json</span>
                    <span>调试时自动注入</span>
                  </div>
                </div>
              </section>

              <section className="docs-panel">
                <h3>请求参数说明</h3>
                <div className="docs-table">
                  <div className="docs-table-row docs-table-head">
                    <span>参数名</span>
                    <span>类型</span>
                    <span>必填</span>
                    <span>说明</span>
                    <span>示例值</span>
                  </div>
                  {selected.parameters.map((parameter) => (
                    <div className="docs-table-row" key={parameter.name}>
                      <code>{parameter.name}</code>
                      <span>{parameter.type}</span>
                      <span>{parameter.required ? "是" : "否"}</span>
                      <span>{parameter.description}</span>
                      <span>{String(parameter.example ?? parameter.defaultValue ?? "—")}</span>
                    </div>
                  ))}
                </div>
                <p className="docs-note">
                  请求参数会与最新 main 分支的后端出入参保持一致。若有自定义参数，请在下方在线调试面板中添加。
                </p>
              </section>

              <section className="docs-panel">
                <h3>返回参数说明</h3>
                <div className="docs-table">
                  <div className="docs-table-row docs-table-head">
                    <span>参数名</span>
                    <span>类型</span>
                    <span>必填</span>
                    <span>说明</span>
                    <span>示例值</span>
                  </div>
                  {responseEnvelope.map((parameter) => (
                    <div className="docs-table-row" key={parameter.name}>
                      <code>{parameter.name}</code>
                      <span>{parameter.type}</span>
                      <span>{parameter.required ? "是" : "否"}</span>
                      <span>{parameter.description}</span>
                      <span>{inlineExample(parameter.example)}</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}

          {activeTab === "errors" && (
            <div className="docs-tab-content">
              <section className="docs-panel">
                <h3>错误码参照</h3>
                <div className="docs-error-list">
                  <div className="docs-table-row docs-table-head">
                    <span>状态</span>
                    <span>错误码</span>
                    <span>说明</span>
                  </div>
                  {selected.errorCodes.map((item) => (
                    <div key={`${item.status}-${item.code}`}>
                      <strong>{item.status}</strong>
                      <code>{item.code}</code>
                      <span>{item.description}</span>
                    </div>
                  ))}
                </div>
                <p className="docs-note">
                  这里优先展示当前接口自身的错误码；更底层的签名、会话或上游异常会在返回体里保留原始语义。
                </p>
              </section>
            </div>
          )}

          {activeTab === "debug" && (
            <div className="docs-tab-content docs-tab-content--debug">
              <div className="docs-debug-panel" aria-label="在线调试">
                <section className="request-builder">
                  <div className="console-heading">
                    <h2>在线调试</h2>
                    <button
                      type="button"
                      onClick={() => {
                        setResult(null);
                        setError("");
                      }}
                    >
                      清空
                    </button>
                  </div>

                  <p className="docs-note docs-debug-note">
                    真正的请求编辑器和响应结果放在同一块工作台里，方便在文档与调试之间来回切换。
                  </p>

                  <div className="request-top-fields">
                    <label>
                      <span>请求方式</span>
                      <select aria-label="请求方式" value={selected.method} disabled>
                        <option>{selected.method}</option>
                      </select>
                    </label>
                    <label>
                      <span>请求路径</span>
                      <input aria-label="请求路径" value={selected.path} readOnly />
                    </label>
                  </div>

                  <h3>请求参数</h3>
                  <div className="parameter-form">
                    {visibleParameters.map((parameter) => (
                      <label key={parameter.name}>
                        <span className="parameter-name">
                          {parameter.name}
                          {parameter.required && <b> *</b>}
                        </span>
                        <span className="parameter-type">{parameter.type}</span>
                        {parameter.type === "boolean" ? (
                          <select
                            aria-label={parameter.name}
                            value={values[parameter.name]}
                            onChange={(event) =>
                              setValues({ ...values, [parameter.name]: event.target.value })
                            }
                          >
                            <option value="true">true</option>
                            <option value="false">false</option>
                          </select>
                        ) : parameter.type === "integer" ? (
                          <input
                            aria-label={parameter.name}
                            inputMode="numeric"
                            type="number"
                            value={values[parameter.name] ?? ""}
                            onChange={(event) =>
                              setValues({ ...values, [parameter.name]: event.target.value })
                            }
                          />
                        ) : (
                          <input
                            aria-label={parameter.name}
                            value={values[parameter.name] ?? ""}
                            onChange={(event) =>
                              setValues({ ...values, [parameter.name]: event.target.value })
                            }
                          />
                        )}
                        <button
                          aria-label={`删除 ${parameter.name}`}
                          onClick={() => removeBuiltInParameter(parameter.name)}
                          type="button"
                        >
                          ×
                        </button>
                      </label>
                    ))}

                    {customParameters.map((parameter, index) => {
                      const rowNumber = index + 1;
                      const rowError = customErrors[parameter.id];

                      return (
                        <div
                          className="custom-parameter-row"
                          data-testid="custom-parameter-row"
                          key={parameter.id}
                        >
                          <label>
                            <span className="parameter-name">自定义参数名 {rowNumber}</span>
                            <input
                              aria-label={`自定义参数名 ${rowNumber}`}
                              value={parameter.name}
                              onChange={(event) =>
                                updateCustomParameter(parameter.id, { name: event.target.value })
                              }
                            />
                          </label>
                          <label>
                            <span className="parameter-name">自定义参数类型 {rowNumber}</span>
                            <select
                              aria-label={`自定义参数类型 ${rowNumber}`}
                              value={parameter.type}
                              onChange={(event) =>
                                updateCustomParameter(parameter.id, {
                                  type: event.target.value as CustomQueryParameter["type"],
                                })
                              }
                            >
                              <option value="string">string</option>
                              <option value="boolean">boolean</option>
                            </select>
                          </label>
                          <label>
                            <span className="parameter-name">自定义参数值 {rowNumber}</span>
                            <input
                              aria-label={`自定义参数值 ${rowNumber}`}
                              value={parameter.value}
                              onChange={(event) =>
                                updateCustomParameter(parameter.id, { value: event.target.value })
                              }
                            />
                          </label>
                          <button
                            aria-label={`删除自定义参数 ${rowNumber}`}
                            onClick={() => removeCustomParameter(parameter.id)}
                            type="button"
                          >
                            ×
                          </button>
                          {rowError && (
                            <p className="custom-parameter-error" role="alert">
                              {rowError}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  <button className="add-parameter" onClick={addCustomParameter} type="button">
                    ＋ 添加参数
                  </button>
                  <button
                    aria-label="发送请求"
                    className="send-button"
                    disabled={loading}
                    onClick={sendRequest}
                    type="button"
                  >
                    {loading ? "请求中..." : "发送请求"}
                  </button>
                </section>

                <section className="response-panel" aria-live="polite">
                  <div className="response-heading">
                    <h3>响应结果</h3>
                    <button onClick={() => result && copyText(pretty(result.body))} type="button">
                      复制
                    </button>
                  </div>

                  {result && (
                    <div className="response-meta">
                      <span>
                        状态：
                        <strong className={result.ok ? "success-status" : "error-status"}>
                          {result.status} {result.statusText}
                        </strong>
                      </span>
                      <span>耗时：{Math.round(result.elapsedMs)}ms</span>
                      <span>大小：{formatBytes(result.body)}</span>
                    </div>
                  )}

                  {error && (
                    <p className="request-error" role="alert">
                      {error}
                    </p>
                  )}

                  {result ? (
                    <SyntaxCodeBlock compact label="真实接口响应" lines={codeLines(result.body)} />
                  ) : !error ? (
                    <p className="empty-note">填写参数并发送请求，响应会显示在这里。</p>
                  ) : null}

                  <small className="response-disclaimer">
                    响应结果仅供调试参考，实际以接口返回为准。
                  </small>
                </section>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
