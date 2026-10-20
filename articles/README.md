# 文章目录

一篇文章对应一个目录：

```text
articles/YYYY-MM-DD-短标题/
├── article.md          必需。脱敏前的原文
├── cover.png           可选。作者自备的封面
├── images/             可选。正文图片
├── 其他配图            可选。也可以直接放在文章目录下
└── x/                  流水线写入。不要手改后当作原文
    ├── desensitize-report.md
    ├── article.x.md              或 article.x.part1.md、part2.md……
    └── cover-prompt.md
```

`articles/_template/` 是空模板，不是文章。复制它来开新篇，不要在模板目录里写正式内容。

## 目录名

- 日期用 `YYYY-MM-DD`，与 `article.md` 文首的 `date` 相同。
- 短标题用小写英文或拼音，单词之间用连字符，不含空格和标点。
- 示例：`articles/2026-01-01-knowledge-workflow/`。

## article.md

文首使用 YAML front matter：

| 字段 | 是否必需 | 说明 |
| --- | --- | --- |
| `title` | 必需 | 文章标题 |
| `subtitle` | 必需 | 副标题，一句话说明视角；没有内容时保留空字符串 |
| `date` | 必需 | `YYYY-MM-DD` |
| `tags` | 必需 | 字符串列表，至少一个 |
| `x_series` | 可选 | 同一主题分成多篇时的系列名。不使用时删掉该字段 |

正文是脱敏前的源文。流水线只读它，不把替换结果写回这个文件。

## 图片

- 引用必须是相对路径，相对于 `article.md`。例如 `![接口关系](./images/api-flow.png)` 或 `![目录关系](./layout.png)`。
- 不要使用 `http://` 或 `https://` 图片地址。需要的图先放到文章目录里再引用。
- 文件名用小写英文或拼音加连字符。不要在文件名里放公司、产品、客户、人名或内网信息。
- 原图保留。脱敏如果要打码，另存为带 `-redacted` 的副本，例如 `images/api-flow.png` 的副本是 `images/api-flow-redacted.png`。润色稿引用副本。

## x/ 里的产物

这些文件由流水线生成，供草稿使用：

- `desensitize-report.md`：每条命中、替换结果、文件与行号，以及尚未处理的遗留项。它会包含原文片段，不要在仓库公开时提交。
- `article.x.md`：单篇润色稿。拆成多篇时改为 `article.x.part1.md`、`article.x.part2.md`，依此类推，不再另写一个不带序号的 `article.x.md`。
- `cover-prompt.md`：封面决定。已有 `cover.png` 时记录「沿用该文件」；没有时写出给外部生图用的提示。

`x/` 不是原文。文章要改，改 `article.md`，然后重新跑流水线。
