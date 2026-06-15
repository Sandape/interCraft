# Research: Phase 6 — 全局能力收尾

## 设计决策

### D1: M20 物理清除时间线

- **Decision**: 从用户发起注销请求算总共 90 天后物理清除。`scheduled_purge_at = NOW() + 90d`,无中间 `purged` 等待期。
- **Rationale**: 90 天是用户可见的单一数字,心理模型比「7+90=97 天」简单。7 天冷静期通过独立字段 `cancellation_deadline` 实现,两个时间互不干扰。
- **Alternatives considered**:
  - B: 7 天冷静期 → `purged` → 再过 90 天物理删除(共 97 天)。被拒绝原因是用户感知复杂。

### D2: 审计日志访问控制

- **Decision**: 双端点模式。`GET /api/v1/audit-logs`(用户自己的日志,RLS 过滤) + `GET /api/v1/admin/audit-logs`(全量,需 admin 角色)。
- **Rationale**: 用户自查场景(「我最近做了什么操作」)是高频需求;admin 全量查看是运维排障刚需。Phase 6 不实现 admin 角色管理后台,admin 角色通过 DB 直接标记 `User.role = 'admin'`。
- **Alternatives considered**:
  - A: 仅用户端。被拒绝是因为运维排障需要全量视角。
  - C: 完全公开。被拒绝,严重隐私风险。

### D3: 导出 ZIP 存储后端

- **Decision**: 本地文件系统,路径由 `EXPORT_STORAGE_PATH` 环境变量配置(开发默认 `/tmp/exports/`)。
- **Rationale**: 零外部依赖,实现简单。MVP 阶段导出量为低频操作(日导出估计 < 100 次),本地文件系统足够。72 小时后由 ARQ cron 清理过期文件。
- **Alternatives considered**:
  - B: S3 兼容对象存储。被拒绝是因为增加外部依赖和运维复杂度,MVP 阶段不需要。
  - C: 两者都支持。被拒绝是因为过度工程化。

### D4: 邮件发送失败降级

- **Decision**: 静默降级。邮件发送失败时:前端站内通知 + 后台日志告警,不阻止业务流程。
- **Rationale**: 邮件是辅助通知通道,站内通知是主通道。邮件失败不应阻塞注销/导出等核心流程。运维通过日志告警感知,可手动重试。
- **Alternatives considered**:
  - B: 同步重试 3 次后阻止操作。被拒绝,因为这会使用户在邮件系统故障时完全无法使用功能。
  - C: 异步重试 + dead_letter。被拒绝,MVP 阶段站内通知已足够,dead_letter 可后续补充。

### D5: 语音模式 deferred

- **Decision**: 语音模式不在 Phase 6 范围。`interview_sessions.mode` 字段保留但仅 `text` 模式有效。前端注释掉语音相关入口。
- **Rationale**: Phase 6 已包含 M20/M21/M22 + Settings + Resources + 订阅,范围足够。语音模式涉及浏览器 Web Speech API 的复杂交互,可独立作为一个后续阶段。
- **Alternatives considered**: 无(用户直接决策)。

### D6: admin 角色实现方式

- **Decision**: 通过 `User.role` 字段实现,取值 `user`(默认)或 `admin`。Phase 6 不实现 admin 管理后台;admin 角色通过 DB `UPDATE` 直接授予。
- **Rationale**: 最小实现。admin 是内部运维角色,不需要自助申请/审批流程。
- **Alternatives considered**:
  - B: 独立 admin 权限表。被拒绝,过度设计,一个字段足矣。

### D7: 订阅升级流程

- **Decision**: MVP 不接支付网关。订阅通过后台手动 `UPDATE` 变更,前端展示方案对比和「升级方案」CTA(跳转定价页或弹窗)。
- **Rationale**: 支付集成(Paddle/Stripe)本身是一个独立项目,不应阻塞 Phase 6 其余功能交付。手动升级可用于内部测试和早期用户。
- **Alternatives considered**: 无(MVP 阶段合理简化)。

### D8: Resources/Help 内容管理

- **Decision**: 初始内容通过 Markdown 文件由运营手动维护,后端读取后通过 API 暴露。后续可迁移到 CMS。
- **Rationale**: MVP 阶段内容量小(几十篇),Markdown 文件零运维成本。CMS 可在内容量增长后引入。
- **Alternatives considered**:
  - B: 直接存 DB 并通过 admin 页面管理。被拒绝,需要额外开发 admin UI。

### D9: 设备管理数据源

- **Decision**: 从已有 `sessions` 表派生,不新增设备注册表。字段: device_name / browser / ip / last_active_at。
- **Rationale**: Phase 1 已有 session 表记录登录信息,派生足够满足「查看设备列表 + 下线其他设备」功能。新增设备注册表会增加写路径复杂度。
- **Alternatives considered**: 无。

### D10: audit_logs 分区与保留

- **Decision**: 按 `created_at` 月分区,保留 12 个月。保留期满后自动删除旧分区。
- **Rationale**: audit_logs 是 append-only 表,数据量线性增长。月分区使得旧数据清理只需 `DROP TABLE`,比 `DELETE` 高效得多。12 个月保留期覆盖常见合规需求。
- **Alternatives considered**:
  - B: 保留 36 个月。被拒绝,MVP 阶段不需要,且会增加存储成本。
  - C: 不分区,使用 DELETE + VACUUM。被拒绝,大表 DELETE 性能差。

### D11: 导出数据格式

- **Decision**: ZIP 内含 JSON 数据文件(结构化) + Markdown 格式简历(人类可读)。JSON 结构对称,Markdown 可直接查看。
- **Rationale**: JSON 便于程序消费和重新导入;Markdown 便于用户直接阅读。两种格式互补,覆盖不同使用场景。
- **Alternatives considered**:
  - B: 仅 JSON。被拒绝,用户直接查看不便。

### D12: 导入格式支持

- **Decision**: 支持 JSON(与导出格式对称)和 Markdown(按 heading 识别块结构)两种格式。
- **Rationale**: JSON 导入适合「从本产品导出后重新导入」场景;Markdown 导入适合「用户从其他工具粘贴的简历」场景。
- **Alternatives considered**: 无。

---

## 技术调研

### PostgreSQL 分区表 (audit_logs)

使用 PostgreSQL 原生分区继承(`PARTITION BY RANGE (created_at)`)。每月初 ARQ cron 自动创建下月分区。12 个月后 ARQ cron 删除过期分区:

```sql
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY,
  actor_id UUID NOT NULL,
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id UUID,
  old_values JSONB,
  new_values JSONB,
  ip_address TEXT,
  user_agent TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (created_at);

CREATE TABLE audit_logs_202606 PARTITION OF audit_logs
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
```

### ARQ Cron 任务设计

Phase 6 新增 3 个 ARQ 任务:

1. **purge_expired_accounts** (每日): `scheduled_purge_at < NOW() AND status = 'soft_deleted'` → 标记为 `purged`
2. **physical_cleanup** (每周): `status = 'purged' AND updated_at < NOW() - 7d` → 物理删除用户数据(每批 100)
3. **cleanup_expired_exports** (每小时): `expires_at < NOW()` → 删除过期 ZIP 文件 + 数据库记录

### admin 角色鉴权

在 `AuthMiddleware` 中添加 `is_admin` 属性。admin 端点通过依赖注入检查:

```python
# backend/app/auth/dependencies.py
async def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != 'admin':
        raise HTTPException(403, detail="Admin access required")
    return current_user

# backend/app/audit/router.py
@router.get("/admin/audit-logs")
async def get_all_audit_logs(admin: User = Depends(require_admin), ...):
    ...
```
