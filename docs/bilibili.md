# iPhone + Shadowrocket：更新哔哩哔哩去广告模块

更新日期：2026-11-13。

这份 `biliad.module` 是在 app2smile 脚本基础上整理的本地适配模块，已上传至本仓库。它包含 UDP 拒绝规则、HTTPS 解密主机、额外 URL 重写规则以及 JSON / Protobuf 响应处理脚本。

## 模块下载地址

复制下面的完整地址，按第 2 步添加：

```text
https://raw.githubusercontent.com/blairevan/Shadowrocket-ADBlock-Rules-Forever/release/modules/biliad.module
```

[直接查看模块](https://raw.githubusercontent.com/blairevan/Shadowrocket-ADBlock-Rules-Forever/release/modules/biliad.module) · [在线分享说明](https://github.com/blairevan/Shadowrocket-ADBlock-Rules-Forever/blob/release/docs/bilibili.md)

## 1. 删除旧的 B 站去广告模块

打开「Shadowrocket → 配置 → 模块」，找到原来的「哔哩哔哩去广告 / Bilibili / biliad」等 B 站专项去广告模块，直接删除，无需保留回退。

可使用模块区域右上角「···」进入管理，选中旧模块后删除。只删除此次要替换的 B 站模块，其他应用的模块无需一起删除。更新完成后只启用一份 B 站专项去广告模块。

## 2. 通过 URL 添加这份适配模块

1. 进入「Shadowrocket → 配置 → 模块」。
2. 点击右上角「+」。
3. 在 URL 输入框粘贴上面的模块下载地址。
4. 点击下载，等待成功。
5. 启用「哔哩哔哩去广告」。

此地址直接返回适配模块文本。不要把仓库首页或本说明页面的地址填进 URL 输入框，也不要在首页的节点订阅入口添加。

下载完成后，模块内容应包含 `[Rule]`、`[MITM]`、`[URL Rewrite]`、`[Script]` 四部分。无需再手动新建并粘贴模块。

## 3. 检查当前配置的 HTTPS 解密和证书

进入「配置 → 当前使用的配置右侧 ⓘ → HTTPS 解密」，开启 HTTPS 解密。

如果当前配置已有正常工作的证书，可继续使用，无需重新生成。如果从未配置过证书：

1. 在 HTTPS 解密页进入「证书」，生成新的 CA 证书并选择安装。
2. 到 iPhone「设置 → 已下载描述文件」完成安装；没有此入口时，到「通用 → VPN 与设备管理」查找。
3. 到「设置 → 通用 → 关于本机 → 证书信任设置」，对刚刚在本机生成并安装的证书开启完全信任。
4. 返回 Shadowrocket，确认当前配置已开启 HTTPS 解密。

每台手机自行生成、安装自己的证书，不需要分享节点订阅、完整配置、证书或私钥。本模块不包含这些内容。

模块中已追加所需解密主机，至少包括 `app.bilibili.com` 和 `grpc.biliapi.net`，无需填写 `*` 开启全站解密。

[Apple 官方证书信任说明](https://support.apple.com/zh-cn/102390)

## 4. 重新加载连接

回到 Shadowrocket 首页，确认「全局路由」为「配置」。关闭连接开关，等待断开后重新开启，确认连接成功。

若出现模块语法错误、证书错误或脚本下载失败，先解决错误，再进行后续测试。

## 5. 清理 B 站缓存

保持 Shadowrocket 已连接，进入「哔哩哔哩 → 我的 → 设置 → 缓存设置」，按实际界面依次清理：

- 本地图片缓存。
- 本地缓存垃圾。
- 其它缓存。
- 直播资源缓存。

不同版本的菜单名称可能略有区别。不要误删需要保留的离线下载视频，无需先卸载应用。清理缓存用于排除已有素材的影响，不能仅凭清理成功认定广告缓存已全部删除。

## 6. 冷启动验证

1. 从屏幕底部上滑并停顿，打开多任务界面。
2. 找到哔哩哔哩，将应用卡片向上划掉。
3. 保持 Shadowrocket 已连接，重新打开哔哩哔哩。
4. 检查是否直接进入首页、是否仍出现全屏广告或「跳过」倒计时。
5. 重复两三次，并分别在 Wi-Fi、蜂窝网络下验证。
6. 检查首页加载、视频播放和评论等常用功能是否正常。

广告投放具有随机性，短时间未出现广告不能单独证明拦截脚本已经命中。实际效果需结合手机端请求记录和脚本日志判断；客户端接口更新后可能需要调整模块。

## 7. 后续更新与排查

需要更新时，在模块管理中对已添加的远程模块执行更新/重新下载；不同版本的入口名称可能不同。若没有更新入口，可删除这一份模块，再用相同 URL 下载一次，然后重新连接。

模块更新后仍有广告，按顺序检查：

1. VPN 是否正常连接，全局路由是否为「配置」。
2. 新模块是否启用，旧 B 站模块是否已删除。
3. 当前使用的配置是否开启 HTTPS 解密，证书是否已安装并信任。
4. 两个脚本是否下载成功；浏览器能打开链接不等于 Shadowrocket 已成功加载脚本。
5. 是否清理缓存并真正划掉 B 站后台。
6. 请求记录中是否出现 `app.bilibili.com` / `grpc.biliapi.net`，脚本日志中是否有下载、解析或执行错误。

如果 B 站无法正常联网，先停用新模块并重新连接，恢复可用状态后再根据日志排查。

## 来源与规则范围

- [app2smile/rules 上游仓库](https://github.com/app2smile/rules)
- [JSON 脚本](https://raw.githubusercontent.com/app2smile/rules/master/js/bilibili-json.js)
- [Protobuf 脚本](https://raw.githubusercontent.com/app2smile/rules/master/js/bilibili-proto.js)
- [模块添加入口参考（社区手册）](https://github.com/riseaudio/shadowrocket#模块)

本文件是适配配置，不能将全部新增规则归为 app2smile 上游原版。两个远程脚本由上游维护，可能独立于本模块发生更新。

UDP 拒绝规则作用于 `bilibili.com` 和 `biliapi.net` 两个后缀下的 UDP 请求，范围并非仅 UDP 443，意图减少相关请求经 QUIC 绕过 HTTPS 处理。实际匹配与拦截结果以手机日志为准。

## Summary

- What changed：删除旧 B 站去广告模块，通过 URL 添加本仓库的适配模块，检查 HTTPS 解密与证书，重新连接并清理缓存。
- Why：模块脚本需要成功下载，并处理对应的解密请求；失效下载、配置未生效、重复模块及缓存都可能影响结果。
- Verification：发布时核验模块公开下载地址、两个脚本地址返回 HTTP 200，并将下载模块与原文件逐字节比对。该核验不代替手机端导入及拦截验证。

下载地址可用性核验命令：

```bash
curl -fLsS -o /dev/null -w '%{http_code}\n' https://raw.githubusercontent.com/blairevan/Shadowrocket-ADBlock-Rules-Forever/release/modules/biliad.module
```
