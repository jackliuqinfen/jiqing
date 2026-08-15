# COS 文件存储配置

产品保留数据库中的 `relative_path` 作为稳定对象标识，生产环境通过配置切换到腾讯云 COS。当前桶使用上海地域的单 AZ 存储桶：`jiqing-1468935338`。

## 生产环境变量

```ini
STORAGE_BACKEND=cos
COS_BUCKET=jiqing-1468935338
COS_REGION=ap-shanghai
COS_PREFIX=prod
COS_SECRET_ID=仅写入服务器环境变量
COS_SECRET_KEY=仅写入服务器环境变量
```

密钥只配置在 systemd 服务环境或服务器密钥管理中，不写入仓库、前端代码、发布包或知识库。建议使用仅允许当前桶对象读写的子账号密钥。

## 对象目录

应用原有路径会映射为以下 COS 对象键：

```text
prod/projects/{projectId}/合同文档/...
prod/projects/{projectId}/项目资料/...
prod/projects/{projectId}/审计附件/...
prod/projects/待关联项目/合同文档/...
```

合同上传早于项目确认时暂存于“待关联项目/合同文档”；项目确认后的归档迁移应在业务确认事务完成后执行。历史文件迁移前不删除本地文件。

## 历史文件迁移

先执行预览：

```bash
python3 scripts/migrate-upload-files-to-cos.py
```

确认清单、桶权限和对象数量无误后，再执行：

```bash
python3 scripts/migrate-upload-files-to-cos.py --apply
```

脚本只上传并校验对象，不删除本地文件；删除本地副本需要另行完成备份和恢复演练后再决定。
