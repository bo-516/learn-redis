from h import *
CH = dict(id="ops", code="OPS", stage=4, name="高手：内存、监控、性能排障与安全",
desc="maxmemory 与淘汰策略（LRU/LFU）、内存碎片、INFO/SLOWLOG/LATENCY、大 key 与热 key、生产配置与 ACL。",
lesson=r'''
## 1. 内存上限与淘汰策略

```
CONFIG SET maxmemory 8gb
CONFIG SET maxmemory-policy allkeys-lfu
```

当内存达到 `maxmemory` 时，写命令触发淘汰：

| 策略 | 范围 | 算法 |
|---|---|---|
| `noeviction`（**默认**） | — | 不淘汰，写命令返回 OOM 错误，读正常 |
| `allkeys-lru` | 所有 key | 最近最少使用 |
| `allkeys-lfu` | 所有 key | 最不经常使用（4.0+） |
| `allkeys-random` | 所有 key | 随机 |
| `volatile-lru` | 设置了过期时间的 key | LRU |
| `volatile-lfu` | 设置了过期时间的 key | LFU |
| `volatile-random` | 设置了过期时间的 key | 随机 |
| `volatile-ttl` | 设置了过期时间的 key | 剩余 TTL 最短的优先 |

> 以上是经典的 8 种策略，新版本可能新增策略，以所用版本的 redis.conf 说明为准。

**选择建议**：纯缓存 → `allkeys-lfu` 或 `allkeys-lru`；缓存与持久数据混用 → `volatile-*`（但持久数据最好放在单独的实例中）；不能丢数据 → `noeviction` + 监控告警。注意 `volatile-*` 策略下如果没有可淘汰的 key，行为与 noeviction 相同。

### 近似 LRU 与 LFU
- Redis 的 LRU 是**近似**的：不维护全局链表，而是每次随机采样 `maxmemory-samples`（默认 5）个 key，淘汰其中最久未访问的（配合淘汰池提高精度）。每个对象有 24 位的 LRU 时钟字段；
- LFU 复用这 24 位：16 位记录上次递减时间，8 位是**对数计数器**（最大 255，访问越多增长越慢，由 `lfu-log-factor` 控制），并随时间衰减（`lfu-decay-time`，默认 1 分钟）。LFU 能避免"偶尔被扫描一次的冷数据把热数据挤出去"的问题；
- `OBJECT IDLETIME key`（LRU 策略下）、`OBJECT FREQ key`（LFU 策略下）可以观察。

## 2. 内存分析

```
INFO memory
MEMORY USAGE key [SAMPLES n]
MEMORY STATS
MEMORY DOCTOR
```
关键指标：
- `used_memory`：Redis 分配器分配的内存（数据 + 内部结构）；
- `used_memory_rss`：操作系统看到的进程常驻内存；
- `mem_fragmentation_ratio` = rss / used_memory：
  - **> 1.5**：碎片较多（频繁修改不同大小的值），可以开启 `activedefrag yes` 主动整理（jemalloc 支持），或者在从库重启后切换；
  - **< 1**：部分内存被换出到 swap，延迟会急剧上升，必须处理；
- `used_memory_peak`：历史峰值；
- 复制缓冲区、客户端输出缓冲区、AOF 缓冲区也会占用内存（`mem_clients_normal`、`mem_replication_backlog` 等）。

**省内存的技巧**：控制 key 长度；小对象用 Hash 聚合以利用 listpack 编码；值序列化选用更紧凑的格式（Protobuf/MessagePack）并对大文本压缩；合理设置 TTL；用 Bitmap/HyperLogLog 替代大集合。

## 3. 监控与诊断命令

| 命令 | 用途 |
|---|---|
| `INFO [section]` | server、clients、memory、persistence、stats、replication、cpu、commandstats、keyspace 等 |
| `SLOWLOG GET 10` | 执行时间超过 `slowlog-log-slower-than`（默认 10000 微秒 = 10ms）的命令，最多保留 `slowlog-max-len` 条 |
| `LATENCY DOCTOR` / `LATENCY LATEST` | 延迟事件分析（需设置 `latency-monitor-threshold`） |
| `CLIENT LIST` / `CLIENT KILL` | 客户端连接信息（输出缓冲区、空闲时间、正在执行的命令） |
| `MONITOR` | 打印所有命令，**严重影响性能**，生产只能短时间使用 |
| `redis-cli --stat` / `--latency` / `--bigkeys` / `--memkeys` / `--hotkeys` | 命令行诊断工具 |

**重点监控指标**：
- 命中率：`keyspace_hits / (keyspace_hits + keyspace_misses)`；
- `instantaneous_ops_per_sec`；
- `connected_clients`、`blocked_clients`、`rejected_connections`；
- `used_memory` 与 maxmemory 的比例、`evicted_keys`、`expired_keys`；
- `mem_fragmentation_ratio`；
- 主从 `master_repl_offset` 差值、`master_link_status`；
- `latest_fork_usec`、`rdb_last_bgsave_status`、`aof_last_write_status`；
- 慢日志数量变化。

常用 Prometheus 的 `redis_exporter` + Grafana 构建监控大盘。

> 注意：SLOWLOG 只统计**命令执行时间**，不包含网络传输和排队时间。客户端看到超时而慢日志为空时，要排查网络、客户端连接池、主线程被其他命令阻塞（排队）、fork、swap 等问题。

## 4. 大 key 与热 key

### 大 key
一般认为：String 值 > 10KB，或者集合元素数 > 5000 / 总大小 > 10MB 就算大 key（各公司标准不同）。
危害：读写耗时长、阻塞主线程；网络流量大；DEL 阻塞；Cluster 中数据倾斜、迁移困难；导致复制和持久化压力。
发现：`redis-cli --bigkeys` / `--memkeys`（基于 SCAN，可加 `-i 0.1` 降低影响）；`MEMORY USAGE`；离线分析 RDB（如 redis-rdb-tools 等工具）。
治理：拆分（按字段或取模拆成多个 key）、压缩、只读取需要的部分（HSCAN、LRANGE 分页）、`UNLINK` 删除、从设计上避免把无界集合放进一个 key。

### 热 key
单个 key 的 QPS 过高（如热门商品、明星微博），使所在节点 CPU/网卡打满。
发现：`redis-cli --hotkeys`（需 LFU 策略）、客户端/代理层统计、`MONITOR` 抽样（谨慎）、云厂商的热 key 分析。
治理：**本地缓存**（最有效）；**热 key 复制多份**（`key:1`…`key:N`，读随机访问一个）；读写分离；限流。

## 5. 常见延迟问题排查清单

1. 慢命令：`SLOWLOG`、`INFO commandstats`（看 usec_per_call）——KEYS、HGETALL、SMEMBERS、ZRANGE 大范围、SORT、长 Lua；
2. 大 key 读写与删除；
3. 大量 key **集中过期**（主动过期循环占用时间）；
4. fork（`latest_fork_usec`）与 THP；
5. AOF `always` 或磁盘慢导致 fsync 阻塞（日志中出现 "Asynchronous AOF fsync is taking too long"）；
6. 内存不足开始使用 **swap**（`mem_fragmentation_ratio < 1`，查看 `/proc/<pid>/smaps` 中 Swap 字段）；
7. 达到 maxmemory 后**淘汰**大量 key；
8. CPU 被其他进程抢占、绑核问题；网络问题；
9. 连接数过多、频繁创建连接（客户端应使用连接池）；
10. `redis-cli --intrinsic-latency 100` 测量宿主机的固有延迟（虚拟机可能较高）。

## 6. 生产配置与安全

```
bind 10.0.0.1                 # 只监听内网
protected-mode yes
port 6379
requirepass <强密码>          # 或使用 ACL
maxmemory 8gb
maxmemory-policy allkeys-lfu
timeout 300                   # 关闭空闲连接
tcp-keepalive 300
maxclients 10000
appendonly yes
appendfsync everysec
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
lazyfree-lazy-user-del yes
slowlog-log-slower-than 10000
latency-monitor-threshold 100
```

**ACL（6.0+）**：
```
ACL SETUSER app on >S3cret ~app:* &* +@read +@write -@dangerous
ACL SETUSER readonly on >pwd ~* +@read
ACL LIST / ACL WHOAMI / ACL LOG
```
- 不要把 Redis 暴露在公网（历史上大量通过未授权访问写入 SSH 公钥、计划任务的入侵事件）；
- 禁用或限制危险命令：`FLUSHALL`、`FLUSHDB`、`KEYS`、`CONFIG`、`DEBUG`（推荐用 ACL 的 `-@dangerous`，旧方法是 `rename-command`）；
- 不要用 root 运行；开启 TLS（`tls-port`）保护跨机房流量；
- 系统层：`vm.overcommit_memory=1`、关闭 THP、`net.core.somaxconn` 与 `tcp-backlog` 匹配、合理的 `ulimit -n`。
''',
quiz=[
S(1,"Redis 默认的 `maxmemory-policy` 是？",["allkeys-lru","volatile-lru","noeviction","allkeys-lfu"],2,r'''
默认是 **noeviction**：内存达到上限后不淘汰任何 key，写命令返回 `OOM command not allowed when used memory > 'maxmemory'`，读命令正常。做缓存时一定要显式配置 maxmemory 和淘汰策略，否则缓存写满就会写失败。''',hot=True),
S(1,"纯缓存场景（所有数据都可以从数据库重建），通常推荐的淘汰策略是？",["noeviction","allkeys-lru 或 allkeys-lfu","volatile-ttl","不设置 maxmemory"],1,r'''
纯缓存应该在所有 key 中淘汰"最不常用"的，`allkeys-lfu` 对访问频率的识别更准确，能抵抗偶发的全量扫描；`allkeys-lru` 也很常用。
- A：缓存写满后报错；
- C：只淘汰带 TTL 的 key，且只看 TTL 而不看访问热度；
- D：在 64 位系统上默认 maxmemory 为 0（不限制），内存会无限增长直到被 OOM Killer 杀掉或使用 swap。''',hot=True),
T(1,"`SLOWLOG` 记录的时间包含了网络传输和命令在队列中等待的时间。",False,r'''
**错误。** 慢日志只记录**命令执行本身**的时间（不包括 I/O 与排队）。因此客户端超时但慢日志为空是很常见的情况：可能是网络问题、连接池耗尽，或者前面有别的慢操作（fork、大 key 删除、过期集中清理）导致命令排队。'''),
S(1,"`slowlog-log-slower-than` 的默认值是 10000，单位是？",["毫秒","微秒","秒","纳秒"],1,r'''
单位是**微秒**，10000 微秒 = **10 毫秒**。对于高性能场景，很多团队会调低到 1000（1ms）。设置为 0 表示记录所有命令，负数表示关闭慢日志。'''),
M(1,"以下哪些属于生产环境 Redis 的安全措施？（多选）",["只绑定内网 IP，不暴露在公网","设置强密码或使用 ACL 进行权限控制","用 ACL 禁用 FLUSHALL、KEYS、CONFIG 等危险命令","使用 root 用户运行，方便管理","跨机房传输开启 TLS"],[0,1,2,4],r'''
A、B、C、E 都是推荐做法。
D 错：用 root 运行时，一旦被入侵（例如利用 `CONFIG SET dir` + `SAVE` 写入 `/root/.ssh/authorized_keys`），攻击者可以直接获得 root 权限。应使用专门的低权限用户运行。''',hot=True),
S(2,"`INFO memory` 中 `mem_fragmentation_ratio` 为 0.6，说明？",["内存碎片很少，状态非常好","RSS 小于 Redis 分配的内存，很可能部分内存被交换到 swap，延迟会显著升高","内存碎片严重，需要重启","Redis 使用了 60% 的 maxmemory"],1,r'''
比值 = used_memory_rss / used_memory。**小于 1** 意味着操作系统中驻留的物理内存比 Redis 认为自己使用的还少，通常是被换出到 swap 了，此时访问会触发磁盘 I/O，延迟急剧上升。应增加内存、降低 maxmemory、关闭或减少 swap 使用。
- C 描述的是比值明显大于 1（如 > 1.5）的情况；
- D：碎片率与 maxmemory 无关。''',hot=True),
S(2,"Redis 的 LRU 淘汰是怎么实现的？",["维护一个包含所有 key 的双向链表，严格按访问时间淘汰","随机采样若干个 key（maxmemory-samples，默认 5），结合淘汰池淘汰其中最久未被访问的","按 key 的字典序淘汰","按 key 的创建时间淘汰"],1,r'''
Redis 使用**近似 LRU**：每个对象记录 24 位的最后访问时钟，淘汰时随机采样并维护一个大小为 16 的候选池，淘汰空闲时间最长的。增加 `maxmemory-samples` 可以更接近真正的 LRU，但消耗更多 CPU。
A：真正的 LRU 需要为每个 key 维护链表指针，并且每次访问都要移动节点，内存和 CPU 开销都很大，所以 Redis 没有采用。'''),
S(2,"使用 `redis-cli --hotkeys` 查找热 key 的前提是？",["开启 AOF","maxmemory-policy 设置为 LFU 相关策略（allkeys-lfu 或 volatile-lfu）","开启 Cluster 模式","开启 MONITOR"],1,r'''
`--hotkeys` 通过 SCAN 遍历 key 并调用 `OBJECT FREQ` 获取访问频率计数器，而这个计数器只在 **LFU** 淘汰策略下维护，否则会报错。其他选项都不是前提条件。'''),
M(2,"以下哪些是大 key 的危害？（多选）",["读写大 key 耗时长，阻塞主线程","占用大量网络带宽","删除时可能长时间阻塞（同步 DEL）","在 Cluster 中造成节点间内存分布不均，且迁移困难","大 key 会自动被 Redis 拆分，没有危害"],[0,1,2,3],r'''
A–D 都是大 key 的典型危害；此外还会放大复制、持久化的开销。
E 错：Redis 不会自动拆分 key，一个 key 永远属于一个槽、一个节点，只能由业务设计来拆分。''',hot=True),
S(2,"某个热点商品 key 的读 QPS 达到 20 万，把所在 Cluster 节点的 CPU 打满。**最有效**的第一步措施是？",["给该 key 设置更短的 TTL","在应用层增加本地缓存（如 Caffeine），短 TTL 缓存该商品信息","增加该节点的内存","把淘汰策略改为 allkeys-lfu"],1,r'''
热 key 的问题是**单节点请求集中**，本地缓存能在应用进程内直接拦截绝大部分读请求，是最直接有效的手段。另一种方法是把该 key 复制成多个副本（`product:1:0..N`），读时随机选择，从而分散到不同的槽/节点。
- A：缩短 TTL 只会增加回源压力；
- C：问题不是内存；
- D：淘汰策略与 QPS 无关。''',hot=True),
F(2,"写出查看最近 10 条慢日志的命令。",["SLOWLOG GET 10"],r'''
`SLOWLOG GET 10`。每条记录包含：唯一 ID、时间戳、执行耗时（微秒）、命令及参数、客户端地址和名称。`SLOWLOG LEN` 查看条数，`SLOWLOG RESET` 清空。慢日志存在内存中，长度由 `slowlog-max-len` 控制，应定期采集到监控系统中。'''),
F(2,"写出一条命令：查看 key `user:1` 占用的内存字节数。",["MEMORY USAGE user:1"],r'''
`MEMORY USAGE user:1` 返回 key 及其值占用的字节数（包括内部开销）。对于集合类型默认采样 5 个元素来估算，可加 `SAMPLES 0` 计算全部元素（大 key 上会很慢）。'''),
S(3,"关于 LFU 中的访问计数器，正确的是？",["每次访问都精确 +1，最多记录到 2^32","是一个 8 位的对数计数器，访问越多增长越慢，并会随时间衰减","LFU 只考虑访问次数，不考虑时间","LFU 需要额外开启 lfu-enabled 配置"],1,r'''
LFU 计数器只有 8 位（最大 255），采用**概率递增**：当前值越大，访问时增加的概率越小（受 `lfu-log-factor` 控制，默认 10，约 100 万次访问才能达到 255）。同时按 `lfu-decay-time`（默认 1 分钟）衰减，因此过去很热、现在不再访问的 key 会逐渐变冷。新 key 的初始值是 5，避免刚写入就被淘汰。
D 错：只需把 maxmemory-policy 设置为 LFU 策略即可，不存在 lfu-enabled 配置。'''),
T(3,"在 `volatile-lru` 策略下，如果所有 key 都没有设置过期时间，内存达到上限时 Redis 会退而淘汰没有过期时间的 key。",False,r'''
**错误。** volatile-* 策略**只**在设置了过期时间的 key 中选择淘汰对象。如果没有可淘汰的 key，行为与 noeviction 相同：写命令返回 OOM 错误。这是混用缓存与持久数据时的一个常见坑。'''),
S(3,"客户端频繁报超时，但 SLOWLOG 中没有慢命令，`INFO stats` 中的 `latest_fork_usec` 为 800000。最可能的原因是？",["网络带宽不足","fork 耗时约 800 毫秒，期间主线程阻塞，请求排队导致超时","AOF 文件损坏","客户端连接数太少"],1,r'''
`latest_fork_usec` 的单位是微秒，800000 微秒 = **800 毫秒**，fork 期间主线程无法处理任何请求，而 fork 不是命令，不会进入慢日志。应控制实例内存大小、关闭 THP、避免在高峰期做 BGSAVE/AOF 重写，或把持久化放到从库。其他选项与这些现象不匹配。'''),
],
bank=[
B(1,"Redis 有哪些内存淘汰策略？如何选择？",r'''
8 种经典策略：
- `noeviction`（默认）：不淘汰，写入报错；
- `allkeys-lru` / `allkeys-lfu` / `allkeys-random`：在所有 key 中淘汰；
- `volatile-lru` / `volatile-lfu` / `volatile-random` / `volatile-ttl`：只在设置了过期时间的 key 中淘汰。

选择：
- 纯缓存：`allkeys-lfu`（有明显热点时）或 `allkeys-lru`；
- 缓存与必须保留的数据混存：`volatile-lru/lfu`，但更推荐拆分为不同实例；
- 访问概率均匀：`allkeys-random`；
- 想让快过期的先淘汰：`volatile-ttl`；
- 数据不能丢：`noeviction` + 告警 + 扩容。

区分**过期删除**（key 到期后删除）和**内存淘汰**（内存满了主动删除未过期的 key），两者是不同的机制。''',hot=True),
B(2,"Redis 的 LRU 和 LFU 是怎么实现的？LFU 解决了 LRU 的什么问题？",r'''
**近似 LRU**：每个 redisObject 有 24 位 `lru` 字段记录最后访问的时钟（秒级精度）。淘汰时随机采样 `maxmemory-samples` 个 key，按空闲时间放入大小为 16 的**淘汰池**，淘汰空闲最久的。采样数为 10 时已非常接近真正的 LRU。

**LFU**（4.0+）：同一 24 位字段拆成 **16 位最后衰减时间（分钟）+ 8 位对数计数器**。
- 访问时按概率增加计数：`p = 1 / ((counter - 5) * lfu_log_factor + 1)`；
- 根据距离上次衰减经过的分钟数，按 `lfu-decay-time` 递减计数；
- 新对象计数初始为 5。

LRU 的问题：一次性的批量扫描（比如导出任务把所有冷数据读一遍）会让冷数据的"最近访问时间"变新，从而把真正的热点数据挤出去。LFU 看的是**访问频率**，偶尔一次访问对计数影响很小，因此能更好地保留热点。''',hot=True),
B(2,"如何发现和处理大 key？",r'''
**定义**（参考值）：String > 10KB；Hash/List/Set/ZSet 元素 > 5000 或总大小 > 10MB。

**发现**：
1. `redis-cli --bigkeys`：按元素数量统计每种类型最大的 key（基于 SCAN，`-i 0.01` 控制扫描间隔）；
2. `redis-cli --memkeys`：按内存统计；
3. `MEMORY USAGE key`；
4. 离线分析 RDB 文件，不影响线上（最推荐用于全面盘点）；
5. 监控：网卡流量突增、慢日志中出现 HGETALL/SMEMBERS 等。

**处理**：
1. **拆分**：大 Hash 按 `field 的哈希 % N` 拆成 N 个小 Hash；大 List 按时间或分页拆分；
2. **压缩**：对大的 String 值使用 gzip/snappy 等压缩；
3. **按需读取**：HSCAN、HMGET、LRANGE 分页、ZRANGE 带 LIMIT，避免全量读取；
4. **安全删除**：`UNLINK`，或开启 lazyfree；4.0 之前要用 HSCAN + HDEL 分批删除；
5. 设计阶段就避免无界增长的集合（例如设置最大长度、定期裁剪）。''',hot=True),
B(2,"如何发现和处理热 key？",r'''
**发现**：
1. `redis-cli --hotkeys`（需要 LFU 策略）；
2. 客户端 SDK 埋点统计 key 的访问频率（最准确）；
3. 代理层（如 Twemproxy、云数据库 Proxy）统计；
4. 短时间 `MONITOR` 抽样（对性能影响大，谨慎）；
5. 抓包分析；
6. 云厂商提供的热 key 分析功能。

**处理**：
1. **本地缓存**：在应用进程中缓存热 key，短 TTL，变更时广播失效；
2. **多副本**：把热 key 复制成 `key_0 ... key_N`，分布到不同节点，读时随机选择，写时更新全部；
3. **读写分离**：增加从库分担读请求；
4. **限流与降级**：保护 Redis 不被打垮；
5. 预判：大促前对热门商品进行预热和本地缓存。''',hot=True),
B(2,"Redis 突然变慢了，你会如何排查？",r'''
按"**先看命令，再看资源，最后看外部**"的顺序：

1. **确认是否真的慢**：`redis-cli --latency` 对比基线；`--intrinsic-latency` 看宿主机固有延迟；
2. **慢命令**：`SLOWLOG GET`、`INFO commandstats` 查看 `usec_per_call` 高的命令；是否有 KEYS、HGETALL 大 key、大范围 ZRANGE、SORT、长 Lua；
3. **大 key**：`--bigkeys`、网卡流量；
4. **集中过期**：`INFO stats` 中 `expired_keys` 是否在整点暴增，检查是否给 TTL 加了随机值；
5. **淘汰**：内存是否达到 maxmemory，`evicted_keys` 是否快速增长；
6. **fork**：`latest_fork_usec`，是否在 BGSAVE/AOF 重写；THP 是否关闭；
7. **AOF**：`appendfsync always`、磁盘 I/O 繁忙（iostat），日志中是否有 fsync 过慢的告警；
8. **swap**：`mem_fragmentation_ratio < 1`，`/proc/<pid>/smaps` 中的 Swap；
9. **CPU**：主线程 CPU 是否打满，是否被其他进程抢占，是否需要绑核或开启 io-threads；
10. **连接**：`connected_clients`、短连接过多、连接池配置；
11. **网络**：带宽、丢包、跨机房。

`LATENCY DOCTOR` 可以给出延迟事件的自动分析建议。''',r'''
回答时最好结合一个真实或假设的案例，例如："某次整点延迟尖刺，排查发现是一批缓存 key 在同一时间写入且 TTL 相同，整点集中过期，主动过期循环占用了大量 CPU，同时缓存回源压力增大。修复方法是给 TTL 加上 0~300 秒的随机值。"''',hot=True),
B(2,"内存碎片是怎么产生的？如何处理？",r'''
**产生原因**：
1. jemalloc 按固定大小的档位分配内存（8、16、32、48、64…字节），申请 20 字节实际分配 32 字节，存在内部碎片；
2. 频繁修改值的大小、删除 key 后释放的内存块零散分布，无法被其他大小的申请复用，也无法归还给操作系统。

**判断**：`mem_fragmentation_ratio = used_memory_rss / used_memory`，长期 > 1.5 说明碎片较多（如果 used_memory 很小，比值大也不必担心）。

**处理**：
1. 开启**主动碎片整理**：`activedefrag yes`，并配置 `active-defrag-ignore-bytes`、`active-defrag-threshold-lower` 和 CPU 占用比例 `active-defrag-cycle-min/max`；
2. `MEMORY PURGE` 让 jemalloc 释放部分脏页；
3. 重启实例（先切换到从库）可以彻底消除碎片。'''),
B(1,"INFO 命令中你最关注哪些指标？",r'''
- **Clients**：`connected_clients`、`blocked_clients`、`maxclients`；
- **Memory**：`used_memory`、`used_memory_rss`、`mem_fragmentation_ratio`、`used_memory_peak`、maxmemory 使用率；
- **Stats**：`instantaneous_ops_per_sec`、`keyspace_hits/misses`（命中率）、`evicted_keys`、`expired_keys`、`rejected_connections`、`latest_fork_usec`、`total_net_input/output_bytes`；
- **Persistence**：`rdb_last_bgsave_status`、`aof_last_write_status`、`rdb_last_cow_size`；
- **Replication**：`role`、`connected_slaves`、`master_link_status`、各从库 offset 与主库 `master_repl_offset` 的差值；
- **CPU**：`used_cpu_sys`、`used_cpu_user`（以及主线程的使用率）；
- **Commandstats**：每个命令的调用次数与平均耗时；
- **Keyspace**：每个库的 key 数量、带过期时间的 key 数量。''',hot=True),
B(2,"生产环境 Redis 有哪些重要的配置和系统参数？",r'''
**redis.conf**：
- `bind` 内网地址、`protected-mode yes`、密码或 ACL；
- `maxmemory`（预留 fork COW 与缓冲区空间）+ `maxmemory-policy`；
- `appendonly`、`appendfsync everysec`、`aof-use-rdb-preamble yes`、`save` 规则；
- `lazyfree-lazy-*` 开启异步释放；
- `timeout`、`tcp-keepalive`、`maxclients`；
- `slowlog-log-slower-than`、`slowlog-max-len`、`latency-monitor-threshold`；
- `repl-backlog-size`、`client-output-buffer-limit replica/pubsub`；
- `io-threads`（多核、高流量时）。

**操作系统**：
- `vm.overcommit_memory = 1`；
- 关闭透明大页：`echo never > /sys/kernel/mm/transparent_hugepage/enabled`；
- `net.core.somaxconn` ≥ `tcp-backlog`（默认 511）；
- `ulimit -n` 足够大（≥ maxclients + 32）；
- 尽量避免 swap（`vm.swappiness` 设置较低）。'''),
B(2,"Redis 有哪些常见的安全问题？如何加固？",r'''
**典型攻击**：未设置密码且暴露在公网的 Redis，攻击者连接后执行 `CONFIG SET dir /root/.ssh`、`CONFIG SET dbfilename authorized_keys`，写入包含公钥的 key 后 `SAVE`，从而获得 SSH 登录权限；类似地写入 crontab 执行挖矿程序。

**加固**：
1. 网络隔离：只绑定内网 IP，安全组 / 防火墙限制来源，不暴露公网；
2. `protected-mode yes`；
3. 认证：强密码，6.0+ 使用 **ACL** 给不同应用分配不同用户，限制 key 前缀（`~app:*`）和命令（`+@read -@dangerous`）；
4. 禁用危险命令：FLUSHALL、FLUSHDB、KEYS、CONFIG、DEBUG、MODULE（ACL 或 `rename-command`）；7.0 起 `enable-protected-configs`、`enable-debug-command`、`enable-module-command` 默认禁止在运行时修改敏感配置和执行 DEBUG/MODULE；
5. 以非 root 用户运行，限制目录权限；
6. 开启 TLS；
7. 关注安全公告，及时升级（例如 Lua 相关的远程代码执行漏洞修复）；
8. `ACL LOG` 审计认证失败与权限拒绝事件。''',hot=True),
B(3,"客户端输出缓冲区是什么？为什么会导致主从同步失败或内存暴涨？",r'''
Redis 为每个客户端维护一个**输出缓冲区**，命令结果先写入缓冲区，再发送到网络。如果客户端读取速度跟不上，缓冲区就会不断增长。

`client-output-buffer-limit <class> <硬限制> <软限制> <软限制持续秒数>`，分为三类：
- `normal 0 0 0`：普通客户端默认不限制（一次 `HGETALL` 大 key 或 `MONITOR` 可能让缓冲区膨胀到数 GB）；
- `replica 256mb 64mb 60`：全量同步期间，主库要把 RDB 生成期间的写命令缓存到从库的缓冲区；写入量大时超过限制，主库会断开从库，从库重连后再次全量同步，形成**死循环**；
- `pubsub 32mb 8mb 60`：慢订阅者会被断开。

处理：根据写入量调大 replica 限制；监控 `CLIENT LIST` 中的 `omem`、`INFO` 中的 `mem_clients_normal`；禁止对大 key 进行全量读取；给 normal 类也设置合理上限。'''),
B(3,"如何安全地对线上 Redis 进行大规模数据迁移或版本升级？",r'''
**版本升级**（主从 / Sentinel）：
1. 先升级从库，验证复制正常、业务读取正常；
2. 手动故障转移（`SENTINEL FAILOVER mymaster` 或 Cluster 中在从库执行 `CLUSTER FAILOVER`）把已升级的从库切为主库；
3. 升级旧主（现为从库）；
4. 注意：新版本生成的 RDB 通常无法被旧版本加载，升级是单向的，回滚需要提前准备方案。

**数据迁移**（如自建迁移到云 / 迁移到 Cluster）：
1. 工具：RedisShake、Redis-port 等基于 PSYNC 模拟从库，先全量再增量同步；或者 `MIGRATE`、`DUMP/RESTORE`；
2. 双写或增量同步追平后，比对数据（抽样或使用 redis-full-check 等工具）；
3. 灰度切换读流量，再切写流量，保留回滚通道；
4. 迁移到 Cluster 前检查多 key 命令、Lua、事务是否满足同槽约束，不满足时先改造业务。''',r'''
迁移大 key 时，`MIGRATE`/`RESTORE` 都是同步的，可能阻塞源和目标实例，应在迁移前先拆分大 key 或在低峰期单独处理。'''),
])
