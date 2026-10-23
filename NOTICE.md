# 版权与授权说明

本仓库包含不同来源的代码，各自遵循原有授权。

## 本仓库原创部分

`ota.py`、`models.py`、`romer.py`、`setup.sh` 及文档

- 作者：本仓库维护者
- 授权：MIT（见各文件头部）

## 第三方代码

以下文件来自 [JerryTse-OSS/OPlus-Tracker](https://github.com/JerryTse-OSS/OPlus-Tracker)，
遵循 **LGPL-3.0**：

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

按 LGPL-3.0 要求：

- 保留原始版权声明
- 修改过的文件需注明修改内容
- 允许再分发，但衍生作品需同样以 LGPL-3.0 发布

本仓库对这些文件**未做修改**。

## 外部数据源

| 来源 | 用途 | 说明 |
|---|---|---|
| [MobileModels](https://github.com/KHwang9883/MobileModels) | 机型代号库 | 运行时下载，不随仓库分发 |
| [rom.yule.ink](https://rom.yule.ink) | ROMer 索引 API | 第三方服务，非本仓库代码 |
| 各厂商 OTA 服务器 | 固件查询 | 仅调用公开接口 |

## 使用声明

本工具仅用于查询个人设备的官方固件、提取系统镜像用于研究。
使用者需自行承担因刷机、修改系统分区等操作导致的后果。

请遵守设备厂商的服务条款及当地法律法规。
