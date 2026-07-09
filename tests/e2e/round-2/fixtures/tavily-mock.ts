/**
 * 025 — Tavily scenario writer + preset scenarios for A2A planner E2E.
 *
 * The MockTavilyClient reads a scenario JSON file at startup. The path is
 * passed to the backend via the TAVILY_MOCK_SCENARIO_PATH env var. Because
 * the backend is started once per E2E session (not per test), we write to a
 * FIXED path before each test and the mock client re-reads the file on every
 * invoke — so each test sees the scenario it wrote.
 *
 * Scenario JSON shape:
 *   {
 *     "scenarios": [
 *       {
 *         "query": "前端开发 面试经验",
 *         "results": [
 *           {
 *             "title": "...",
 *             "content": "...",
 *             "url": "...",
 *             "score": 0.95
 *           }
 *         ]
 *       }
 *     ]
 *   }
 *
 * The mock client falls back to empty results if a query does not match
 * any scenario or the file is missing.
 */
import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export interface TavilyScenario {
  scenarios: TavilyScenarioEntry[]
}

export interface TavilyScenarioEntry {
  query: string
  results: TavilySearchResult[]
}

export interface TavilySearchResult {
  title: string
  content: string
  url: string
  score: number
}

/**
 * Fixed absolute path the backend reads from. Must match the
 * TAVILY_MOCK_SCENARIO_PATH env var used to start the backend for E2E.
 */
export const SCENARIO_FILE_PATH = resolve(
  __dirname,
  'tavily-scenarios',
  'active.json',
)

/**
 * HAPPY planner scenario: queries for a frontend developer interview at
 * "字节跳动" return rich results across all 3 search dimensions.
 */
export const HAPPY_PLANNER_SCENARIO: TavilyScenario = {
  scenarios: [
    {
      query: '字节跳动 前端开发 面试经验 面经',
      results: [
        {
          title: '字节跳动前端面试经验分享 2025',
          content:
            '字节跳动前端面试通常分为4轮：技术面（2轮）、系统设计、HR面。' +
            '重点考察 React 原理、性能优化、工程化能力。面试官会深入问项目细节。',
          url: 'https://example.com/bytedance-fe-interview',
          score: 0.96,
        },
        {
          title: '字节跳动前端面经 - 牛客网',
          content:
            '一面：手写 Promise、实现深拷贝、React 事件机制。' +
            '二面：Webpack 优化、微前端、性能监控。三面：系统设计 - 设计一个实时协作编辑系统。',
          url: 'https://example.com/bytedance-frontend-面经',
          score: 0.92,
        },
      ],
    },
    {
      query: '字节跳动 技术栈 工程文化',
      results: [
        {
          title: '字节跳动前端技术栈概览',
          content:
            '字节跳动前端主要使用 React + TypeScript + SSR 架构。' +
            '内部有自研的微前端框架和构建工具链。强调性能指标和监控体系。',
          url: 'https://example.com/bytedance-tech-stack',
          score: 0.94,
        },
        {
          title: '字节跳动工程文化 - 技术博客',
          content:
            '字节跳动强调数据驱动和快速迭代。前端团队推行 Code Review 制度，' +
            '有完善的 CI/CD 流程和自动化测试体系。',
          url: 'https://example.com/bytedance-engineering-culture',
          score: 0.88,
        },
      ],
    },
    {
      query: '前端开发 常见面试题',
      results: [
        {
          title: '2025 前端高频面试题汇总',
          content:
            '包括：React Fiber 架构、虚拟 DOM 原理、闭包与作用域链、' +
            '浏览器渲染机制、HTTP 缓存策略、Webpack 构建优化、微前端方案对比。',
          url: 'https://example.com/common-fe-questions',
          score: 0.97,
        },
        {
          title: '前端系统设计面试指南',
          content:
            '常见系统设计题：设计前端监控系统、设计组件库、设计权限管理方案、' +
            '设计大型表单系统、设计前端构建流水线。',
          url: 'https://example.com/fe-system-design',
          score: 0.85,
        },
      ],
    },
    {
      query: 'default',
      results: [
        {
          title: '通用面试准备指南',
          content:
            '准备面试时重点复习：数据结构与算法、项目经验梳理、系统设计能力、' +
            '沟通表达能力。建议结合实际项目经验进行准备。',
          url: 'https://example.com/general-interview-prep',
          score: 0.75,
        },
      ],
    },
  ],
}

/**
 * BACKWARD-COMPAT scenario: returns empty results for all queries to
 * simulate no external search info (planner generates plan from resume+JD only).
 */
export const EMPTY_SEARCH_SCENARIO: TavilyScenario = {
  scenarios: [
    {
      query: 'default',
      results: [],
    },
  ],
}

/**
 * Write a scenario to the fixed active.json path. The backend's MockTavilyClient
 * re-reads the file on every invoke, so writing before each test is enough.
 */
export function writeTavilyScenarioFile(scenario: TavilyScenario): string {
  mkdirSync(dirname(SCENARIO_FILE_PATH), { recursive: true })
  writeFileSync(SCENARIO_FILE_PATH, JSON.stringify(scenario, null, 2), 'utf-8')
  return SCENARIO_FILE_PATH
}
