# Scraw — Unified Scraping & Document Processing Workflow

## 工作流（7 步）

```
用户请求 → 1. 分析任务
           → 2. 选择工具
           → 3. [可选] 检查工具版本
           → 4. 加载子技能
           → 5. 执行抓取/处理
           → 6. 结构化输出
           → 7. 返回结果
```

---

### Step 1 — 分析任务

从用户请求中提取四个关键维度：

| 维度 | 要判断的内容 |
|------|-------------|
| **来源类型** | 静态网站 / JS 渲染 / 反爬保护 / API / 文档 (PDF/Excel/Word) |
| **规模** | 单页 / 分页列表 / 整站爬取 |
| **输出需求** | 原始数据 / 结构化 JSON / Markdown / 写入数据库 |
| **反爬级别** | 无 / 基础 / Cloudflare / 浏览器指纹 |

### Step 2 — 选择工具（决策矩阵）

| 场景 | 推荐工具 | 理由 |
|------|---------|------|
| 简单静态 HTML | **Scrapling** (`get`) | 最快，自适应解析 |
| JS 渲染、无反爬 | **Playwright** / **Crawl4AI** | 完整浏览器自动化 |
| Cloudflare / Turnstile | **Scrapling** (`stealthy-fetch`) | 内置绕过 |
| 强反爬 + 指纹检测 | **CloakBrowser** | 真实浏览器 Profile |
| 大规模多页爬取 | **Scrapy** / **Scrapling Spiders** | Pipeline、并发 |
| LLM 友好的结构化输出 | **Crawl4AI** | 内置提取策略 |
| PDF / Excel / Word | **文档处理** | AI 驱动格式检测 |
| 金融数据 API | **httpx**（任意工具内） | 直接 REST 调用 |

> 原则：从简单开始 → Scrapling get → Scrapling stealthy-fetch → CloakBrowser

### Step 3 — 可选：检查更新

如果是会话中首次使用某工具，加载 `tools/update/SKILL.md` 检查可用更新。

### Step 4 — 加载子技能

根据选定的工具，加载对应子技能并按其指令执行：

| 子技能 | 路径 | 用途 |
|--------|------|------|
| Playwright | `tools/playwright/SKILL.md` | 浏览器自动化 |
| CloakBrowser | `tools/cloakbrowser/SKILL.md` | 反检测浏览器 |
| Scrapling | `tools/scrapling/SKILL.md` | 自适应 HTTP 抓取 |
| Crawl4AI | `tools/crawl4ai/SKILL.md` | 异步爬取 + LLM 提取 |
| Scrapy | `tools/scrapy/SKILL.md` | 大规模爬虫框架 |
| 文档处理 | `tools/document-processing/SKILL.md` | PDF/Excel/Word AI 处理 |

### Step 5 — 执行抓取/处理

按照子技能的模式执行实际抓取或文档处理工作。

### Step 6 — 结构化输出

参考以下两个规范文件处理结果：

- `references/common-patterns.md` — 数据清洗、去重、规范化
- `references/output-formats.md` — 标准输出 Schema

### Step 7 — 返回结果给用户

---

## 关键规则

- 只抓取你有权访问的内容
- 遵守 `robots.txt` 和服务条款
- 大规模爬取要加延迟（保持礼貌）
- 不绕过付费墙、认证，不抓取个人/敏感数据
- 超过 100 页的爬取需要先征得用户同意
