# 离线封面与配图渲染器

不依赖任何生图 API 或密钥。用 HTML/CSS + SVG 排版，再由无头 Chrome 截图成 PNG。
配色与版式遵循 [`../config/style-prompt.md`](../config/style-prompt.md)：深海军蓝底、白色中文黑体标题、短青线、右侧青蓝到琥珀金的细线波浪。

## 依赖

- `google-chrome`（或 `chromium`），支持 `--headless=new`
- Python 3；Pillow 可选（用于校验并修正输出尺寸）
- 字体：Noto Sans CJK SC（`fonts-noto-cjk`）

## 用法

```bash
cd skills/cover-gen/render

# 封面：标题用 "|" 分行，输出固定 1500×600
python3 render.py cover --eyebrow "Article → X Draft" \
  --title "写完就有草稿：|“文章 → X 草稿”自动流水线" \
  --subtitle "脱敏、润色、封面、建草稿全自动，发布留给人" -o cover.png

# 单张配图：JSON 规格 → 1600×900 PNG
python3 render.py diagram specs/2026-10-20-x-auto-draft-pipeline/01-pipeline-overview.json -o 01.png

# 一篇文章的全部图片：目录里每个 *.json 按自己的 "output" 字段写到文章目录下
python3 render.py batch specs/2026-10-20-x-auto-draft-pipeline -o ../../../articles/2026-10-20-x-auto-draft-pipeline
```

加 `--keep-html` 会在 PNG 旁边留下中间 HTML，便于在浏览器里调样式。

## 规格类型

所有类型都支持 `title`、`subtitle`、`footer`、`output`、`seed`（背景波浪随机种子）；配图另支持右上角 `tag`。

| type | 尺寸 | 主要字段 |
| --- | --- | --- |
| `cover` | 1500×600 | `eyebrow`（可省略）、`title`（字符串用 `\|` 分行，或字符串数组）、`subtitle` |
| `pipeline` | 1600×900 | `steps: [{title, desc, accent?: "amber"}]`，默认每行 4 个，蛇形排列 |
| `compare` | 1600×900 | `labels: [前, 后]`，`rows: [{before, after}]`；`[[词]]` 会被高亮 |
| `lanes` | 1600×900 | `lanes: [{icon, name, role, items[], kind?: "human"}]` |
| `boundary` | 1600×900 | `left`/`right: {name, tag, items[], button?}`，`wall` 为中间分界文字；条目可写成 `{text, class: "draft"}` 以虚线强调 |

样式在 `templates/`：`base.css`（调色板）、`cover.css`、`diagram.css`。

## 检查

渲染后逐张打开 PNG 看：文字不越界、不被裁切、没有豆腐块（缺字方框）。中文只用 Noto Sans CJK SC 已覆盖的字符。
`compare` 示例里只放替换后的假名或词表里已经公开的测试词，不要把真实敏感词写进规格文件。
