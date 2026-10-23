# 版权与授权说明

本仓库采用**混合授权**：原创部分 MIT，第三方部分保持原授权。

## 一、原创部分（MIT）

```
ota.py
models.py
romer.py
setup.sh
README.md 及其他文档
```

Copyright (c) 2026 hzf1878

授权全文见 [LICENSE](LICENSE)。

## 二、第三方部分（LGPL-3.0）

以下 15 个文件来自 [JerryTse-OSS/OPlus-Tracker](https://github.com/JerryTse-OSS/OPlus-Tracker)，
遵循 **GNU Lesser General Public License v3.0**：

```
C16_transer.py
changelog_query.py
config.py
desc_query.py
downgrade_query.py
downgrade_query_old.py
earbuds_query.py
iot_query.py
iot_query_new.py
opex_analyzer.py
opex_query.py
realme_edl_query.py
sota_changelog_query.py
sota_query.py
tomboy_pro.py
```

上游授权全文：https://www.gnu.org/licenses/lgpl-3.0.html

**本仓库对上述文件未作修改**，原样分发。

如果你要修改这些文件并再分发，按 LGPL-3.0 要求需要：

- 保留原始版权声明
- 在文件中注明你的修改内容与日期
- 修改后的文件同样以 LGPL-3.0 发布

LGPL 允许与采用其他授权的代码组合使用（即本项目整体不必是 LGPL），
只要第三方部分本身仍遵守 LGPL 条款。

## 三、外部数据源（不属于本仓库代码）

| 来源 | 用途 | 说明 |
|---|---|---|
| [MobileModels](https://github.com/KHwang9883/MobileModels) | 机型代号库 | 运行时下载，不随仓库分发 |
| [rom.yule.ink](https://rom.yule.ink) | ROMer OTA 索引 API | 第三方服务 |
| 各厂商 OTA 服务器 | 固件查询 / 下载 | 仅调用公开接口 |

## 四、使用声明

本工具用于查询**个人设备**的官方固件、提取系统镜像用于学习与备份。

使用者需自行承担因刷写分区、修改系统文件等操作导致的后果——
包括但不限于设备无法启动、数据丢失、保修失效。

请遵守设备厂商服务条款及当地法律法规。请勿用于传播未经授权的内容。
