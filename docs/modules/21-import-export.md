# M21 · 导入导出

> 状态: draft · 所属领域: F · 优先级: P1
> 引用原文档: §9.3(导出 / 导入)、§11.4(数据所有权)

## 1. 需求摘要

实现用户数据的「**一键全量导出**」与「**跨账号导入 / 合并**」流程,支撑 §11.4「数据所有权」条款。导出生成签名 zip(24h 一次性 URL),包含 9 类业务数据(用户 / 简历 / 错题 / 能力 / 任务 / 活动 / 面试报告 / AI 消息);导入支持「**新建账号(覆盖 / 合并)**」与「**现有账号追加**」两种模式,涉及加密字段的密钥重加密(参见 [A10])。本模块与 M20(生命周期)互补:M20 是「自己删」,M21 是「自己搬」。

## 2. 验收标准

- [ ] `POST /api/v1/account/exports` 提交导出任务(异步,ARQ 调度)
- [ ] `GET /api/v1/account/exports/{export_id}` 查询导出任务状态(pending / building / ready / expired / failed)
- [ ] 导出包结构:zip 内 9 个 JSONL 文件(每类实体一行 JSON)+ `manifest.json`(元数据 / 校验和 / schema 版本)
- [ ] 导出完成后生成**签名 URL**(S3 预签名,24h 过期),通过站内信 + 邮件通知
- [ ] 用户在 24h 内可下载;过期后 S3 对象 + DB 记录一并清理
- [ ] 加密字段在导出包内为**明文**(用户已通过二次确认 + 密码验证;详情参见 [A10])
- [ ] 导出记录写入 `audit_logs`(`action='data.exported'`)
- [ ] `POST /api/v1/account/imports` 提交导入任务(上传 zip + 选择模式:`new_account` / `merge_into_existing` / `overwrite_existing`)
- [ ] 导入流程:dry-run(预览 diff)→ 用户确认 → 真实导入 → 报告
- [ ] dry-run 返回:实体计数(新增 / 更新 / 冲突)+ 错误清单
- [ ] 导入后:AI 消息重绑到新 `user_id`;错题本去重(同 `question_hash` 合并 frequency)
- [ ] 加密字段(身份证 / 薪资 / 原始 AI 对话)导入时按**新用户的加密密钥**重新加密(参见 [A10])
- [ ] 大文件支持:导出包 > 100MB 时分卷(分多个 zip),导入时识别 multi-volume
- [ ] 单元测试:导出 → 导入 round-trip(数据完整性)
- [ ] 集成测试:跨账号搬运(账号 A 导出 → 账号 B 导入)

## 3. 依赖与被依赖关系

**强依赖**: M02(ORM)、M03(加密 / S3 客户端)、M04(账号)、M20(软删检查;导入不应导入已软删记录)
**弱依赖**: M22(audit 写入)
**被以下模块依赖**: M23(前端「我的数据」页)
**外部依赖**: S3 兼容对象存储;邮件服务(导出就绪通知)

## 4. 数据模型

**新表**:
```sql
export_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),
  status text NOT NULL DEFAULT 'pending',  -- pending | building | ready | expired | failed
  requested_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  ready_at timestamptz,
  expires_at timestamptz,  -- ready_at + 24h
  s3_bucket text,
  s3_key_prefix text,  -- 可能多卷
  total_size_bytes bigint,
  file_count int,  -- 1 或多卷
  manifest jsonb,  -- 完成时填入:每类实体计数 + schema_version + checksum
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

import_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id),  -- 目标账号
  source_user_id_hint uuid,  -- 来自 manifest,可为空(用户未透露)
  mode text NOT NULL,  -- new_account | merge_into_existing | overwrite_existing
  status text NOT NULL DEFAULT 'pending',  -- pending | dry_run | awaiting_confirm | importing | completed | failed
  uploaded_zip_path text,  -- S3 路径(用户上传的 zip)
  dry_run_report jsonb,  -- dry-run 结果(每类实体: 新增 N / 更新 M / 冲突 K)
  confirm_token text,  -- 用户确认 dry-run 后签发
  confirmed_at timestamptz,
  completed_at timestamptz,
  result_report jsonb,  -- 完成后填入:实际新增/更新/错误数
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
```

**导出包结构**(`exports/{export_id}/v1.zip` 或多卷):
```
manifest.json                 # {schema_version, exported_at, user_id_hash, counts, checksums}
users.jsonl                   # 1 行(用户基本信息,不含密码哈希)
resume_branches.jsonl
resume_blocks.jsonl
resume_versions.jsonl
error_questions.jsonl
ability_dimensions.jsonl
ability_history.jsonl
tasks.jsonl
activities.jsonl
interview_sessions.jsonl
interview_reports.jsonl
ai_messages.jsonl             # 注意:可能很大,6 月内全部
tool_call_logs.jsonl
README.txt                    # 用户可读的导出说明
```

**manifest.json 示例**:
```json
{
  "schema_version": "1.0.0",
  "exported_at": "2026-06-12T10:30:00Z",
  "user_id_hash": "sha256:abcd...",  // 不暴露原始 user_id
  "counts": {
    "users": 1,
    "resume_branches": 3,
    "resume_blocks": 42,
    ...
  },
  "checksums": {
    "users.jsonl": "sha256:...",
    "resume_branches.jsonl": "sha256:...",
    ...
  },
  "encryption": {
    "scheme": "plaintext",  // 用户已通过二次确认
    "re_encryption_required_on_import": true
  }
}
```

## 5. 接口契约

**REST**:
| Method | Path | 说明 |
|---|---|---|
| POST | `/api/v1/account/exports` | 提交导出 `{password_confirm, scope?: "all" \| "subset"}` |
| GET | `/api/v1/account/exports` | 列出历史导出任务 |
| GET | `/api/v1/account/exports/{export_id}` | 查询单个导出任务 + 临时下载 URL |
| POST | `/api/v1/account/imports` | 上传 zip + 提交导入 `{mode, dry_run: true}` |
| POST | `/api/v1/account/imports/{import_id}/confirm` | 确认 dry-run 结果,开始真实导入 `{confirm_token}` |
| GET | `/api/v1/account/imports/{import_id}` | 查询导入进度与结果 |

**ARQ 任务**:
```python
@worker_task
async def build_export(ctx, export_id: UUID, user_id: UUID):
    """从业务表抽数据 → 写 JSONL → 打包 zip → 上传 S3 → 生成签名 URL"""

@worker_task
async def execute_import(ctx, import_id: UUID, user_id: UUID):
    """下载 zip → 校验 manifest → 按 mode 写入 → 报告"""

@worker_task
async def cleanup_expired_exports(ctx):
    """每小时扫:expires_at < now() AND status='ready' → 删 S3 对象 + 标 expired"""
```

**签名 URL**: 由 S3 SDK 生成,`ExpiresIn=24*3600`,URL 不落库(每次查询时实时生成)。

## 6. 关键设计点

- **导出范围**:`scope='all'` 导全部;`scope='subset'` 导用户勾选的类别(通过 `include: ["resume_branches", "error_questions"]` 传入)
- **导出流式处理**:避免 OOM,逐类流式 cursor 读取 → 写 JSONL → 增量打包 zip(`zipstream` 库)
- **二次确认**:导出接口需 `password_confirm`(再次输入密码),防 CSRF / 误触
- **大文件分卷**:zip 大小超 100MB 自动分卷(`export_job.file_count > 1`),每卷独立签名 URL,用户下载后本地 cat 合并
- **导入 dry-run**:不写任何业务表,只生成 diff 报告(`新增 N 条 / 更新 M 条 / 冲突 K 条`),让用户确认
- **导入模式**:
  - `new_account`:用 manifest 中的 email 创建新账号(若已存在则报错)
  - `merge_into_existing`:目标账号已存在,逐实体按主键 / 唯一键合并(默认 `skip`,可指定 `overwrite`)
  - `overwrite_existing`:**先软删目标账号的所有数据** → 再导入(危险操作,需 super_admin 或显式二次确认)
- **去重策略**:
  - 错题本:按 `question_hash` 合并,`frequency` 累加
  - 简历分支:按 `(user_id, name)` 唯一,重名时追加 `(imported at {ts})`
  - 任务 / 活动流:不导入(带时间戳,跨账号无意义)
  - 能力画像:导入但不覆盖现有(取较大值)
  - AI 消息:全部导入,`source='imported'` 标记
- **加密字段重加密**(参见 [A10]):
  - 身份证 / 薪资 / 原始 AI 对话:导出时**不解密**(导出包内是密文 + 原始 aad),导入时**不导入**(避免密钥泄露);改为写入「需在新账号重新录入」提示
  - 仅对 PII 字段(email / phone / display_name)做明文导出 / 重新写入
- **导入幂等**:同一 zip + 同一 import_id 重复提交,返回原结果(用 `import_jobs.id` 做幂等键)
- **可观测**:导出 / 导入全链路写入 `audit_logs`,失败时含错误堆栈
- **__version__ = "1.0.0"**

## 7. 待澄清

- **[A10]** 加密字段(身份证 / 薪资 / AI 原始对话)在导出包内的形式:本模块采用**密文 + 提示用户重新录入**方案,需产品确认是否符合 §11.4「数据所有权」的字面要求
- 跨账号导入是否需要原账号授权:GDPR 不要求,但产品可加「原账号生成 share_token」的流程
- 大于 1GB 的 AI 消息全量导出耗时:建议超过阈值时分卷 + 异步通知(用户先继续用,导出好再下载)
- 导入后的 AI 消息是否要触发能力画像重算:不触发(由 M18 异步任务按需重算)

## 8. 实现提示

- 文件:
  - `backend/app/services/export_service.py`(`ExportService.build_manifest / stream_jsonl / package_zip`)
  - `backend/app/services/import_service.py`(`ImportService.validate_manifest / dry_run / execute / merge_entities`)
  - `backend/app/workers/tasks/exports.py` / `imports.py`
  - `backend/app/api/v1/account_exports.py` / `account_imports.py`
  - `backend/app/schemas/export_manifest.py`(pydantic 模型)
- 复用: M02 BaseRepository(流式 cursor);M03 encryptor;M20 软删过滤
- 依赖库:`zipstream-ng`(流式打包)、`smart-open`(S3 多卷)
- 与 mockData 关系:无(mockData 是新账号示例数据,导入导出不涉及)
- 测试:`tests/integration/import_export/` round-trip 测试 + 跨账号搬运测试
