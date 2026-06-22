"""
md2html.py - 把研究报告 .md 转换成 self-contained HTML
"""
import re
import sys
import argparse
from pathlib import Path


def slugify(s):
    """中英混合 slug：保留中文"""
    s = re.sub(r'[^\w\u4e00-\u9fff\- ]', '', s).strip().lower()
    s = re.sub(r'\s+', '-', s)
    return s or 'section'


def inline(s):
    """行内 Markdown → HTML"""
    s = re.sub(r'`([^`]+)`', r'<code class="md-inline-code">\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    return s


def is_table_separator(line):
    """判断是否是表格分隔行 |---|---|"""
    return bool(re.match(r'^\|?[\s\-:|]+\|?$', line.strip())) and '-' in line


def md_to_html(md_text):
    """Markdown → HTML body"""
    lines = md_text.split('\n')
    out = []
    i = 0
    state = None  # 'p' | 'ul' | 'ol' | 'code' | 'table'
    buf = []
    code_lang = ''
    in_code = False  # 独立的代码块状态标志

    def close_state():
        nonlocal state, buf
        if state is None:
            return
        if state == 'p':
            for line in buf:
                if line.strip():
                    out.append(f'<p class="md-p">{inline(line.strip())}</p>')
        elif state == 'ul':
            out.append('<ul class="md-ul">')
            for item in buf:
                m = re.match(r'^[-*]\s+(.+)$', item.strip())
                if m:
                    out.append(f'<li>{inline(m.group(1))}</li>')
            out.append('</ul>')
        elif state == 'ol':
            out.append('<ol class="md-ol">')
            for item in buf:
                m = re.match(r'^\d+\.\s+(.+)$', item.strip())
                if m:
                    out.append(f'<li>{inline(m.group(1))}</li>')
            out.append('</ol>')
        elif state == 'table':
            # buf: [header, sep, row1, row2, ...]
            head_cells = [c.strip() for c in buf[0].strip().strip('|').split('|')]
            rows = []
            for r in buf[2:]:
                cells = [c.strip() for c in r.strip().strip('|').split('|')]
                rows.append(cells)
            out.append('<details class="md-table" open>')
            out.append('<summary>表格（点击折叠 / 展开）</summary>')
            out.append('<div class="tbl-wrap"><table>')
            out.append('<thead><tr>')
            for h in head_cells:
                out.append(f'<th>{inline(h)}</th>')
            out.append('</tr></thead>')
            out.append('<tbody>')
            for row in rows:
                out.append('<tr>')
                for c in row:
                    out.append(f'<td>{inline(c)}</td>')
                out.append('</tr>')
            out.append('</tbody>')
            out.append('</table></div>')
            out.append('</details>')
        state = None
        buf = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # 代码块
        if stripped.startswith('```'):
            close_state()
            if not in_code:
                # 开始新的代码块
                in_code = True
                state = 'code'
                buf = []
                code_lang = stripped[3:].strip() or 'text'
            else:
                # 结束当前代码块
                esc = '\n'.join(buf).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                out.append(f'<pre class="md-code"><code class="lang-{code_lang}">{esc}</code></pre>')
                in_code = False
                state = None
                buf = []
                code_lang = ''
            i += 1
            continue
        if state == 'code':
            buf.append(line)
            i += 1
            continue

        # 标题
        m = re.match(r'^(#{1,6})\s+(.+)$', stripped)
        if m:
            close_state()
            level = len(m.group(1))
            title = m.group(2).strip()
            anchor = slugify(title)
            cls = f'md-h{level}'
            out.append(f'<h{level} id="{anchor}" class="{cls}"><a href="#{anchor}" class="anchor">#</a> {inline(title)}</h{level}>')
            i += 1
            continue

        # 表格起始检测
        if stripped.startswith('|') and i + 1 < len(lines) and is_table_separator(lines[i+1]):
            close_state()
            state = 'table'
            buf = [stripped]
            i += 1
            continue
        if state == 'table':
            if stripped.startswith('|'):
                buf.append(stripped)
                i += 1
                continue
            else:
                close_state()
                # fall through

        # 列表
        if re.match(r'^[-*]\s+', stripped):
            if state not in ('ul',):
                close_state()
                state = 'ul'
                buf = []
            buf.append(stripped)
            i += 1
            continue
        if re.match(r'^\d+\.\s+', stripped):
            if state not in ('ol',):
                close_state()
                state = 'ol'
                buf = []
            buf.append(stripped)
            i += 1
            continue

        # 引用
        if stripped.startswith('>'):
            close_state()
            quote_text = stripped.lstrip('>').strip()
            out.append(f'<blockquote class="md-quote">{inline(quote_text)}</blockquote>')
            i += 1
            continue

        # 分隔线
        if re.match(r'^-{3,}$', stripped):
            close_state()
            out.append('<hr class="md-hr">')
            i += 1
            continue

        # 空行（结束当前 block）
        if stripped == '':
            close_state()
            i += 1
            continue

        # 段落
        if state != 'p':
            close_state()
            state = 'p'
            buf = []
        buf.append(line)
        i += 1

    close_state()
    return '\n'.join(out)


def build_toc(md_text):
    """提取 H2/H3 生成目录"""
    items = []
    for m in re.finditer(r'^(#{2,3})\s+(.+)$', md_text, re.MULTILINE):
        level = len(m.group(1))
        title = m.group(2).strip()
        anchor = slugify(title)
        cls = 'toc-h3' if level == 3 else 'toc-h2'
        items.append(f'<li class="{cls}"><a href="#{anchor}">{title}</a></li>')
    if not items:
        return ''
    return '<ul class="toc">' + '\n'.join(items) + '</ul>'


HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} · AI 项目落地研究</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="../assets/report.css">
</head>
<body>

<header class="report-header">
  <div class="container">
    <div class="header-row">
      <a href="../index.html" class="logo">
        <span class="logo-mark">◆</span>
        <span class="logo-text">AI 项目落地研究</span>
      </a>
      <nav class="report-nav">
        <a href="../index.html#highlights">← 回到首页</a>
        <a href="../index.html#latest">最新更新</a>
        <a href="../index.html#industries">行业地图</a>
      </nav>
    </div>
  </div>
</header>

<div class="report-layout">
  <aside class="report-toc">
    <div class="toc-title">目录</div>
    {toc}
  </aside>

  <article class="report-body">
    <div class="report-meta">
      <span class="meta-tag">{tag}</span>
      <span class="meta-updated">最后更新：{updated}</span>
    </div>
    {body}
  </article>
</div>

<footer class="report-footer">
  <div class="container">
    <p>本报告由 AI 项目落地研究仓库产出 · <a href="../index.html">回到首页</a> · <a href="https://github.com/FrankFang99/ai-landing-research" target="_blank" rel="noopener">仓库地址</a></p>
  </div>
</footer>

<script>
(function() {{
  const toc = document.querySelector('.report-toc');
  if (!toc) return;
  const title = toc.querySelector('.toc-title');
  if (!title) return;
  title.addEventListener('click', () => toc.classList.toggle('toc-open'));
}})();
</script>

</body>
</html>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input', help='input markdown file')
    ap.add_argument('output', help='output html file')
    ap.add_argument('--title', required=True)
    ap.add_argument('--desc', default='')
    ap.add_argument('--tag', default='研究报告')
    ap.add_argument('--updated', default='2026-06-22')
    args = ap.parse_args()

    md = Path(args.input).read_text(encoding='utf-8')
    body = md_to_html(md)
    toc = build_toc(md)
    html = HTML_TEMPLATE.format(
        title=args.title, desc=args.desc or args.title,
        tag=args.tag, updated=args.updated,
        body=body, toc=toc,
    )
    Path(args.output).write_text(html, encoding='utf-8')
    print(f'Wrote {args.output} ({len(html)} chars, toc items: {toc.count("<li")})')
    # 调试输出
    print(f'  paragraphs: {body.count("<p ")}')
    print(f'  tables: {body.count("md-table")}')
    print(f'  lists: {body.count("<ul") + body.count("<ol")}')


if __name__ == '__main__':
    main()