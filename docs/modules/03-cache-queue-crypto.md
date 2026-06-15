# M03 · 缓存 / 队列 / 加密

> 状态: draft · 所属领域: A · 优先级: P0
> 引用原文档: §2.2, §3.3, §11.1, §11.2

## 1. 需求摘要

接入三个横切基础设施:Redis(锁 / 缓存 / Pub-Sub)、ARQ Worker(异步任务)、AES-256-GCM 加密层(敏感字段)。**只搭框架与抽象**,具体的悲观锁实现归 M12,具体任务归各业务模块。

## 2. 验收标准

- [ ] Redis 异步客户端封装,提供单例 + 健康检查
- [ ] ARQ Worker 可独立启动,跑通示例任务 `dummy_task(delay=2)` 并返回结果
- [ ] AES-256-GCM 加密层:`encrypt(plaintext, context) → ciphertext`,`decrypt(ciphertext, context) → plaintext`,密钥从环境变量 / KMS 获取
- [ ] 加密 SQLAlchemy TypeDecorator:`EncryptedString` 字段透明加解密
- [ ] 全局限流装饰器:`@rate_limit(times=100, per_seconds=60, key="...")`,Redis token bucket 实现
- [ ] 跨请求审计:Redis Pub-Sub demo(发布 / 订阅一条消息)

## 3. 依赖与被依赖关系

**强依赖**: M01(项目骨架)
**弱依赖**: M02(可并行,但 SQLAlchemy TypeDecorator 需 M02 先就绪)
**被以下模块依赖**: M04(密码哈希 / 凭据加密)、M12(悲观锁)、M14(LangGraph 限流 + checkpoint)、M20(ARQ 清除任务)、M22(对账任务)
**外部依赖**: redis (asyncio), arq, cryptography, kms-client(可选)

## 4. 数据模型

无新表。但定义两个核心类型:

```python
class EncryptedString(TypeDecorator):
    """SQLAlchemy 透明加解密 TypeDecorator,基于 AES-256-GCM"""
    impl = BYTEA
    cache_ok = True

class RateLimit(BaseModel):
    times: int
    per_seconds: int
    key_template: str  # e.g. "tool:{name}:{user_id}"
```

## 5. 接口契约

**REST**: 无
**WebSocket**: 无
**核心 API**:
```python
# Redis
async def get_redis() -> Redis: ...

# ARQ
@worker_task
async def dummy_task(ctx, delay: int) -> dict: ...

# 加密
async def encrypt(plaintext: str, context: dict | None = None) -> bytes: ...
async def decrypt(ciphertext: bytes, context: dict | None = None) -> str: ...

# 限流
@rate_limit(times=100, per_seconds=60, key="...")
async def some_function(...): ...
```

## 6. 关键设计点

- **密钥管理(MVP)**: `MASTER_KEY` 环境变量(base64);后续可切换到 AWS KMS / 阿里云 KMS,通过 envelope 加密派生数据密钥
- **密钥轮换**: 加密时附加 `key_version` 字段,解密时按 version 路由;轮换通过 ARQ 后台任务批量重加密
- **context (AAD)**: AES-GCM 的 additional authenticated data,绑定 user_id / field_name,防止跨字段密文调换攻击
- **Redis 连接池**: `BlockingConnectionPool`,最大连接数 = 8 × CPU
- **ARQ 调度**: 任务命名 `{module}.{action}` 风格(如 `lifecycle.purge_soft_deleted`)
- **限流 key 模板**: 支持动态参数,如 `tool:query_resume:{user_id}` → 每用户每工具独立桶
- **降级**: Redis 不可用时 → 加密 / 哈希仍可用(纯计算);限流自动放行(fail-open,日志告警)

## 7. 待澄清

- **[A8]** monthly_token 重置 ARQ 任务(每月 1 日)的归属模块:本模块提供 Worker 框架,M04(账号)实现具体任务
- 密钥管理升级到 KMS 的时间窗口:MVP 用环境变量,生产建议尽快切换

## 8. 实现提示

- 文件: `backend/app/core/redis.py`、`backend/app/core/crypto.py`、`backend/app/core/rate_limit.py`、`backend/app/workers/main.py`、`backend/app/workers/tasks/dummy.py`
- 与 mockData 关系: 无
