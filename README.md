# OPPO / 一加 / realme OTA 工具集

一套完整的 OTA 查询与提取工具链，支持国行官方包查询、动态链接解析、分区镜像直读提取。

## 目录

- [快速开始](#快速开始)
- [工具组成](#工具组成)
- [机型库](#机型库)
- [ota.py 一键工具](#otapy-一键工具)
- [各工具单独用法](#各工具单独用法)
- [常见任务](#常见任务)
- [故障排查](#故障排查)

---

## 快速开始

```sh
cd /workspace/oplus

# 查某机型最新版下载链接
./ota.py link PJZ110

# 也可以直接写中文名
./ota.py link "一加 13"

# 一步提取指定分区
./ota.py get PJZ110 dtbo,boot,init_boot
```

---

## 机型库

`models.py` 维护一份机型代号库，数据来自
[MobileModels](https://github.com/KHwang9883/MobileModels)，覆盖
OPPO / OnePlus / realme / vivo / Xiaomi，约 1800+ 条记录。

### 为什么需要它

不同工具对机型的称呼不一样：

| 你会说 | OTA 接口要的是 |
|---|---|
| 一加 13、OP 13 | `PJZ110` |
| OPPO Find X8 | `PKB110` |
| iQOO 12 | `V2307A` |

机型库负责把前者翻译成后者。

### 命令

```sh
./ota.py models sync              # 同步机型库（7 天内不重复下载）
./ota.py models sync --force      # 强制重新下载
./ota.py models search "一加 13"   # 搜索，返回代号 / 机型 / 品牌
./ota.py models resolve "一加 13"  # 解析成代号 + 分支
./ota.py models list              # 查看记录总数
```

### 搜索示例

```sh
$ ./ota.py models search "一加 13"
代号                机型                              品牌
--------------------------------------------------------------------
PJZ110            一加 13 国行版                       OnePlus
PKX110            一加 13T 国行版                      OnePlus
CPH2649           一加 13 印度版                       OnePlus
CPH2655           一加 13 北美版                       OnePlus
...
```

排序规则：精确匹配 > 前缀匹配 > 包含匹配，「国行 / 全网通」额外加权，
所以国行版总是排在最前。

### 多镜像自动回退

GitHub 在国内经常连不上，`models.py` 会依次尝试：

```
https://gh-proxy.com/https://raw.githubusercontent.com/...
https://ghfast.top/https://raw.githubusercontent.com/...
https://raw.githubusercontent.com/...
```

每个文件下完都会校验内容（必须含 Markdown 结构），防止把错误页存成机型库。

### 名称解析在哪些地方生效

`link` 和 `get` 都会先过一遍机型库：

```sh
$ ./ota.py link "一加 13"
[*] 机型解析: 一加 13 → PJZ110
[*] 查询 PJZ110 ...
```

带分支的输入也能识别：

```sh
./ota.py link PJZ110_11.C                        # → PJZ110 + 分支 11.C
./ota.py link PJZ110_11.C.36_1360_20250814       # 完整版本也能解析
```

分支字母会映射成 ColorOS 大版本：

| 分支 | ColorOS |
|---|---|
| `_11.A` | 15 |
| `_11.C` | 16 |
| `_11.F` | 17 |
| `_11.H` | 17+ |

### 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `ROMDB_DIR` | `/workspace/oplus/romdb` | 机型库缓存目录 |

---

## 工具组成

| 文件 | 作用 |
|---|---|
| `ota.py` | **一键封装**，串联下面所有工具（推荐用这个） |
| `models.py` | **机型库**：同步机型代号、名称模糊搜索、名称→代号解析 |
| `romer.py` | 查 ROMer 索引库（第三方整理，覆盖广） |
| `tomboy_pro.py` | 查官方 OTA 接口（实时，CN 区权威） |
| `C16_transer.py` | 解析 `downloadCheck?` 动态链接 → 真实 zip 地址 |
| `/workspace/payload-dumper/pdg` | HTTP Range 直读提取分区，不用下整包 |
| `venv/` | Python 环境（requests / cryptography / remotezip） |
| `romdb/` | 机型库缓存（MobileModels 的 `.md` 文件） |

### 数据流

```
用户输入型号
    │
    ├─→ ROMer 索引 (rom.yule.ink)      有记录就用，覆盖最广
    │       ↓ 没有
    └─→ tomboy_pro 官方接口            实时查询，10分钟过期
            │
            ↓
       得到链接（可能是 downloadCheck? 动态页）
            │
            ├─ 动态链接 → C16_transer 解析 → 真实 zip 地址
            └─ 静态地址 → 直接用
            │
            ↓
        pdg HTTP Range 直读 → 只下载需要的分区数据
```

---

## ota.py 一键工具

### link — 查下载链接

```sh
./ota.py link <型号> [--c15|--c16|--c17]
```

输出示例：

```
来源:     ROMer 索引
机型:     OP 13
型号:     PJZ110
版本:     PJZ110_17.0.0.103(CN01)
OTA:      PJZ110_11.F.07_2070_202610080010
系统:     ColorOS 17
补丁:     2026-09-01
构建:     2026-10-08T00:10:00
原始页:   https://component-ota-cn.allawntech.com/downloadCheck?c=...
下载:     https://gauss-compota-c-cn.allawnfs.com/.../xxx.zip?sign=...
          （签名链接，约 10 分钟内有效）
```

**注意**：`downloadCheck` 类型会显示两行——`原始页` 是索引里存的地址，`下载` 是解析后的真实地址。只有后者能用 `curl` 或 `pdg` 直接访问。

### parts — 列分区

```sh
./ota.py parts <型号或URL> [--c15|--c16|--c17]
```

只读 payload 元数据，几乎不耗流量（几百 KB），输出该包包含的所有分区及大小。

### get — 查 + 提取

```sh
./ota.py get <型号> <分区1,分区2,...> [--c15|--c16|--c17]
```

**版本选择**：

| 命令 | 选中的版本 | 输出目录 |
|---|---|---|
| `get PJZ110 dtbo` | 最新（C17） | `$OUTDIR/PJZ110/` |
| `get PJZ110 dtbo --c16` | ColorOS 16 | `$OUTDIR/PJZ110_c16/` |
| `get PJZ110 dtbo --c17` | ColorOS 17 | `$OUTDIR/PJZ110_c17/` |

不指定版本时取 ROMer 索引里标记为最新的版本。指定版本但该机型没有对应分支时，会明确提示而不是静默回退：

```
[!] 未找到 ColorOS 16 的版本，可能该机型没有此分支
```

**输入里带分支也会自动识别**：

```sh
./ota.py get PJZ110_11.C dtbo      # 自动按 C16 处理
```

分支字母与 ColorOS 的对应关系见[机型库](#机型库)章节。

输出到 `$OUTDIR/<型号>[_c版本]/`，默认 `$OUTDIR` 为 `/workspace/ota_out/`。

环境变量可覆盖：

```sh
PDG=/path/to/pdg OUTDIR=/workspace/myout ./ota.py get PJZ110 dtbo --c16
```

---

## 各工具单独用法

### romer.py — ROMer 索引查询

```sh
./romer.py latest PJZ110      # 某型号最新版
./romer.py find 关键词         # 搜机型/型号/版本
./romer.py c17                # 列出已升级 ColorOS 17 的机型
./romer.py list               # 全部机型最新版
./romer.py info PJZ110        # 某型号完整版本历史
```

数据缓存 1 小时（`/tmp/romer_catalog.json`），避免频繁请求。

**API**：`https://rom.yule.ink/api/ota/catalog`

### tomboy_pro.py — 官方接口查询

```sh
./venv/bin/python tomboy_pro.py <型号>_11.<分支> cn [选项]
```

分支与 ColorOS 对应：

| 分支 | ColorOS |
|---|---|
| `_11.A` | ColorOS 15 |
| `_11.C` | ColorOS 16 |
| `_11.F` | ColorOS 17 |
| `_11.H` | ColorOS 17+（部分机型受限） |

常用选项：

```sh
--original_link 1         同时显示原始页和解析后链接
--anti 1                  绕过 ColorOS 16+ 查询限制
--mode taste              配合 --anti 使用
--pki 1                   针对 Android 17 的兼容修正
```

其他子命令：

```sh
./venv/bin/python changelog_query.py PJZ110_11.F.07_2070 cn   # 查更新日志
./venv/bin/python desc_query.py PJZ110_11.F.07_2070 cn        # 查 changelog 网址
./venv/bin/python opex_query.py <完整版本> cn --info 17,OnePlus
./venv/bin/python sota_query.py <版本> cn --brand OnePlus --coloros ColorOS17
./venv/bin/python downgrade_query.py <前缀> <项目号> <SN> <DUID>
```

### pdg — 分区提取

```sh
# 列分区
./pdg -l "URL或本地zip"

# 提取指定分区
./pdg -q -c 4 -p dtbo,boot -o 输出目录 "URL"

# 提取全部分区（注意流量）
./pdg -o 输出目录 "URL"

# 本地文件照常可用
./pdg -p dtbo ota.zip
```

参数：

| 参数 | 说明 |
|---|---|
| `-p` | 分区名，逗号分隔 |
| `-o` | 输出目录 |
| `-c` | 并发数（远程建议 4-8，太高易被 CDN 限流） |
| `--resume` | 断点续传：空=全部启用，`none`=关闭，或指定分区名 |
| `--chunk` | 窗口大小，默认 4M |
| `--chunk-workers` | 单次大读取的并发 Range 数，默认 4 |
| `--ua` / `--header` | 自定义 UA / 请求头 |
| `--no-fec` | 跳过 FEC 生成（镜像 sha256 会不匹配，只能看不能刷） |

---

## 常见任务

### 提取某机型的 dtbo

```sh
./ota.py get PJZ110 dtbo
# → /workspace/ota_out/PJZ110/dtbo.img

# 指定要 C16 版本
./ota.py get PJZ110 dtbo --c16
# → /workspace/ota_out/PJZ110_c16/dtbo.img

# 也可以用中文名
./ota.py get "一加 13" dtbo --c16
```

### 查看某机型有哪些 ColorOS 版本

```sh
./romer.py info PJZ110
```

### 找已升级 ColorOS 17 的机型

```sh
./romer.py c17
```

### 只要长期有效的链接

```sh
./ota.py parts PJZ110    # 会打印实际使用的 URL
```

或直接调 API 拿原始 `source_url`：

```sh
curl -s 'https://rom.yule.ink/api/ota/catalog?model=PJZ110' | python3 -m json.tool
```

### 把提取的文件送到手机

```sh
# Linux 侧复制到共享目录
cp /workspace/ota_out/PJZ110/*.img /workspace/share/

# Android 侧再复制到下载目录
cp /data/local/tmp/eta/share/*.img /storage/emulated/0/Download/
```

---

## 故障排查

### `pdg` 报 `input is neither a payload.bin nor a zip`

多半是喂了 `downloadCheck?` 动态链接。先解析：

```sh
./venv/bin/python C16_transer.py "<downloadCheck链接>"
```

`ota.py` 会自动处理这一步。

### `pdg` 报 `remote returned unknown size`

链接已过期（403）。重新查：

```sh
./ota.py link PJZ110
```

签名链接有效期通常 10 分钟，大文件下载中途失效需重新获取并用 `curl -C -` 续传。

### `tomboy_pro` 返回 `2004 artifactV1Result is empty`

服务端拒绝返回，常见原因：

- 该 ColorOS 分支未开放查询（如内测分支 `_11.H`）
- 版本号不在公开升级路线上
- 请求过于频繁

可以试 `--anti 1 --mode taste`，或改用 ROMer 索引。

### 机型搜索不到 / 解析成错误的代号

先看机型库里有没有：

```sh
./ota.py models search "OPPO Find X8"
```

**搜不到** → 说明机型库没同步或版本旧：

```sh
./ota.py models sync --force
```

**解析错了**（比如把一加 13 认成一加 13R）→ 直接用代号绕过解析：

```sh
./ota.py link PJZ110          # 而不是 link "一加 13"
```

机型库优先匹配「国行 / 全网通」，但国际版机型的命名可能重叠。

### `models sync` 全部失败

三个镜像全挂时，检查网络：

```sh
curl -I https://gh-proxy.com/
curl -I https://raw.githubusercontent.com/
```

如果有代理，记得带上：

```sh
export https_proxy=http://127.0.0.1:7890
./ota.py models sync --force
```

### ROMer 数据滞后

它是第三方定时抓取的，`catalog_updated_at` 字段显示更新时间。要最新数据用 `tomboy_pro` 实时查，两者交叉验证。

### ROMer 的 `source_url` 打不开

分两种情况：

- 静态地址（`gauss-compota.../xx.zip`）→ 长期有效
- 动态地址（含 `downloadCheck?`）→ 需解析，且解析后的签名链接 10 分钟过期

---

## 环境重建

如果 `venv` 丢失：

```sh
cd /workspace/oplus
python3 -m venv venv
./venv/bin/python -m pip install requests cryptography remotezip
```

`pdg` 需要 Go + gcc + musl-dev + xz-dev，编译方法见
`/workspace/payload-dumper/README-URL.md`。
