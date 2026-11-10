# 安徽农信制卡接口服务

依据 `document/安徽农信银行与卡商系统接口规范_v1.7_20260818.md`。

## 启动

使用 Python 3.12 或以上版本：

```powershell
python -m pip install -r requirements.txt
python main.py
```

服务地址与卡商代码见 `resources/application.yaml`。公共配置共用，本地与正式环境分别放在 `server.environments` 中。

默认 `server.active: local`：本地访问和监听 `127.0.0.1:8000`，开启自动重载。
正式环境 `production`：访问地址 `192.168.20.166:18081`，监听 `0.0.0.0:18081`，关闭自动重载。

可以修改 `server.active`，也可以用环境变量覆盖（不必修改配置文件）：

```powershell
$env:AHNX_ENV = "production"
python main.py
```

切回本地：

```powershell
$env:AHNX_ENV = "local"
python main.py
```

更改监听配置后需要重启服务。

## Tkinter 接口测试窗口

在项目根目录另开终端：

```powershell
python -m ui.client
```

选择环境（local / production）会自动切换服务地址，卡商固定为 HB，再选择接口，点击“生成请求”，可编辑 JSON 中的分页、日期、机构等条件，再点击“发送 POST”。窗口通过真实 HTTP 请求访问服务，显示状态码、耗时和原始响应，并校验成功响应的报文结构。修改接口后请重新生成请求。

服务码固定使用规范 3.5 的 HB 映射：3033000313 / 3033000314。查询业务字段使用规范 JSON 示例中的小写别名。

测试窗口包含两个页签：

- **JSON 请求测试**：保留可编辑请求与原始响应，支持 Ctrl + 鼠标滚轮调整字体大小，Ctrl + Z 撤销编辑。
- **表单查询与表格**：输入 page、limit、日期、机构等字段，自动拼接 ESB 请求。报文头自动生成；所有查询和筛选条件默认空，表示不限。page、limit 留空时按第 1 页、每页 10 条提交。日期框白底，支持日历选择和清空。
- 表格以中文表头、细线单元格网格展示接口返回的 records，上一页、下一页按服务端 count 和 limit 计算，沿用上次成功查询的条件；修改查询条件或 limit 后点击“查询”提交。
- 每个响应字段均提供模糊筛选框，不区分大小写，多列条件同时满足。筛选仅作用于当前页，接口查询条件仍按规范精确匹配，不改变服务端 count。


## 数据与接口

`server.sftppath` 直接填写订单根目录，默认 `"./安徽农信借记卡订单文件"`。支持 Windows 单、双反斜杠，修改后重启。`server.scan-interval-ms` 单位毫秒，当前为 `60000`（1 分钟）。

- 原始文件存放在 `data/yyyyMMdd/`。文件名为 `pending_日期.txt`、`making_日期.txt`、`finished_日期.txt`；兼容 `finshed` 拼写。文件后缀日期不参与业务筛选，不要求等于目录日期。只以所在日期目录决定扫描范围，以前缀决定状态。
- 每行是一个 `{"biz":{...}}` JSON 对象，空行和仅空白字符的行忽略，支持 UTF-8 BOM、CRLF。多笔订单放在同一文件中，不是 JSON 数组。坏行记录文件及行号，其他有效行正常导入，下一轮再次读取坏行。
- 每轮完整重读当天目录的全部三类 txt，不按文件名跳过、不依赖修改时间。读取期间文件大小或修改时间发生变化时跳过该文件，本轮不导入，下轮重试。源文件只读，不修改、不删除、不移动。
- report 只使用一个 `orders.sqlite3`。`orders` 表按订单 `orderId` 为主键，原始 biz 每个字段对应一列，另有 `crdprdsts`、`logisticscompany`、`logisticsno`。`scans` 表在同一库保存凌晨补扫进度，不再创建分日期数据库或 index.sqlite3。
- 相同订单反复读取执行更新，不增加重复行；同一状态重传可修正订单字段。状态优先级 `finished > making > pending`，旧状态文件不会把已完成订单退回。源文件中暂时不再出现的订单不会从数据库删除。
- `biz` 支持 `logisticscompany`、`logisticsno`。pending/making 可以省略、为 null 或空字符串，查询物流始终为 null；finished 必须同时提供两个非空字符串，空白字符串也无效。物流从源文件读取，不再硬编码。非法行跳过且不覆盖库中已有记录，当天的 service_YYYYMMDD.log 记录文件完整路径、行号及原因，其他有效行继续处理；下轮会再次尝试。当前已有 txt 的 7 笔订单已补上“顺丰速运 / SF5149695523766”。
- 启动扫描当天及待补扫目录，每日 01:00 后首轮完整补扫昨天；00:00～01:00 之间启动的补扫不算最终兜底。停机跨日后补扫遗漏日期。首次启动不自动扫描全部历史目录；本次已有历史状态文件已一次性导入。
- 物流 POST 查询只读 report/orders.sqlite3，不再读取 mock 或旧版分日期数据库。回盘接口保留 ESB 报文，暂未提供实际数据，返回空列表。
- 升级迁移时保留整个 data、report 和配置。旧版数据库在本次切换前备份到 build 目录，单库生成后不再读取旧库。禁止用随包历史库覆盖现场更新后的数据库。
- HTTP 404 返回 `{"code":404,"msg":"url not found"}`，500 返回 `{"code":500,"msg":"ks server error"}`；其他参数和业务错误通过 HTTP 200 ESB 业务码返回。恒宝代码配对：`ICCARD12001001/3033000313`、`ICCARD12001002/3033000314`。

## 代码结构

查询：`main.py` → `app/app.py` → `app/api/v1/endpoints` → `app/services` → report 单库。

扫描：`app/app.py` 生命周期 → `app/workers/order_scan.py` → 订单文件与 report 数据库。

`app/models` 定义 Pydantic 报文与序列化，`app/core` 读取配置，`ui/client.py` 为独立测试客户端。

## 验证

```powershell
python -m unittest discover -s tests -v
python -m pytest -q
```

pytest 另行安装。已按规范 3.3 校验请求日期和时间与服务器北京时间偏差不超过 ±5 分钟；`globalSq` 使用 `resources/replay.sqlite3` 持久化去重（跨接口、并发与重启均生效），重复请求以 HTTP 200 和业务失败码返回。空业务体也执行防重放校验。`msgId` 为可选消息流水号，规范没有单独的去重要求。数据库包含已接收流水号，部署更新时应保留。

规范 2.2 要求银行侧默认读取超时 30 秒、服务方应在 10 秒内返回。±5 分钟是请求时间新鲜度，不是响应超时。测试客户端使用 30 秒网络超时；当前未增加服务端 10 秒强制中止机制，需要在部署和性能验收中验证该目标。

表格左侧序号从 1 开始，按当前展示页编号；制卡文件名称列加宽，被截断的单元格悬浮 0.4 秒显示全文。

JSON 测试页与表单查询页分别选择接口、展示结果，互不改写请求和响应。“生成请求”“发送 POST”仅在 JSON 页显示；JSON 页按编辑器原文发送，可用于测试错误报文。

JSON 测试页支持 GET/POST 和编辑路径。查询业务接口按规范仍仅接受 POST；对业务接口发送 GET 时返回 HTTP 200 ESB 请求方式错误。未知地址返回 404 和 {"msg":"url not found","code":404}，内部异常返回 500 和 {"msg":"ks server error","code":500}。字段校验错误在 resText 和 bizResText 中显示字段路径及原因。


## Windows 无终端发布包

发布产物：`dist/AHNX-Service-Windows-x64.zip`。解压后整体复制，主程序和外部资源布局为：

```text
AHNX-Service/
  AHNX-Service.exe
  AHNX-TestClient.exe
  resources/
    application.yaml
  使用说明.txt
```

双击 `AHNX-Service.exe` 启动后台服务，双击 `AHNX-TestClient.exe` 打开测试客户端。在程序目录运行 `.\AHNX-Service.exe --stop` 正常停止服务。两个 EXE 分别内置运行库，目标 Windows x64 机器无需安装 Python。发布包保留外置 `resources/application.yaml`，现场订单目录通过 `sftppath` 指定。
发布包原样复制项目 YAML 的 active（local 为 8000，production 为正式端口），EXE 始终禁用 reload，并以 EXE 同目录 resources/application.yaml 的 active 为准，不读取 AHNX_ENV。源码运行时仍支持环境变量覆盖。
日志按北京时间日期写入 `resources/service_YYYYMMDD.log`（如 `service_20261103.log`），跨天自动切换，不再按大小轮转。每日 01:00 后首轮扫描清理日期早于七天前的日期日志；失败记录错误并在下一轮重试。原有 service.log 保留，不自动删除。可访问 `http://127.0.0.1:18082/` 确认服务启动。
资源均从 EXE 同目录读取，与启动时所在目录无关。目录需要写入权限。
请用同一 Windows 账号、同一登录会话启动和停止。当前为后台进程，不是注册的 Windows 系统服务，不自动开机启动。
升级时保留目标机器的配置、订单数据、去重数据库，不要用发布包中的初始资源覆盖已有运行数据。

重新构建与验证：

```powershell
python -m pip install -r requirements-build.txt
python build_service.py
python tests/verify_release.py
```

构建在临时目录组装发布包并写入 dist，不包含订单目录或运行数据库。
EXE 集成验证在临时副本中进行，覆盖后台启动、真实 HTTP 查询、读取临时测试订单、重复启动保护及正常停止。

发布程序已更新：日志格式为 `[yyyy-MM-dd HH:mm:ss] SSS LEVEL logger: message`；启动成功和失败均弹出英文提示；正常停止后删除 replay.sqlite3 及其 SQLite 辅助文件，因此防重放记录只覆盖本次运行，不再跨服务重启保留。强制结束进程或断电时无法保证执行清理。

打包不会改写 active。请修改实际运行 EXE 同目录的 resources/application.yaml；项目根目录和发布目录是两份独立配置。修改后停止旧服务，再重新启动。
