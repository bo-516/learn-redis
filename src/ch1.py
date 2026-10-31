from h import *
CH = dict(id="basics", code="BASE", stage=1, name="入门：认识 Redis 与 String",
desc="Redis 是什么、怎么安装连接、键空间通用命令，以及最常用的 String 类型。",
lesson=r'''
## 1. Redis 是什么

Redis（REmote DIctionary Server）是一个**内存优先**的键值数据库：所有数据都放在内存里，按 key 直接定位，所以单次读写通常在**亚毫秒**级。它不是"只能存字符串的缓存"，value 可以是 String、Hash、List、Set、Sorted Set、Stream、Bitmap、HyperLogLog、Geo 等多种结构，Redis 8 起还把 JSON、Search（查询引擎）、Time Series、Bloom 等概率结构合并进了开源发行版。

**典型用途**：缓存、Session、计数器、排行榜、分布式锁、限流、消息队列（Stream）、实时统计（UV、签到）、附近的人。

**不适合**：数据量远大于内存的冷数据存储、需要多表 JOIN 与复杂查询的业务主库、要求强一致多行事务回滚的场景——这些交给 MySQL / PostgreSQL，Redis 做加速层。

### 为什么快
- 数据在内存，避免磁盘随机 I/O；
- 针对场景精心设计的数据结构（listpack、skiplist、quicklist…）；
- **命令执行是单线程**的：没有锁竞争和上下文切换，配合 epoll 等 I/O 多路复用处理大量连接；
- 6.0 起可开启 I/O 线程（`io-threads`）把网络读写并行化，但**命令本身仍串行执行**，所以每条命令依然是原子的。

> 版本提示：截至 2026 年 10 月，Redis Open Source 最新稳定线是 8.10.x。7.4 起许可证改为 RSALv2/SSPLv1，8.0 起新增 AGPLv3 可选；社区另有 BSD 协议的分支 Valkey。学习本手册的命令与原理，在这几个版本之间基本通用。

## 2. 安装与连接

最快的方式是 Docker：

```
docker run -d --name redis -p 6379:6379 redis:latest
docker exec -it redis redis-cli
```

也可以用包管理器（`brew install redis`、`apt install redis`）。默认端口 **6379**。连上后：

```
127.0.0.1:6379> PING
PONG
127.0.0.1:6379> SET hello world
OK
127.0.0.1:6379> GET hello
"world"
```

常用 redis-cli 参数：`-h` 主机、`-p` 端口、`-a` 密码（会出现在 shell 历史里，生产推荐用 `--askpass` 或 `AUTH`）、`-n` 选库、`-c` 集群模式自动跟随重定向、`--scan` 扫描 key、`--bigkeys` 找大 key、`--latency` 测延迟。

## 3. 键空间与通用命令

Redis 默认有 16 个逻辑库（`SELECT 0..15`），但它们只是命名空间，**Cluster 模式只支持 0 号库**，所以实践中更推荐用 key 前缀区分业务。

| 命令 | 作用 | 注意 |
|---|---|---|
| `EXISTS k [k...]` | 返回存在的 key 个数 | 多个 key 时重复会重复计数 |
| `DEL k [k...]` | 同步删除 | 删大 key 会阻塞 |
| `UNLINK k [k...]` | 先从键空间摘除，后台线程释放内存 | 删大 key 用它 |
| `TYPE k` | 返回类型 | string/list/set/zset/hash/stream |
| `EXPIRE k sec` / `TTL k` | 设置 / 查看剩余秒数 | TTL：-1 无过期，-2 不存在 |
| `PERSIST k` | 移除过期时间 | |
| `RENAME k nk` | 改名 | nk 存在会被覆盖；`RENAMENX` 不覆盖 |
| `KEYS pattern` | 模式匹配所有 key | **O(N)，阻塞，线上禁用** |
| `SCAN cursor MATCH p COUNT n` | 渐进式遍历 | 可能返回重复，需要客户端去重 |
| `OBJECT ENCODING k` | 查看底层编码 | 学习数据结构时很有用 |

`SCAN` 的游标从 0 开始，返回 0 表示遍历结束；`COUNT` 只是"每次大概做多少工作"的提示，不保证返回条数。完整遍历期间一直存在的 key 一定会被返回至少一次。

## 4. String：最基础也最常用

String 是二进制安全的字节数组，最大 **512 MB**。可以存文本、数字、序列化后的 JSON、图片字节等。

```
SET user:1:name "Alice"
SET token:abc 1 EX 3600 NX   # 不存在才设置，同时 1 小时过期
GET user:1:name
MSET a 1 b 2                 # 批量写，原子
MGET a b
INCR page:views              # 原子 +1，返回新值
INCRBY stock:1001 -1
INCRBYFLOAT price 0.5
APPEND log "line\n"
STRLEN user:1:name
GETRANGE user:1:name 0 2
SET k v GET                  # 设置新值并返回旧值（替代已废弃的 GETSET）
GETEX k EX 60                # 读取并刷新过期时间
GETDEL k                     # 读取并删除
```

**SET 的选项**（一个命令搞定"条件写 + 过期"，这是分布式锁的基础）：

- `EX seconds` / `PX milliseconds` / `EXAT` / `PXAT`：设置过期；
- `NX`：仅当 key 不存在时写入；`XX`：仅当存在时写入；
- `KEEPTTL`：保留原来的过期时间（普通 SET 会**清除**原有 TTL）；
- `GET`：返回旧值。

### 底层编码
`OBJECT ENCODING` 可以看到三种：`int`（可表示为 64 位整数的值）、`embstr`（≤ 44 字节的短字符串，和对象头一次分配）、`raw`（更长的字符串）。这解释了为什么"小而多"的 key 很省 CPU，但每个 key 仍有几十字节的元数据开销。

### 计数器为什么用 INCR
`GET` + 应用里加一 + `SET` 在并发下会丢更新；`INCR` 在服务端单线程内完成"读-改-写"，天然原子。对不是整数的值执行 INCR 会报错 `ERR value is not an integer or out of range`。

## 5. 动手练习
1. 用 `SET ... EX ... NX` 写一个"60 秒内只允许领取一次"的 key，重复执行观察返回值。
2. 写 1 万个 key（`redis-cli` 里用 `DEBUG POPULATE 10000` 或脚本），分别用 `KEYS *` 和 `SCAN` 遍历，体会区别。
3. 对同一个 key 先 `EXPIRE` 再 `SET`，用 `TTL` 观察过期时间被清除；再用 `SET ... KEEPTTL` 对比。
''',
quiz=[
S(1,"Redis 默认监听的端口是？",["3306","6379","27017","11211"],1,r'''
Redis 默认端口是 **6379**。
- 3306 是 MySQL 默认端口；
- 27017 是 MongoDB；
- 11211 是 Memcached。
另外要记住：Sentinel 默认 26379，Cluster 总线端口是"数据端口 + 10000"（如 16379）。''',hot=True),
S(1,"关于 Redis 为什么快，下列说法**最准确**的是？",["因为 Redis 是多线程并行执行命令的","因为数据主要在内存中、数据结构高效、命令单线程执行避免锁竞争，并用 I/O 多路复用处理大量连接","因为 Redis 把所有数据都压缩存储","因为 Redis 不支持持久化"],1,r'''
B 正确，这是标准答案的四要素：**内存**、**高效数据结构**、**单线程执行命令（无锁、无上下文切换）**、**I/O 多路复用**。
- A 错：即使开启 `io-threads`，多线程也只用于网络读写，**命令执行始终串行**。
- C 错：只有部分小对象用紧凑编码（listpack、intset），并不是全量压缩；
- D 错：Redis 支持 RDB / AOF 持久化，且持久化由子进程或后台 fsync 完成，不是"快的原因"。''',hot=True),
T(1,"线上环境可以放心用 `KEYS user:*` 查找 key，因为它支持模式匹配，速度很快。",False,r'''
**错误。** `KEYS` 会遍历整个键空间，时间复杂度 O(N)。Redis 命令单线程执行，几百万 key 的实例上一次 `KEYS` 可能阻塞数百毫秒到数秒，期间所有其他请求都在排队，极易引发超时雪崩。
线上请用 `SCAN 0 MATCH user:* COUNT 100` 渐进式遍历，或在 redis.conf / ACL 中禁用 KEYS（如 ACL 规则 `-keys`）。''',hot=True),
S(1,"执行 `TTL k` 返回 -2，表示什么？",["key 存在但没有设置过期时间","key 不存在（或已过期被删除）","key 将在 2 秒后过期","命令执行出错"],1,r'''
- **-2：key 不存在**（Redis 2.8 起的语义）；
- **-1：key 存在但没有过期时间**（A 描述的是 -1）；
- 正数才是剩余秒数，所以 C 错；
- TTL 对不存在的 key 不会报错，D 错。''',hot=True),
S(1,"想设置 key `lock:1` 值为 `abc`，仅当 key 不存在时写入，并在 30 秒后过期，下列哪条命令**一步原子完成**？",["SETNX lock:1 abc 然后 EXPIRE lock:1 30","SET lock:1 abc NX EX 30","SET lock:1 abc XX EX 30","MSET lock:1 abc EX 30"],1,r'''
B 正确：`SET key value NX EX 30` 是单条命令，"不存在才写 + 设置过期"一次完成，原子。
- A 是两条命令，SETNX 成功后如果客户端崩溃，EXPIRE 没执行，就留下一把**永不过期的锁**——这是经典事故；
- C 的 `XX` 是"存在才写"，语义相反；
- D：MSET 不支持 EX 选项，会报语法错误。''',hot=True),
F(1,"填写一条命令：把 key `page:views` 的值原子加 1。",["INCR page:views","INCRBY page:views 1"],r'''
`INCR page:views`（等价于 `INCRBY page:views 1`）。key 不存在时会先当作 0 再加 1，返回 1。
它在服务端一次完成"读-改-写"，并发安全；而 GET + 应用层 +1 + SET 会出现两个客户端读到同一个旧值，最终只加了 1 次的**丢失更新**问题。'''),
T(1,"对一个已经有 TTL 的 key 执行普通的 `SET key newvalue`（不带任何选项），原来的过期时间会被保留。",False,r'''
**错误。** 普通 SET 会覆盖值并**清除**原有的过期时间，key 变成永久的（TTL 返回 -1）。
这是很多"缓存永不过期、内存越涨越多"事故的根源。想保留 TTL，使用 `SET key newvalue KEEPTTL`（6.0+），或者每次写入都显式带上 EX。'''),
S(2,"对值为 `\"hello\"` 的 key 执行 `INCR`，会发生什么？",["值变成 hello1","值变成 1","返回错误 ERR value is not an integer or out of range，值不变","key 被删除"],2,r'''
INCR 要求值能解析成 64 位有符号整数，否则返回错误，**原值不变**。
- A/B：Redis 不会做字符串拼接或隐式转为 0（只有 key 不存在时才按 0 处理）；
- D：出错的命令不会修改数据。'''),
S(2,"`SCAN` 命令的特性中，**错误**的是？",["游标返回 0 表示一轮遍历结束","同一个 key 可能在多次迭代中被重复返回","COUNT 参数保证每次恰好返回 COUNT 个元素","整个遍历期间一直存在的 key 至少会被返回一次"],2,r'''
C 错误（所以选 C）：`COUNT` 只是每次迭代"工作量"的**提示**，实际返回数量可多可少，甚至可能返回空数组但游标不为 0——此时要继续迭代，不能当成结束。
A、B、D 都是官方文档保证的语义：0 游标结束；可能重复（rehash 时）所以应用层要能去重；全程存在的元素一定被返回至少一次。'''),
M(2,"以下哪些 SET 选项是合法的？（多选）",["EX / PX 设置过期","NX / XX 条件写入","KEEPTTL 保留原过期时间","GET 返回旧值","INCR 写入时自增"],[0,1,2,3],r'''
A–D 都是 `SET` 的合法选项：`EX|PX|EXAT|PXAT`、`NX|XX`、`KEEPTTL`（6.0）、`GET`（6.2，替代 GETSET）。
E 错：`INCR` 是 **ZADD** 的选项（`ZADD key INCR score member`），SET 没有。'''),
S(2,"`OBJECT ENCODING k` 返回 `embstr`，说明？",["k 是 Hash 类型","k 的值是 ≤ 44 字节的短字符串，对象头与数据一次连续分配","k 的值是整数","k 是被压缩过的长字符串"],1,r'''
String 有三种编码：
- `int`：值可以表示为 64 位整数（C 描述的是它）；
- `embstr`：≤ 44 字节的短字符串，redisObject 和 SDS 在一块连续内存里，一次分配、缓存友好；
- `raw`：更长的字符串，分两次分配。
A 错：Hash 的编码是 listpack / hashtable；D 错：Redis 不会自动压缩 String。'''),
S(2,"要删除一个包含 500 万个元素的 Hash，且不希望阻塞主线程，应该使用？",["DEL bighash","UNLINK bighash","EXPIRE bighash 0","FLUSHDB"],1,r'''
`UNLINK` 只在主线程里把 key 从键空间摘掉（O(1)），真正释放内存交给后台 lazyfree 线程，不会阻塞。
- A：`DEL` 同步释放 500 万个元素，可能阻塞几百毫秒以上（除非配置了 `lazyfree-lazy-user-del yes`，此时 DEL 行为同 UNLINK）；
- C：过期删除时是否异步取决于 `lazyfree-lazy-expire`，且语义上不清晰；
- D：会清掉整个库，显然不对。''',hot=True),
T(2,"Redis 默认有 16 个逻辑数据库，在 Redis Cluster 中同样可以用 `SELECT 1` 切换到 1 号库。",False,r'''
**错误。** Redis Cluster（官方开源版）只支持 **0 号库**，`SELECT` 非 0 会报错。因此跨环境通用的做法是用 **key 前缀**（如 `order:`、`user:`）隔离业务，而不是依赖多 DB。'''),
F(2,"写出一条命令：读取 key `session:42` 的值并同时把它的过期时间刷新为 1800 秒。",["GETEX session:42 EX 1800"],r'''
`GETEX session:42 EX 1800`（6.2+）一条命令完成"读 + 续期"，适合滑动过期的 Session。
用 `GET` + `EXPIRE` 两条命令也能实现，但多一次往返，并且不是原子的（中间 key 可能恰好过期）。`GETEX key PERSIST` 则可以去掉过期时间。'''),
S(3,"String 类型单个 value 的最大长度是？",["64 KB","1 MB","512 MB","没有上限"],2,r'''
单个 String 最大 **512 MB**（key 的上限同样是 512 MB）。但"能存"不代表"该存"：value 超过 10 KB 就值得警惕，几 MB 的 value 读写会占满网络、阻塞主线程，是典型的**大 key**问题（见第 6 章）。'''),
],
bank=[
B(1,"Redis 是什么？和 MySQL 的定位有什么区别？",r'''
Redis 是**内存优先的键值数据库**，支持丰富的数据结构，读写延迟在亚毫秒级，单实例可达十万级 QPS。
MySQL 是**磁盘为主的关系型数据库**，支持 SQL、JOIN、二级索引和完整的 ACID 事务。

| 维度 | Redis | MySQL |
|---|---|---|
| 存储 | 内存（可持久化到磁盘） | 磁盘（Buffer Pool 缓存热点） |
| 数据模型 | key → 多种结构 | 表、行、列 |
| 查询 | 按 key 访问为主 | SQL、索引、JOIN |
| 事务 | 命令原子、MULTI 无回滚 | 完整 ACID |
| 典型角色 | 缓存、计数、锁、排行榜 | 业务主数据 |

实际项目里两者是**配合**关系：MySQL 是真相源，Redis 做加速层和特定场景的数据结构服务。''',hot=True),
B(1,"Redis 为什么这么快？单线程为什么还能这么快？",r'''
1. **内存存储**：没有磁盘寻道，访问是纳秒到微秒级；
2. **高效数据结构**：SDS、listpack、quicklist、skiplist、intset 等针对场景优化；
3. **单线程执行命令**：没有锁竞争、没有线程切换，代码路径简单；CPU 很少是瓶颈，瓶颈通常是内存和网络；
4. **I/O 多路复用**：用 epoll/kqueue 一个线程管理上万连接；
5. 6.0 起可开启 **I/O 线程**，把网络读写和协议解析并行化，提升高并发下的吞吐。''',r'''
"单线程"要说准确：指的是**命令执行**在主线程串行完成。Redis 本身还有后台线程（lazyfree 释放内存、AOF fsync、关闭文件）、fork 出的子进程（RDB / AOF 重写）以及可选的 I/O 线程。

单线程带来的代价：**任何慢命令都会阻塞所有客户端**。所以要避免 `KEYS`、大 key 的 `HGETALL`/`DEL`、长 Lua 脚本、O(N) 的大范围查询。这是后面所有"性能排障"话题的出发点。''',hot=True),
B(1,"KEYS 和 SCAN 有什么区别？SCAN 有什么需要注意的地方？",r'''
- `KEYS pattern`：一次性遍历整个键空间返回所有匹配 key，O(N)，**会阻塞主线程**，线上禁用。
- `SCAN cursor [MATCH p] [COUNT n] [TYPE t]`：基于游标的渐进式遍历，每次只做一小部分工作，不会长时间阻塞。

SCAN 注意点：
1. 游标返回 `0` 才表示结束；
2. 可能返回**重复** key（遍历过程中发生 rehash），应用要去重；
3. `COUNT` 只是提示，返回条数不固定，甚至可能返回空但游标非 0；
4. 遍历期间新增或删除的 key 可能被返回也可能不被返回；
5. 集合类型对应有 `HSCAN`、`SSCAN`、`ZSCAN`。''',r'''
SCAN 能做到"不重不漏（对一直存在的 key）"，靠的是**反向二进制位递增**的游标：游标按高位加 1 的顺序遍历哈希桶，扩容（桶数翻倍）或缩容时，已经遍历过的桶对应到新表里依然是"已遍历"的区域，所以不会漏；缩容时可能把已遍历的桶合并进来，于是会出现重复。''',hot=True),
B(1,"DEL 和 UNLINK 有什么区别？什么时候用 UNLINK？",r'''
- `DEL`：在主线程里同步释放 key 及其所有元素的内存。对小 key 没问题，但删除百万元素的集合可能阻塞上百毫秒。
- `UNLINK`（4.0+）：主线程只把 key 从字典中摘掉（O(1)），内存释放交给后台 lazyfree 线程。

建议：删除可能很大的集合类型时一律 `UNLINK`；也可以配置 `lazyfree-lazy-user-del yes` 让 DEL 自动走异步。相关的还有 `FLUSHALL ASYNC`、`lazyfree-lazy-eviction`、`lazyfree-lazy-expire`。''',hot=True),
B(1,"SET 命令有哪些常用选项？SETNX 还推荐使用吗？",r'''
`SET key value [NX|XX] [GET] [EX s|PX ms|EXAT ts|PXAT ts|KEEPTTL]`
- `NX` 不存在才写、`XX` 存在才写；
- `EX/PX` 相对过期、`EXAT/PXAT` 绝对时间戳过期；
- `KEEPTTL` 保留原 TTL；
- `GET` 返回旧值。

`SETNX`、`SETEX`、`PSETEX`、`GETSET` 都可以用 SET 的选项替代。特别是 SETNX 不能同时设置过期时间，"SETNX + EXPIRE"两步操作不原子，做锁时有死锁风险，因此推荐 `SET key token NX PX 30000`。'''),
B(2,"为什么普通 SET 会清除 TTL？这会导致什么线上问题？",r'''
Redis 的语义是：**覆盖 key 的写命令**（SET、GETSET、以及对 key 整体替换的操作）会把 key 当作新对象写入，原有过期时间被清除；而修改元素的命令（`INCR`、`LPUSH`、`HSET`、`APPEND` 等）**不会**改变 TTL。

典型事故：缓存刷新逻辑写成 `SET cache:x newval`，忘了带 EX，结果这个 key 从此永不过期，内存缓慢上涨，最终触发淘汰或 OOM。
预防：封装统一的缓存写入方法强制带 TTL；需要保留原 TTL 时用 `KEEPTTL`；定期用 `SCAN` + `TTL` 抽样巡检永久 key。'''),
B(2,"String 底层是怎么实现的？int、embstr、raw 三种编码有什么区别？",r'''
Redis 的字符串是自己实现的 **SDS（Simple Dynamic String）**：记录了长度 len 和已分配容量 alloc，因此 `STRLEN` 是 O(1)、二进制安全（可以包含 `\0`）、追加时有预分配，减少 realloc 次数。

三种编码：
- `int`：值是 64 位整数时直接存在对象指针里，不另外分配；0~9999 的小整数还会使用共享对象；
- `embstr`：长度 ≤ 44 字节，redisObject 和 SDS 一次分配在同一块 64 字节内存中，只读；
- `raw`：更长或被修改过（如 APPEND）的字符串，对象和 SDS 分两次分配。''',r'''
为什么是 44？redisObject 占 16 字节，最小的 SDS 头（sdshdr8）占 3 字节，结尾 `\0` 占 1 字节，16 + 3 + 1 + 44 = 64，正好落进 jemalloc 的 64 字节分配档位。'''),
B(2,"计数器场景为什么要用 INCR？如何实现每天自动清零的计数？",r'''
INCR 在服务端单线程中完成读-改-写，原子且只需一次网络往返；应用层 GET+SET 会产生**丢失更新**。

每日清零：把日期放进 key，如 `pv:20261031`，第一次写入时设置过期：
```
INCR pv:20261031
EXPIRE pv:20261031 172800 NX   # 7.0+ 的 NX：只在没有 TTL 时设置
```
或者用 Lua / MULTI 把 INCR 与 EXPIRE 放在一起，避免"INCR 成功但 EXPIRE 没执行"留下永久 key。'''),
B(2,"Redis 的 key 有哪些命名规范？",r'''
1. 用冒号分层：`业务:实体:ID[:字段]`，如 `order:10086:status`，便于阅读、SCAN 匹配和工具分组展示；
2. **短而可读**：key 本身占内存，亿级 key 时 `user:info:` 和 `u:i:` 差出几个 GB，需要在可读性和成本之间平衡；
3. 不要把无界变化的参数（完整 URL、整段 SQL）直接拼进 key，必要时取哈希；
4. 不含空格、换行等特殊字符；
5. Cluster 下需要多 key 同时操作时，用 **Hash Tag** `{user:100}:cart` 让它们落到同一槽；
6. 缓存类 key 一定设置 TTL。''',hot=True),
B(2,"redis-cli 有哪些实用参数？",r'''
- `-h/-p/-a/--user/--askpass`：连接与认证（`-a` 会把密码留在 shell 历史，慎用）；
- `-n db`：选库；`-c`：集群模式，自动跟随 MOVED/ASK；
- `--scan --pattern 'user:*'`：安全地列出 key；
- `--bigkeys` / `--memkeys`：按元素数 / 内存抽样找大 key；
- `--hotkeys`：找热 key（需要 LFU 淘汰策略）；
- `--latency`、`--latency-history`、`--intrinsic-latency 10`：测延迟；
- `--stat`：每秒刷新的实例概况；
- `-r 次数 -i 间隔`：重复执行命令；
- `--pipe`：大批量导入数据；`--rdb file`：远程拉取 RDB 备份。'''),
B(3,"Redis 的许可证变化（7.4 / 8.0）和 Valkey 是怎么回事？选型时要注意什么？",r'''
- Redis 7.2 及之前：BSD 三条款；
- 2024 年的 **7.4**：改为 RSALv2 / SSPLv1 双许可，限制云厂商直接提供托管服务；
- 同年 Linux 基金会发起 **Valkey**（基于 7.2.4 分叉，BSD 协议），主流云厂商支持；
- 2025 年的 **Redis 8.0**：增加 **AGPLv3** 作为可选的开源许可，并把 JSON、Search、Time Series、概率数据结构合并进开源发行版。

选型：公司内部自用一般不受影响；如果要把 Redis 作为服务对外提供，需要法务评估许可证；Valkey 与 Redis 7.2 协议兼容，但 8.x 的新功能（如 Query Engine、Vector Set）各自演进，不再完全一致。'''),
B(3,"什么是 RESP 协议？RESP3 带来了什么？",r'''
RESP（REdis Serialization Protocol）是客户端与服务器的文本协议，简单、易解析：`+` 简单字符串、`-` 错误、`:` 整数、`$` 批量字符串、`*` 数组。例如 `SET k v` 实际发送：
```
*3\r\n$3\r\nSET\r\n$1\r\nk\r\n$1\r\nv\r\n
```
**RESP3**（6.0+，用 `HELLO 3` 切换）增加了 Map、Set、Double、Boolean、Null、Push 等类型：
- 客户端能直接拿到 Map 而不是扁平数组（如 HGETALL）；
- **Push 类型**让同一连接可以接收服务端推送，这是客户端缓存（Client-side caching / tracking）失效通知的基础。''',r'''
因为协议是纯文本且带长度前缀，所以可以用 `redis-cli --pipe` 把大量生成好的 RESP 命令一次性灌入，导入速度远快于逐条执行。'''),
])
