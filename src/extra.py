def c(cmd, cx, desc, ex): return dict(cmd=cmd, cx=cx, desc=desc, ex=ex)
CMDS = [
dict(id="key", name="通用 / 键空间", desc="对任意类型的 key 生效的命令。", items=[
c("EXISTS key [key ...]","O(N)","返回存在的 key 数量。","EXISTS user:1 user:2"),
c("DEL key [key ...]","O(N)","同步删除；删除大集合会阻塞，大 key 请用 UNLINK。","DEL user:1"),
c("UNLINK key [key ...]","O(1) 摘除","异步释放内存的删除。","UNLINK bighash"),
c("EXPIRE key seconds [NX|XX|GT|LT]","O(1)","设置过期时间；7.0 起支持条件选项。PEXPIRE 为毫秒。","EXPIRE session:1 1800 NX"),
c("TTL / PTTL key","O(1)","剩余秒数 / 毫秒数；-1 无过期，-2 不存在。","TTL session:1"),
c("PERSIST key","O(1)","移除过期时间。","PERSIST session:1"),
c("TYPE key","O(1)","返回值的类型。","TYPE rank"),
c("SCAN cursor [MATCH p] [COUNT n] [TYPE t]","每次 O(1)","渐进式遍历 key，代替 KEYS。","SCAN 0 MATCH user:* COUNT 100"),
c("RENAME / RENAMENX key newkey","O(1)","改名；RENAMENX 在新名字存在时不覆盖。","RENAMENX tmp:rank rank"),
c("OBJECT ENCODING|FREQ|IDLETIME key","O(1)","查看编码、LFU 频率、空闲时间。","OBJECT ENCODING user:1"),
c("MEMORY USAGE key [SAMPLES n]","O(N)","估算 key 占用的字节数。","MEMORY USAGE user:1"),
c("DUMP / RESTORE","O(N)","序列化与恢复单个 key，用于迁移。","DUMP user:1"),
]),
dict(id="string", name="String", desc="字符串、计数器、位图。", items=[
c("SET key value [NX|XX] [GET] [EX|PX|EXAT|PXAT|KEEPTTL]","O(1)","最核心的写命令，可原子地附带条件与过期。","SET lock:1 token NX PX 30000"),
c("GET / GETEX / GETDEL","O(1)","读取；GETEX 读取同时修改过期；GETDEL 读取后删除。","GETEX session:1 EX 1800"),
c("MSET / MGET","O(N)","批量写读；Cluster 下需同槽。","MSET a 1 b 2\nMGET a b"),
c("INCR / INCRBY / DECR / INCRBYFLOAT","O(1)","原子计数。","INCRBY stock:1 -1"),
c("APPEND / STRLEN / GETRANGE / SETRANGE","O(1)~O(N)","字符串片段操作。","APPEND log \"x\""),
c("SETBIT / GETBIT / BITCOUNT / BITOP / BITPOS","O(1)~O(N)","位图操作。","SETBIT sign:u1:202610 30 1\nBITCOUNT sign:u1:202610"),
c("BITFIELD","O(1) 每个子命令","把字符串当作多个任意位宽整数读写。","BITFIELD sign:u1:202610 GET u31 0"),
]),
dict(id="hash", name="Hash", desc="字段级读写的对象。", items=[
c("HSET key f v [f v ...]","O(1) 每字段","写入字段，返回新增字段数。","HSET user:1 name Alice age 30"),
c("HGET / HMGET","O(1)/O(N)","读取一个或多个字段。","HMGET user:1 name age"),
c("HGETALL / HKEYS / HVALS","O(N)","全量读取，大 Hash 慎用。","HGETALL user:1"),
c("HINCRBY / HINCRBYFLOAT","O(1)","字段原子加减。","HINCRBY cart:u1 sku:1 2"),
c("HDEL / HEXISTS / HLEN","O(1)","删除、判断、计数。","HDEL cart:u1 sku:1"),
c("HSCAN key cursor [MATCH p] [COUNT n]","每次 O(1)","渐进遍历字段。","HSCAN user:1 0 COUNT 100"),
c("HEXPIRE key seconds FIELDS n f...","O(N)","7.4+ 字段级过期，还有 HTTL、HPERSIST；8.0 新增 HSETEX/HGETEX/HGETDEL。","HEXPIRE session:u1 3600 FIELDS 1 token"),
]),
dict(id="list", name="List", desc="队列、栈、最新列表。", items=[
c("LPUSH / RPUSH key v [v ...]","O(1) 每元素","头部 / 尾部插入。","LPUSH feed:u1 post:9"),
c("LPOP / RPOP key [count]","O(N)","弹出元素。","RPOP q 10"),
c("BLPOP / BRPOP key [key ...] timeout","O(1)","阻塞弹出，timeout 为 0 表示一直等待。","BRPOP q 5"),
c("LMOVE / BLMOVE src dst LEFT|RIGHT LEFT|RIGHT","O(1)","原子移动，用于可靠队列。","BLMOVE q q:processing RIGHT LEFT 0"),
c("LRANGE key start stop","O(S+N)","范围读取，-1 表示最后一个。","LRANGE feed:u1 0 19"),
c("LTRIM key start stop","O(N)","只保留指定范围。","LTRIM feed:u1 0 999"),
c("LLEN / LINDEX / LPOS / LREM","O(1)~O(N)","长度、下标、查找、删除。","LREM q:processing 1 job:1"),
]),
dict(id="set", name="Set", desc="去重与集合运算。", items=[
c("SADD / SREM key m [m ...]","O(1) 每元素","添加 / 删除成员。","SADD like:post:1 u1"),
c("SISMEMBER / SMISMEMBER","O(1)/O(N)","判断成员是否存在。","SISMEMBER like:post:1 u1"),
c("SCARD key","O(1)","成员数量。","SCARD like:post:1"),
c("SMEMBERS key","O(N)","全部成员，大集合用 SSCAN。","SMEMBERS tags:redis"),
c("SINTER / SUNION / SDIFF (STORE)","O(N*M) 等","交、并、差集。","SINTER follow:u1 follow:u2"),
c("SINTERCARD numkeys key... [LIMIT n]","O(N*M)","7.0+ 只返回交集数量。","SINTERCARD 2 follow:u1 follow:u2"),
c("SPOP / SRANDMEMBER key [count]","O(N)","随机弹出 / 随机读取。","SPOP lottery:1 3"),
]),
dict(id="zset", name="Sorted Set", desc="排行榜、延时队列、滑动窗口。", items=[
c("ZADD key [NX|XX] [GT|LT] [CH] [INCR] score m ...","O(log N)","添加或更新成员分数。","ZADD rank GT 100 alice"),
c("ZINCRBY key incr member","O(log N)","增加分数。","ZINCRBY rank 10 bob"),
c("ZSCORE / ZMSCORE","O(1)","查分数。","ZSCORE rank alice"),
c("ZRANK / ZREVRANK","O(log N)","查名次（从 0 开始）。","ZREVRANK rank alice"),
c("ZRANGE key start stop [BYSCORE|BYLEX] [REV] [LIMIT o c] [WITHSCORES]","O(log N + M)","6.2 起的统一范围查询。","ZRANGE rank 0 9 REV WITHSCORES"),
c("ZCOUNT / ZCARD","O(log N)/O(1)","区间计数 / 总数。","ZCOUNT rank 90 +inf"),
c("ZREM / ZREMRANGEBYSCORE / ZREMRANGEBYRANK","O(log N + M)","删除成员或区间。","ZREMRANGEBYSCORE rl:u1 0 1730390000000"),
c("ZPOPMIN / ZPOPMAX / BZPOPMIN","O(log N)","弹出最小 / 最大分数的成员。","ZPOPMIN delay:q"),
]),
dict(id="special", name="Stream / HLL / Geo", desc="消息流与特殊结构。", items=[
c("XADD key [MAXLEN ~ n] *|id field value ...","O(1)","追加消息。","XADD orders MAXLEN ~ 100000 * uid 1 amount 99"),
c("XGROUP CREATE key group id|$ [MKSTREAM]","O(1)","创建消费组。","XGROUP CREATE orders g1 $ MKSTREAM"),
c("XREADGROUP GROUP g c [COUNT n] [BLOCK ms] STREAMS key >","O(M)","消费组读取新消息。","XREADGROUP GROUP g1 c1 COUNT 10 BLOCK 5000 STREAMS orders >"),
c("XACK key group id ...","O(1)","确认消息。","XACK orders g1 1730390000000-0"),
c("XPENDING / XAUTOCLAIM","O(N)","查看 / 认领待确认消息。","XAUTOCLAIM orders g1 c2 60000 0-0 COUNT 10"),
c("XRANGE / XLEN / XINFO","O(N)","读取范围、长度、详情。","XINFO GROUPS orders"),
c("PFADD / PFCOUNT / PFMERGE","O(1)","HyperLogLog 基数估算。","PFADD uv:20261031 u1 u2"),
c("GEOADD / GEOSEARCH / GEODIST","O(log N)","地理位置。","GEOSEARCH shops FROMLONLAT 116.41 39.91 BYRADIUS 2 km ASC"),
c("BF.ADD / BF.EXISTS / BF.RESERVE","O(K)","Redis 8 内置布隆过滤器。","BF.RESERVE bf:user 0.001 1000000"),
]),
dict(id="tx", name="事务 / 脚本 / 发布订阅", desc="原子性与消息通知。", items=[
c("MULTI / EXEC / DISCARD","—","事务：命令入队后一次性执行，不回滚。","MULTI\nINCR a\nINCR b\nEXEC"),
c("WATCH / UNWATCH","O(1)","乐观锁，被监视的 key 改变则 EXEC 返回 nil。","WATCH balance:u1"),
c("EVAL script numkeys key... arg...","取决于脚本","执行 Lua 脚本，原子。","EVAL \"return redis.call('GET', KEYS[1])\" 1 k"),
c("SCRIPT LOAD / EVALSHA","—","缓存脚本并按 SHA1 调用。","SCRIPT LOAD \"return 1\""),
c("FUNCTION LOAD / FCALL","—","7.0+ 持久化函数库。","FCALL myfunc 1 k arg"),
c("PUBLISH / SUBSCRIBE / PSUBSCRIBE","O(N+M)","发布订阅，消息不持久化。","PUBLISH news hello"),
c("SPUBLISH / SSUBSCRIBE","O(N)","7.0+ 分片 Pub/Sub。","SPUBLISH {room1}:chat hi"),
]),
dict(id="admin", name="运维 / 诊断", desc="监控、排障与集群管理。", items=[
c("INFO [section]","O(1)","实例信息：memory、stats、replication、persistence、commandstats…","INFO memory"),
c("SLOWLOG GET n / LEN / RESET","O(N)","慢日志。","SLOWLOG GET 10"),
c("LATENCY DOCTOR / LATEST","O(1)","延迟诊断报告。","LATENCY DOCTOR"),
c("CLIENT LIST / KILL / SETNAME","O(N)","客户端管理。","CLIENT LIST"),
c("CONFIG GET / SET / REWRITE","O(N)","运行时读写配置并写回文件。","CONFIG SET maxmemory-policy allkeys-lfu"),
c("BGSAVE / BGREWRITEAOF / LASTSAVE","O(1) 触发","后台持久化。","BGSAVE"),
c("REPLICAOF host port | NO ONE","O(1)","设置复制 / 提升为主。","REPLICAOF NO ONE"),
c("CLUSTER INFO / NODES / SHARDS / KEYSLOT","O(N)","集群信息与槽位。","CLUSTER KEYSLOT {user:1}:cart"),
c("ACL SETUSER / LIST / WHOAMI / LOG","O(N)","访问控制。","ACL SETUSER app on >pwd ~app:* +@read +@write -@dangerous"),
c("MEMORY STATS / DOCTOR / PURGE","O(1)","内存诊断与释放。","MEMORY DOCTOR"),
]),
]
HOME = r'''
## 30 天学习计划

| 时间 | 任务 | 对应章节 |
|---|---|---|
| 第 1–3 天 | Docker 安装 Redis，熟练使用 redis-cli；掌握 String 与键空间命令 | 第 1 章 |
| 第 4–7 天 | 五大数据结构 + Bitmap / HLL / Geo，用 OBJECT ENCODING 观察编码变化 | 第 2 章 |
| 第 8–11 天 | 过期机制、RDB / AOF 实验（kill -9 后看丢了多少数据）、事务、Pipeline、Lua | 第 3 章 |
| 第 12–17 天 | 写一个带缓存的小服务：Cache-Aside + 防穿透/击穿/雪崩；分布式锁；限流；Stream 消费组 | 第 4 章 |
| 第 18–23 天 | Docker Compose 搭 1 主 2 从 + 3 Sentinel，kill 主库观察切换；搭 3 主 3 从 Cluster，体验 MOVED、Hash Tag、reshard | 第 5 章 |
| 第 24–28 天 | 设置 maxmemory 观察淘汰；制造大 key / 热 key 并用工具发现；用 INFO、SLOWLOG、LATENCY 排查 | 第 6 章 |
| 第 29–30 天 | 刷完全部面试题，把错题重做一遍；写一页属于自己的「生产 Checklist」 | 全部 |

**学完的标志**：能独立设计一套带过期、防击穿、可降级的缓存方案；能讲清 RDB/AOF、复制、Sentinel、Cluster 的原理与取舍；线上变慢时能按清单用 INFO / SLOWLOG / 大 key 工具定位问题。

## 常见坑（建议贴在显示器旁）

1. 线上执行 `KEYS *`、`FLUSHALL`、对大 key `HGETALL` / `DEL`；
2. 缓存不设 TTL，或者全部 TTL 相同导致集中过期；
3. 普通 `SET` 覆盖时清除了 TTL；
4. 分布式锁没有过期时间、释放时不校验持有者、业务不幂等；
5. 先删缓存再更新 DB，导致长期脏数据；
6. Cluster 下多 key 操作 / Lua 跨槽；
7. 没有配置 maxmemory 和淘汰策略，或者内存不给 fork 留空间；
8. 没关 THP、没设 `overcommit_memory=1`；
9. Redis 暴露在公网且无密码；
10. 把 Redis 当成唯一的、绝对不丢数据的存储。

## 推荐资源

| 资源 | 链接 |
|---|---|
| 官方文档 | https://redis.io/docs/latest/ |
| 命令参考 | https://redis.io/docs/latest/commands/ |
| 数据类型 | https://redis.io/docs/latest/develop/data-types/ |
| 持久化 | https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/ |
| 复制 | https://redis.io/docs/latest/operate/oss_and_stack/management/replication/ |
| Sentinel | https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/ |
| Cluster 规范 | https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/ |
| 淘汰策略 | https://redis.io/docs/latest/develop/reference/eviction/ |
| 延迟排查 | https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency/ |
| 分布式锁 | https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/ |
| 源码 | https://github.com/redis/redis |
'''
