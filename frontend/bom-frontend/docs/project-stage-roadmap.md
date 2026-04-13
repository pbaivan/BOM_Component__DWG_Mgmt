# BOM Component DWG Mgmt - Project Stage Roadmap

## 文档信息
1. 更新时间: 2026-04-13 (Stage 4 completion update)
2. 适用范围: BOM_Component__DWG_Mgmt 前后端协同改造
3. 推进原则: 先稳后快、单线推进、每阶段可回归

## 当前阶段结论
1. 当前处于 Stage 1-4 已完成状态: 后端基础架构重构、PR 快速门禁、SharePoint 服务深拆并行优化、前端服务/hooks/组件拆分均已完成。
2. 当前最强项在前后端结构清晰度与回归可执行性，下一阶段重点转向 Stage 5 的可观测性与质量门槛建设。

## 现状核对证据
1. 后端模块化已完成: backend/app/main.py, backend/app/db.py, backend/app/config.py, backend/app/routes/*, backend/app/services/*。
2. 后端 BOM 领域已拆分: backend/app/services/bom_models.py, backend/app/services/bom_utils.py, backend/app/services/bom_parser.py, backend/app/services/bom_records_service.py。
3. 兼容层已保留: backend/app/services/bom_data.py 作为兼容 facade，避免旧导入断裂。
4. 数据库连接池已落地: backend/app/db.py 使用 psycopg_pool.ConnectionPool，requirements 已包含 psycopg-pool。
5. 基线联调脚本已具备: backend/scripts/api_regression_smoke.py 与 backend/scripts/run_regression.ps1。
6. CI 已有手动 workflow: .github/workflows/backend-regression-smoke.yml。
7. CI 快速门禁已落地: .github/workflows/pr-quick-check.yml (pull_request + workflow_dispatch)。
8. SharePoint 服务已拆为 auth/search/file/utils 子模块，兼容门面仍为 backend/app/services/sharepoint_service.py。
9. SharePoint 多 target URL 已改为 asyncio.gather + Semaphore 受控并行。
10. 前端已完成分层: services/hooks/components 已落地，App.jsx 已收敛为页面编排层。

## 阶段定义与状态
1. Stage 1 - 基线与依赖完善: 已完成。
2. Stage 2 - 后端架构重构: 已完成。
3. Stage 3A - 门禁收口: 已执行(首版完成)。
4. Stage 3B - 后端复杂域治理(SharePoint): 已完成。
5. Stage 4 - 前端架构拆分: 已完成。
6. Stage 5 - 稳定性与可观测性强化: 未开始。

## 后续阶段推进步骤

## Stage 3A (先收口门禁)
1. 目标: 把现有回归能力从“可执行”提升到“可门禁”。
2. 执行结果:
3. 已新增 PR 快速门禁 workflow: .github/workflows/pr-quick-check.yml。
4. 已保持真实联调 workflow 手动触发: .github/workflows/backend-regression-smoke.yml。
5. 已覆盖前端最小门禁: npm run lint, npm run build。
6. 已在 backend/README.md 写入 quick gate 与 manual integration 区分说明。
7. 本地验证(2026-04-13): 前端 lint/build 通过，后端 compileall 与关键路由装配校验通过。
8. 验收标准:
9. PR 页面可见前后端快速检查结果。
10. 手动真实联调可稳定给出 pass/fail JSON 结果。

## Stage 3B (第二优先，SharePoint 深拆与并行化，已完成)
1. 目标: 降低 sharepoint_service.py 复杂度，并提升多目录搜索性能。
2. 操作步骤:
3. 先拆不改行为: 抽离认证、target 解析、单目录搜索、结果聚合模块。
4. 引入受控并行: 对 target_urls 使用 asyncio.gather + Semaphore 控并发。
5. 保持容错语义: 单 target 失败不拖垮全局，返回部分成功结果与失败摘要日志。
6. 增加缓存策略: 可选短期 token 缓存与重复请求去重。
7. 回归验证: 执行 backend/scripts/api_regression_smoke.py 覆盖 health/save/search/sp_file。
8. 验收标准:
9. 多 target 下搜索总耗时明显下降。
10. 输出字段结构保持兼容，前端无需同步改接口。
11. 回归脚本无新增失败项。
12. 执行记录(2026-04-13):
13. 已完成 sharepoint_auth.py / sharepoint_search.py / sharepoint_file_proxy.py / sharepoint_utils.py。
14. 已将 sharepoint_service.py 收敛为兼容 facade，路由层继续复用。
15. 已完成受控并行与容错语义，单 target 失败不会拖垮全局。
16. 已新增 token 缓存策略与并发锁保护，减少重复认证请求。
17. /api/search 已支持可选 include_debug=true 输出分 target 诊断信息，默认响应结构保持不变。
18. 已新增性能基准脚本 backend/scripts/sharepoint_search_benchmark.py，可输出 avg/p95 耗时与失败率。
19. 本地回归验证通过: health/save/search/sp_file 全部通过。

## Stage 4 (第三优先，前端组件化与服务层抽离)
1. 目标: 把 App.jsx 从单体拆成可维护的页面编排 + 组件 + hooks + services。
2. 操作步骤:
3. 先抽 API 服务层: src/services/api.js，迁出 fetchApiWithFallback 与 parseResponseBody。
4. 再抽业务 hooks: useBomUploadSave, useHistoryRecords, useDrawingSearch, useDragAndDropUpload。
5. 再抽 UI 组件: ExcelTable, ColumnFilter, DrawingPanel, HistoryModal, TopBar。
6. App.jsx 仅保留路由级状态编排和跨区交互。
7. 每次拆分后执行 npm run lint 和 npm run build，再执行后端 smoke 回归。
8. 验收标准:
9. App.jsx 缩减到页面编排级别。
10. 关键业务流(上传、保存、历史加载、SharePoint 搜索、预览下载)行为不变。
11. 前后端联调保持通过。
12. 执行记录(2026-04-13, Stage 4A):
13. 已新增 src/services/api.js，集中管理 API_BASE_CANDIDATES、fallback 请求与响应解析。
14. App.jsx 已改为复用服务层 API，不再内嵌 fetchApiWithFallback/parseResponseBody 实现。
15. 本地验证通过: npm run lint 与 npm run build 均通过。
16. 执行记录(2026-04-13, Stage 4B):
17. 已新增 src/hooks/useHistoryRecords.js，抽离历史记录加载/删除与弹窗状态管理。
18. 已新增 src/hooks/useDragAndDropUpload.js，抽离拖拽上传交互与窗口级文件拖放拦截。
19. App.jsx 已接入上述 hooks，历史记录与拖拽逻辑不再内嵌在页面主文件。
20. 本地验证通过: npm run lint 与 npm run build 均通过。
21. 执行记录(2026-04-13, Stage 4C):
22. 已新增 src/hooks/useDrawingSearch.js，抽离图纸搜索、目录聚合、缺失项统计、预览下载行为。
23. App.jsx 已移除 onMasterRowClicked/onDetailRowClicked 复杂搜索逻辑，改由 hook 承载。
24. 执行记录(2026-04-13, Stage 4D):
25. 已新增 src/hooks/useBomUploadSave.js，抽离上传/保存/历史加载/保存状态机。
26. 已新增组件: src/components/ColumnFilter.jsx, src/components/ExcelTable.jsx, src/components/DrawingPanel.jsx, src/components/HistoryModal.jsx, src/components/TopBar.jsx。
27. App.jsx 已收敛为页面编排，核心职责为状态拼装和组件组合。
28. 验证通过: npm run lint, npm run build, backend/scripts/api_regression_smoke.py (health/save/upload/search/sp_file 全通过)。

## Stage 5 (稳定性与运营化)
1. 目标: 为上线或长期维护准备可观测性与质量保障。
2. 操作步骤:
3. 统一后端结构化日志，增加 request_id 与关键耗时指标。
4. 增加前端错误边界与接口错误分类提示。
5. 增加后端关键单元测试与最小契约测试。
6. 增加性能基准: SharePoint 多目录查询基线和对比报表。
7. 验收标准:
8. 异常可定位。
9. 性能优化可量化。
10. 版本发布有明确质量门槛。

## 建议执行顺序
1. 先完成 Stage 3A 门禁收口。
2. 再完成 Stage 3B SharePoint 深拆和并行化。
3. 再推进 Stage 4 前端拆分，避免双线重构导致回归定位困难。(已完成)
4. 最后执行 Stage 5 的可观测性与质量强化。(下一阶段)

## 每阶段回归命令
```powershell
# 后端真实联调(本地自动启动后端)
powershell -ExecutionPolicy Bypass -File backend/scripts/run_regression.ps1 -StartServer

# 前端静态检查与构建
cd frontend/bom-frontend
npm run lint
npm run build
```

## 风险提示
1. 避免后端 SharePoint 深拆与前端大规模组件化同时进行。
2. 每次仅推进一个阶段并保留可回滚提交。
3. 外部依赖波动(SharePoint/网络)应通过脚本结构化失败输出保留证据。
