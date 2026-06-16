# Quickstart: Personal Ability Profile

**Status**: Phase 1 output · **Date**: 2026-06-16

> 10 分钟快速验证能力画像模块:查看雷达图 → 自评 → 查看成长曲线 → 生成分享链接 → PDF 导出 → 管理员查看

## 前置条件

- Phase 1/2 基础设施已就位(PostgreSQL/Redis)
- `VITE_USE_MOCK=false`(真实 API 模式)
- Phase 2 migration 已执行(`uv run alembic upgrade head`)
- 新用户已注册(可通 Phase 1 注册流)
- 已有至少 1 次面试评分(可选,用于验证系统评分显示)

## 场景 1:查看能力画像仪表盘(SC-001)

```bash
# 1. 启动后端
uv run uvicorn app.main:app --reload &

# 2. 启动前端
npm run dev

# 3. 浏览器操作:
#    a. 登录测试用户(如 test@example.com / password123)
#    b. 导航到 /ability-profile
#    c. 观察雷达图显示:
#       - 6 维度(技术深度/架构能力/工程实践/沟通表达/算法能力/业务理解)
#       - 新用户:所有维度 actual=0, ideal=10(空态引导)
#       - 有面试记录用户:actual 显示系统评分
#    d. 下方能力列表:每个维度一行,显示分数和趋势
```

**预期时间**:≤ 2 分钟

**验证点**:
- [ ] 雷达图渲染 6 个维度轴,标签正确
- [ ] actual 和 ideal 两条 Radar 叠加显示
- [ ] 空态:无能力数据时显示引导提示
- [ ] 列表:每个维度卡片显示趋势指示器

## 场景 2:自评能力(SC-002)

```bash
# 浏览器操作:
#    a. 在 /ability-profile 页面,点击某个维度的「自评」按钮
#    b. 在弹出的评分组件中设置分数(0-10)
#    c. 可选添加备注「3年后端开发经验」
#    d. 提交

# API 验证:
curl -X PATCH -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"actual_score": 7.0}' \
  http://localhost:8000/api/v1/ability-dimensions/tech_depth
# 预期:返回更新后的 dimension
```

**预期时间**:≤ 3 分钟

**验证点**:
- [ ] 自评后雷达图即时更新
- [ ] 自评分数和系统评分在雷达图中用不同颜色区分
- [ ] 修改自评后,版本历史保留

## 场景 3:查看成长曲线(SC-005)

```bash
# 前置:需要 ability_dimensions_history 中有至少 2 条记录
# 可以通过 seed 数据或多次自评产生

# 浏览器操作:
#    a. 在 /ability-profile 页面,点击某个维度
#    b. 跳转到 /ability-profile/tech_depth
#    c. 观察 TimelineChart 显示历史分数变化

# API 验证:
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/ability-dimensions/history?dimension_key=tech_depth"
# 预期:返回历史数据点数组
```

**预期时间**:≤ 2 分钟

## 场景 4:分享能力画像(SC-004 / SC-006)

```bash
# 浏览器操作:
#    a. 在 /ability-profile 页,点击「分享」按钮
#    b. 设置可选过期时间(48 小时)
#    c. 勾选「设置 PIN」(可选)
#    d. 生成链接,复制

# 验证分享页:
#    在无痕浏览器中打开分享链接
#    预期:只读视图,无编辑控件,雷达图和列表完整

# API 直接测试:
# 生成分享链接
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"expires_in_hours": 48}' \
  http://localhost:8000/api/v1/ability-profile/share
# 预期:返回 { data: { token, url, ... } }

# 公开访问
curl "http://localhost:8000/api/v1/ability-profile/share/TOKEN_VALUE"
# 预期:返回只读能力画像数据

# 撤销
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/ability-profile/share/SHARE_ID
# 预期:204 No Content
```

**预期时间**:≤ 3 分钟

## 场景 5:PDF 导出(FR-018)

```bash
# 1. 触发导出
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/ability-profile/export
# 预期:202 { data: { export_id, status: "pending" } }

# 2. 查询状态(轮询,最多等 15 秒)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/ability-profile/exports/EXPORT_ID
# 预期:status 从 pending → processing → completed

# 3. 下载 PDF
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/ability-profile/exports/EXPORT_ID/download \
  -o ability-profile.pdf

# 4. 验证
ls -la ability-profile.pdf
# 预期:文件存在且 > 10KB
```

**预期时间**:≤ 15 秒

## 场景 6:管理员查看(FR-016 / FR-017)

```bash
# 前置:需要一个 admin 角色用户
# 假设 admin token 已获取

curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/ability-profile/admin/USER_ID_TO_VIEW
# 预期:返回该用户的完整能力画像(与用户端数据结构一致)

# 验证权限隔离:
curl -H "Authorization: Bearer $NORMAL_USER_TOKEN" \
  http://localhost:8000/api/v1/ability-profile/admin/SOME_USER_ID
# 预期:403 Forbidden
```

**预期时间**:≤ 1 分钟

## 完整 E2E 测试

```bash
# 一条命令跑完所有 E2E 测试
npx playwright test tests/e2e/sc-ability-profile.spec.ts

# 预期:所有测试通过(绿)
```

## E2E 测试覆盖

```
sc-ability-profile.spec.ts
├── 空态显示引导
├── 雷达图渲染 6 维度
├── 自评更新后雷达图刷新
├── 生成分享链接并验证公开访问
├── 撤销分享链接后访问返回 404
├── 触发 PDF 导出并验证文件生成
└── 非管理员访问 admin 端点返回 403
```
