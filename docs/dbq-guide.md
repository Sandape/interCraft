# dbq — 开发数据库快速访问工具

## 定位

`scripts/dbq.py` 是开发期专用的数据库快速探查工具，用于替代手写 ad-hoc SQL 或开 psql。

## 使用

```bash
# 从 backend/ 目录运行
cd backend

# 列出所有表
uv run python -m scripts.dbq tables

# 查看某个表的结构
uv run python -m scripts.dbq schema users

# 查看所有表行数
uv run python -m scripts.dbq count

# 查询某个表的前 N 行
uv run python -m scripts.dbq rows resume_branches -l 10

# 带 WHERE 条件
uv run python -m scripts.dbq rows users -w "status='active'" -o created_at

# 任意 SQL
uv run python -m scripts.dbq sql "SELECT id, email, display_name, status FROM users LIMIT 5"

# JSON 行输出（适合管道给 jq 或其他工具）
uv run python -m scripts.dbq sql "SELECT * FROM users" --json

# CSV 输出
uv run python -m scripts.dbq rows resume_blocks --csv

# 跨表搜索文本
uv run python -m scripts.dbq search "demo@intercraft.io"

# 外键关系
uv run python -m scripts.dbq fkeys resume_blocks

# 查询计划分析
uv run python -m scripts.dbq explain "SELECT count(*) FROM users"
```

## 边界准则

### 使用范围

| 允许 | 不允许 |
|---|---|
| 开发期数据探查 | 生产环境使用 |
| 调试测试数据 | 写操作（INSERT/UPDATE/DELETE/DDL） |
| 验证迁移结果 | 导出客户数据 |
| 检查 seed 数据状态 | 长时间锁表的查询 |
| 调试 RLS 行为 | 替代正式数据访问层 |

### 安全约束

1. **只读设计** — 工具不会校验 SQL 是否是 SELECT，你可以在 `sql` 命令中执行写操作，但这是**你的责任**避免误写。建议仅在明确需要时才用 `sql` 命令执行写操作，日常探查用 `rows / count / search` 即可。
2. **不要写入敏感信息到输出** — `--json` / `--csv` 输出可能被重定向到文件，注意文件中可能包含用户邮箱、密码哈希等敏感数据，用完清理。
3. **不在生产环境使用** — 脚本会校验 `APP_ENV=production` 并拒绝连接（待实现防御式检查），但仍需人为保证不在生产数据库 URL 下运行。
4. **session 级连接** — 每次命令执行创建新连接，执行完毕立即关闭，不会遗留连接。

### 性能边界

| 场景 | 建议 |
|---|---|
| 大表全表扫描 | 始终加 `-l` 限制行数 |
| JSONB 查询 | 避免 `rows` 命令直接查 JSONB 字段，用 `sql` 命令指定具体字段 |
| 搜索命令 | `search` 遍历所有文本列，大表上可能慢，建议先 `count` 确认表大小 |
| 长 SQL | `--json` 模式对大结果集更节省终端渲染开销 |

### 已知限制

- 使用 `asyncpg` 直连，不经过 SQLAlchemy ORM，因此 JSONB 字段以 Python dict 形式返回
- 不处理 RLS —— 连接时未设置 `app.user_id`，所以 RLS policy 中的 `(current_setting('app.user_id', true) = '')` 分支会匹配，看到所有行
- 不支持事务 —— 每条命令自动提交
- 远程数据库（当前 `81.71.152.210`）延迟约 30ms，频繁小查询注意累积时间

## 故障排除

```
# asyncpg 未安装
uv sync

# 连接拒绝
检查 backend/.env 中的 DATABASE_URL 是否正确
尝试 telnet <host> 5432 确认网络可达

# 表不存在
注意表名区分大小写，PG 会自动小写化
用 `tables` 命令确认准确名称
```
