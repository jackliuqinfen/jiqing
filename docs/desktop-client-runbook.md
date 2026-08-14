# Windows 桌面客户端运维交付手册

> 适用范围：集庆工程管理 Electron 桌面客户端，Windows 10/11 x64。
>
> 安全边界：中央服务器是唯一业务数据源；桌面同步仅从服务器下载到本地，
> 不自动上传、重命名或删除服务器文件。不得使用虚构项目、合同、财务或资料数据。

## 1. 发布状态与硬门禁

- `internal-test` 可连接经明确配置的 HTTP 或 HTTPS 地址，窗口必须显示“内部测试”。
- `production` 只接受 HTTPS，并且必须使用 Windows 代码签名证书。
- 当前正式服务器仍是 HTTP，只能制作 `internal-test` 安装包，不能通过 production 门禁。
- production 工作流使用 `forceCodeSigning=true`。签名失败时不得上传或分发安装包。
- 安装、登录、真实文件同步、撤权和卸载保留文件仍需在独立 Windows 验收账号上人工完成。

## 2. 本地开发

在仓库根目录执行：

```powershell
npm ci
npm --prefix desktop ci
npm run dev
```

另开 PowerShell，使用明确的未打包开发入口：

```powershell
$env:DESKTOP_RELEASE_CHANNEL = 'development'
$env:DESKTOP_SERVER_URL = 'http://127.0.0.1:5173'
npm --prefix desktop start
```

`DESKTOP_SERVER_URL` 只影响未打包开发或专用 smoke 入口。已打包应用只读取
`app.asar` 内嵌 release profile，运行时环境变量不能覆盖或削弱 production。

## 3. 本地自动化验证

```powershell
python -m unittest discover -s server/tests -v
npm run test:premium-theme
npm run test:desktop-settings
npm run test:desktop-sync-ui
npm run build
npm --prefix desktop run verify
```

`verify` 依次运行 desktop tests、图标生成、内嵌技术用 `internal-test` profile
的目录打包、打包内容/fuse 校验和真实 Electron smoke。smoke 使用随机
`127.0.0.1` 端口与未打包 `test/smoke-app.mjs`，不会为 production 增加运行时后门。

若 Electron 43 在本机返回 `ERR_FAILED (-2) loading 'app://connecting/'`，
该次 smoke 不通过。不得以 Node 单元测试代替；应在干净 Windows 验收机或
GitHub Actions `windows-latest` 重新执行并保留失败日志。

## 4. 制作 internal-test 安装包

从安全渠道取得测试服务器 URL，不把值写入仓库：

```powershell
$env:DESKTOP_RELEASE_CHANNEL = 'internal-test'
$env:DESKTOP_SERVER_URL = Read-Host 'Internal-test server URL'
node desktop/scripts/validate-release-configuration.mjs
npm --prefix desktop run dist:win
npm --prefix desktop run verify:package
```

产物位于 `desktop/dist/JiqingERP-<version>-x64-Setup.exe`。只把它交给受控
验收用户，并明确标记为内部测试。HTTP 安装包不得改名或转作 production。

## 5. GitHub 变量与 secrets

在仓库 `Settings > Environments` 预先创建受保护的 `production`
Environment，并配置：

- Variables: `DESKTOP_TEST_URL`
- Variables: `DESKTOP_PRODUCTION_URL`
- Variables: `WINDOWS_EXPECTED_SIGNER_SHA256`
- Secrets: `WINDOWS_CERTIFICATE_BASE64`
- Secrets: `WINDOWS_CERTIFICATE_PASSWORD`

`WINDOWS_EXPECTED_SIGNER_SHA256` 是预期代码签名证书的 64 位 SHA-256
指纹，不是从本次上传的 PFX 动态计算。证书与密码只放在
`production` Environment Secrets，不保留同名 repository 或 organization
Secrets。`DESKTOP_TEST_URL` 可继续作为仓库级变量。

不要在 issue、日志、文档、脚本或提交中记录实际 secret 值。手工触发
`Windows Desktop` workflow 生成 internal-test；只有符合
`desktop-v<major>.<minor>.<patch>` 的 tag 才能通过 production 门禁。

production job 会先等待 `production` Environment 审批，再在同一个
PowerShell 步骤中验证 HTTPS、secrets 和预期指纹，解码 PFX、构建并检查
安装包与 `JiqingERP.exe`。两个文件必须为 `Valid`、使用相同的预期
SHA-256 签名者指纹并包含时间戳。该步骤使用 `try/finally` 在上传
artifact 之前清除 `CSC_*` 环境变量并删除临时 PFX；签名凭据不写入
`GITHUB_ENV`。

## 6. Production 前置条件

1. `DESKTOP_PRODUCTION_URL` 是有效的 `https://` origin。
2. `/api/health` 在该 origin 返回 ERP 健康响应，且无跨 origin 重定向。
3. TLS 证书链、主机名和有效期均正常，不允许绕过证书错误。
4. `production` Environment 已启用 Required reviewers、Prevent
   self-review，并禁止管理员绕过；部署分支或 tag 策略只允许
   `desktop-v*`。
5. 仓库 ruleset 限制 `desktop-v*` tag 的创建、更新和删除。
6. Windows 签名证书、密码和固定 SHA-256 指纹已配置且未过期。
7. `desktop-v<major>.<minor>.<patch>` tag 指向已完成自动化和人工验收的提交。
8. 安装包和内含 `JiqingERP.exe` 的签名均需在验收机复核。

GitHub Environment 的审批人、自审限制、管理员绕过、tag 部署策略和
Secrets 归属不能由仓库 YAML 自动配置，发布负责人必须在 GitHub
Settings 中逐项验收。私有仓库还需确认当前 GitHub 套餐支持所需的
Environment 保护规则。

## 7. 为一个验收用户启用同步

只使用已授权的真实用户与其已有可见项目：

1. 管理员进入 `系统管理 > 系统设置 > 本地资料同步策略`。
2. 启用桌面同步，保持“默认不勾选”。
3. 在“允许用户”中只加入该验收用户 ID；不要扩大角色范围。
4. 选择“管理员指定项目”，只加入已获批准的真实项目。
5. 保存后，让该用户重新登录桌面客户端。
6. 用户进入 `资料中心 > 本地资料同步`，选择独立于安装目录的本地文件夹。
7. 只勾选获批项目并启动同步。
8. 验收结束后移除该用户 ID 或关闭全局开关，并确认后续同步停止。

## 8. 读取脱敏诊断

当前可安全收集的范围是客户端版本、环境标签、用户可见同步状态、最后成功时间、
完成/失败文件计数、策略版本和稳定错误码。服务不可用页的错误码为
`E-SERVER-UNAVAILABLE`。

不要收集或转发密码、Bearer token、Cookie、合同正文、OCR 内容、个人联系方式、
服务器文件系统路径或同步文件本身。当前版本尚无已验收的一键诊断包导出；
不要用 DevTools 网络内容替代。需要更深排查时，由工程人员在授权设备上复现。

## 9. 暂停同步与撤权

- 单用户：从 `allowedUserIds` 移除用户，保存策略。
- 指定项目：从 `allowedProjectRefs` 移除项目，保存策略。
- 全局暂停：关闭“启用桌面同步”，保存策略。

策略在下一次刷新生效，每次 manifest/download 仍由服务器重新校验权限。
撤权后不得宣称能删除用户复制到非托管位置的文件。

## 10. 回滚

1. 保留上一版已验证且已签名的安装包、版本号和 SHA-256。
2. 暂停同步或撤销验收用户授权。
3. 卸载当前客户端；不要删除同步资料目录。
4. 安装上一版，复核签名、版本、环境 origin 和 `/api/health`。
5. 登录后先保持同步关闭，确认基础页面正常，再恢复一个用户的授权。

远端 Web UI 回滚遵循服务器发布流程；无需为单纯 Web 回滚重装客户端。

## 11. 卸载与资料保留

NSIS 为每用户安装，`deleteAppDataOnUninstall: false`。卸载只移除应用二进制和
快捷方式，不得静默删除用户选择的同步目录或其中资料。同步目录不得位于安装目录。

卸载保留行为必须由人工验收确认后才能发布。发现安装器删除用户资料时立即停止分发。

## 12. 健康与 HTTPS 检查

```powershell
$origin = Read-Host 'Server origin'
$health = Invoke-RestMethod -Uri "$origin/api/health" -Method Get
$health.success
$health.data.status
```

预期为 `True` 和 `ok`。production 还应执行：

```powershell
if (-not $origin.StartsWith('https://')) { throw 'Production requires HTTPS' }
Invoke-WebRequest -Uri "$origin/api/health" -Method Get
```

任何证书错误、HTTP 降级、跨 origin 重定向或非 ERP 健康响应都应阻断 production。

## 13. 尚未完成的人工验收门禁

- 非管理员 Windows 账号安装和卸载。
- Start 菜单、桌面、任务栏图标。
- 真实登录、退出、上传、下载、预览和打印。
- 一个已授权真实项目的字节数与 SHA-256 对比。
- 本地修改不被覆盖、本地删除不影响服务器。
- 撤权后同步停止。
- 卸载后同步资料明确保留。
- 安装包与应用程序签名在 Windows 上均显示有效。

这些项目在人工记录签字前均为未完成，不得宣称 production 可发布。
