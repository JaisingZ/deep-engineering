# deep-engineering

> **这个仓库应当保持私有。** `articles/<目录>/article.md` 保存的是脱敏之前的原文，里面可以有公司、产品、内网地址、账号和截图里的个人信息。脱敏报告也会逐条抄录命中的原文。正式词表是 `skills/desensitize/config/sensitive-words.txt`。

这里存放作者关于软件工程的中文原文，主题包括 AI Native 开发与知识工程。每篇文章是一条流水线的输入：发现新增或更新，脱敏，按 X 长文的阅读方式润色，准备封面，保存为 X Articles 草稿，校验，然后通知作者。

**草稿只保存，不自动发布。** 作者核对草稿后再亲手发布。

本仓库目前只有目录约定、技能说明和配置模板，没有调用外部接口的脚本，也没有持续集成。

## 目录

```text
.
├── README.md                 本说明
├── articles/                 原文。一篇文章一个目录
│   ├── README.md
│   └── _template/            空模板，不是一篇文章
├── docs/                     可选。仅用于将来的 GitHub Pages，只能放脱敏后的成品
└── skills/                   脱敏、润色、封面。配置放在各自的 config/ 下
    ├── desensitize/
    │   ├── SKILL.md
    │   └── config/sensitive-words.txt
    ├── polish/
    │   ├── SKILL.md
    │   └── config/polish-rules.md
    └── cover-gen/
        ├── SKILL.md
        └── config/style-prompt.md
```

`articles/_template/` 不进入流水线。

## 如何新增一篇文章

1. 复制 `articles/_template/`，改名为 `articles/YYYY-MM-DD-短标题/`。短标题用小写英文或拼音，单词之间用连字符，不要加空格。例如 `articles/2026-01-01-knowledge-workflow/`。
2. 编辑该目录下的 `article.md`。填好文首信息，再写正文。
3. 图片放在同一目录或其中的 `images/`。正文只用相对路径引用，例如 `![说明](./images/diagram.png)`。
4. 已有封面时，把文件放在该目录并命名为 `cover.png`。没有也可以，流水线会另写封面提示，生图在仓库外完成。
5. 提交这个目录。不要把密钥、令牌或正式脱敏词表写进文章或配置。

目录名里的日期与 `article.md` 文首的 `date` 保持一致。约定的细节见 [articles/README.md](articles/README.md)。

## 流水线

对每篇新增或更新的文章，按下面的顺序做。上一步没有通过，就不要做下一步。

1. **发现。** 找出 `articles/YYYY-MM-DD-短标题/article.md`。忽略 `_template`。目录里还没有 `x/`，或者 `article.md`、配图比 `x/` 里的产物更新，就当作待处理。
2. **脱敏。** 按 [skills/desensitize/SKILL.md](skills/desensitize/SKILL.md) 扫描正文、代码块、文件名和图片里的文字。原图不改，打码写到副本。通过标准是对脱敏后的材料复扫，命中数为 0。报告写到 `x/desensitize-report.md`。
3. **润色。** 按 [skills/polish/SKILL.md](skills/polish/SKILL.md) 和 [skills/polish/config/polish-rules.md](skills/polish/config/polish-rules.md)，把脱敏后的正文改成 X 长文。不改变技术内容。结果是 `x/article.x.md`；需要分篇时是 `x/article.x.partN.md`。
4. **封面。** 按 [skills/cover-gen/SKILL.md](skills/cover-gen/SKILL.md) 写 `x/cover-prompt.md`。目录里已有 `cover.png` 就沿用，并在提示里注明。没有则根据润色稿和 [skills/cover-gen/config/style-prompt.md](skills/cover-gen/config/style-prompt.md) 写生图提示。图在仓库外生成。
5. **草稿。** 把润色稿存成 X Articles 草稿。只创建或更新草稿，不发布。
6. **校验。** 核对脱敏复扫、标题层级、列表、篇幅、图片数量、代码块长度、分篇衔接和封面。草稿的状态必须是未发布。
7. **通知。** 把草稿位置、报告路径和「需要作者亲手发布」告诉作者。通知不是发布。

`article.md` 始终保持为脱敏前原文，流水线不覆盖它。生成文件放在该文目录的 `x/`：

| 文件 | 步骤 |
| --- | --- |
| `x/desensitize-report.md` | 脱敏 |
| `x/article.x.md` 或 `x/article.x.partN.md` | 润色 |
| `x/cover-prompt.md` | 封面 |

## 不要提交的东西

- 密钥、令牌、`.env`

`docs/` 的用途见 [docs/README.md](docs/README.md)。那里只能出现已经脱敏的成品，不能用来放原文。
