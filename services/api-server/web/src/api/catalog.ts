export type ApiParameterType = "string" | "integer" | "boolean";
export type ApiParameterLocation = "path" | "query";
export type ApiGroup = "基础接口" | "内容接口" | "播放接口";

export interface ApiParameterValidation {
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  enum?: string[];
}

export interface ApiParameter {
  name: string;
  type: ApiParameterType;
  location: ApiParameterLocation;
  required: boolean;
  description: string;
  defaultValue?: string | boolean | number;
  example?: string | boolean | number;
  validation?: ApiParameterValidation;
}

export interface ApiErrorCode {
  status: number;
  code: string;
  description: string;
}

export interface ApiEndpoint {
  id: string;
  group: ApiGroup;
  title: string;
  method: "GET";
  path: string;
  description: string;
  parameters: ApiParameter[];
  successExample: unknown;
  errorCodes: ApiErrorCode[];
}

const sharedUpstreamErrors: ApiErrorCode[] = [
  { status: 503, code: "session_missing", description: "缺少上游会话" },
  { status: 401, code: "session_expired", description: "上游会话已过期" },
  { status: 503, code: "signer_unavailable", description: "签名服务不可用" },
  {
    status: 502,
    code: "signer_invalid_response",
    description: "签名服务返回无效数据",
  },
  { status: 429, code: "risk_controlled", description: "触发上游风控" },
  { status: 504, code: "upstream_timeout", description: "上游请求超时" },
  { status: 502, code: "upstream_unavailable", description: "上游不可用" },
  {
    status: 502,
    code: "upstream_invalid_response",
    description: "上游返回无效数据",
  },
  { status: 502, code: "upstream_http_error", description: "上游 HTTP 请求失败" },
];

const cursorError: ApiErrorCode = {
  status: 400,
  code: "invalid_cursor",
  description: "游标无效",
};

const successEnvelope = (data: unknown) => ({
  code: 200,
  message: "success",
  data,
  cached: false,
  request_id: "request-id-0001",
});

export const apiCatalog: ApiEndpoint[] = [
  {
    id: "health",
    group: "基础接口",
    title: "服务健康检查",
    method: "GET",
    path: "/health",
    description: "检查本地 API 服务是否已经准备好接收请求。",
    parameters: [],
    successExample: { server: "ready" },
    errorCodes: [],
  },
  {
    id: "search",
    group: "内容接口",
    title: "搜索接口",
    method: "GET",
    path: "/api/search",
    description: "按关键词搜索短剧，并支持分页和游标继续翻页。",
    parameters: [
      {
        name: "q",
        type: "string",
        location: "query",
        required: true,
        description: "搜索关键词",
        example: "都市甜宠",
        validation: { minLength: 1, maxLength: 100 },
      },
      {
        name: "page",
        type: "integer",
        location: "query",
        required: false,
        description: "页码，从 1 开始",
        defaultValue: 1,
        example: 1,
      },
      {
        name: "page_size",
        type: "integer",
        location: "query",
        required: false,
        description: "每页数量，最大 100",
        defaultValue: 30,
        example: 30,
      },
      {
        name: "cursor",
        type: "string",
        location: "query",
        required: false,
        description: "下一页游标",
        validation: { maxLength: 4096 },
      },
    ],
    successExample: successEnvelope({
      items: [
        {
          series_id: "1001",
          video_id: "2001",
          title: "示例短剧",
          episode_count: 80,
          play_count: 120000,
          cover: "https://example.com/cover.jpg",
          copyright: "DramaFlux",
          categories: ["短剧", "都市"],
          is_today: false,
          author: "DramaFlux",
          type: "短剧",
          duration: "12:34",
          publish_time: "2026-06-13",
          intro: "示例简介",
          record_number: "备案号 1001",
          subtitles: ["示例短剧"],
          rank: 1,
          score: 9.2,
        },
      ],
      next_cursor: "eyJvZmZzZXQiOjMwLCJwYXNzYmFjayI6bnVsbCwic2VhcmNoX2lkIjoic2VhcmNoLTEifQ",
      has_more: true,
      page: 1,
      page_size: 30,
      total: 1,
    }),
    errorCodes: [...sharedUpstreamErrors, cursorError],
  },
  {
    id: "latest",
    group: "内容接口",
    title: "获取最新短剧",
    method: "GET",
    path: "/api/latest",
    description: "获取指定分类的最新短剧列表。",
    parameters: [
      {
        name: "genre",
        type: "string",
        location: "query",
        required: false,
        description: "内容分类",
        defaultValue: "short_play",
        example: "short_play",
        validation: {
          enum: ["short_play", "comic_series", "ai_series"],
        },
      },
      {
        name: "today_only",
        type: "boolean",
        location: "query",
        required: false,
        description: "是否只返回今日内容",
        defaultValue: true,
        example: true,
      },
      {
        name: "page",
        type: "integer",
        location: "query",
        required: false,
        description: "页码，从 1 开始",
        defaultValue: 1,
        example: 1,
      },
      {
        name: "page_size",
        type: "integer",
        location: "query",
        required: false,
        description: "每页数量，最大 100",
        defaultValue: 30,
        example: 30,
      },
      {
        name: "cursor",
        type: "string",
        location: "query",
        required: false,
        description: "下一页游标",
        validation: { maxLength: 4096 },
      },
    ],
    successExample: successEnvelope({
      items: [
        {
          series_id: "1001",
          title: "示例短剧",
          author: "DramaFlux",
          type: "短剧",
          duration: "12:34",
          publish_time: "2026-06-13",
          intro: "示例简介",
          record_number: "备案号 1001",
          subtitles: ["今日上新"],
          episode_count: 80,
          play_count: 120000,
          cover: "https://example.com/cover.jpg",
          copyright: "DramaFlux",
          categories: ["短剧", "都市"],
          is_today: true,
        },
      ],
      next_cursor: null,
      has_more: false,
      page: 1,
      page_size: 30,
      total: null,
    }),
    errorCodes: [...sharedUpstreamErrors, cursorError],
  },
  {
    id: "rank",
    group: "内容接口",
    title: "获取短剧榜单",
    method: "GET",
    path: "/api/rank",
    description: "获取推荐、热榜、收藏、追更等榜单内容。",
    parameters: [
      {
        name: "board",
        type: "string",
        location: "query",
        required: false,
        description: "榜单类型",
        defaultValue: "hot",
        example: "hot",
        validation: {
          enum: [
            "recommend",
            "hot",
            "new",
            "must_watch",
            "followed",
            "hot_search",
          ],
        },
      },
      {
        name: "page",
        type: "integer",
        location: "query",
        required: false,
        description: "页码，从 1 开始",
        defaultValue: 1,
        example: 1,
      },
      {
        name: "page_size",
        type: "integer",
        location: "query",
        required: false,
        description: "每页数量，最大 100",
        defaultValue: 30,
        example: 30,
      },
      {
        name: "cursor",
        type: "string",
        location: "query",
        required: false,
        description: "下一页游标",
        validation: { maxLength: 4096 },
      },
    ],
    successExample: successEnvelope({
      items: [
        {
          series_id: "1001",
          video_id: "2001",
          title: "示例短剧",
          episode_count: 80,
          play_count: 120000,
          cover: "https://example.com/cover.jpg",
          copyright: "DramaFlux",
          categories: ["短剧"],
          is_today: false,
          author: "DramaFlux",
          type: "短剧",
          duration: "12:34",
          publish_time: "2026-06-13",
          intro: "示例简介",
          record_number: "备案号 1001",
          subtitles: ["榜单示例"],
          rank: 1,
          score: 9.6,
        },
      ],
      next_cursor: null,
      has_more: false,
      page: 1,
      page_size: 30,
      total: null,
    }),
    errorCodes: [...sharedUpstreamErrors, cursorError],
  },
  {
    id: "book-detail",
    group: "内容接口",
    title: "获取短剧详情",
    method: "GET",
    path: "/api/books/{series_id}",
    description: "获取指定短剧及其全部剧集的标准化详情。",
    parameters: [
      {
        name: "series_id",
        type: "string",
        location: "path",
        required: true,
        description: "短剧 ID",
        example: "1001",
      },
    ],
    successExample: successEnvelope({
      series_id: "1001",
      title: "示例短剧",
      author: "DramaFlux",
      category: "短剧",
      categories: ["短剧", "都市"],
      duration: "12:34",
      publish_time: "2026-06-13",
      episode_count: 2,
      intro: "示例简介",
      cover: "https://example.com/cover.jpg",
      episodes: [
        {
          index: 1,
          video_id: "2001",
          title: "第 1 集",
          first_pass_time: "2026-06-13T00:00:00Z",
          volume_name: "第一卷",
          duration_seconds: 120,
          cover: "https://example.com/episode-1.jpg",
        },
      ],
    }),
    errorCodes: [
      ...sharedUpstreamErrors,
      { status: 404, code: "book_not_found", description: "未找到短剧" },
    ],
  },
  {
    id: "book-episodes",
    group: "内容接口",
    title: "获取短剧剧集",
    method: "GET",
    path: "/api/books/{series_id}/episodes",
    description: "获取指定短剧按序排列的剧集列表。",
    parameters: [
      {
        name: "series_id",
        type: "string",
        location: "path",
        required: true,
        description: "短剧 ID",
        example: "1001",
      },
    ],
    successExample: successEnvelope([
      {
        index: 1,
        video_id: "2001",
        title: "第 1 集",
        first_pass_time: "2026-06-13T00:00:00Z",
        volume_name: "第一卷",
        duration_seconds: 120,
        cover: "https://example.com/episode-1.jpg",
      },
    ]),
    errorCodes: [
      ...sharedUpstreamErrors,
      { status: 404, code: "book_not_found", description: "未找到短剧" },
    ],
  },
  {
    id: "video",
    group: "播放接口",
    title: "解析播放地址",
    method: "GET",
    path: "/api/videos/{video_id}",
    description: "按清晰度解析指定剧集的可播放地址，支持 fast 开关。",
    parameters: [
      {
        name: "video_id",
        type: "string",
        location: "path",
        required: true,
        description: "视频 ID",
        example: "2001",
      },
      {
        name: "quality",
        type: "string",
        location: "query",
        required: false,
        description: "期望清晰度",
        defaultValue: "1080p",
        example: "1080p",
        validation: {
          enum: ["360p", "480p", "540p", "720p", "1080p"],
        },
      },
      {
        name: "fast",
        type: "boolean",
        location: "query",
        required: false,
        description: "是否走快速解析",
        defaultValue: true,
        example: true,
      },
    ],
    successExample: successEnvelope({
      video_id: "2001",
      vid: "2001",
      vod_id: "vod-2001",
      requested_quality: "1080p",
      selected_quality: "1080p",
      url: "https://example.com/video.mp4",
      backup_url: null,
      encrypted: false,
      expires_at: "2026-06-14T00:00:00Z",
    }),
    errorCodes: [
      ...sharedUpstreamErrors,
      { status: 404, code: "video_not_found", description: "未找到视频" },
      {
        status: 422,
        code: "encrypted_stream_unsupported",
        description: "暂不支持加密播放流",
      },
    ],
  },
];
