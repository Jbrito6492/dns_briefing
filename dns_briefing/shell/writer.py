from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import boto3
import markdown as _md

# ── HTML template ──────────────────────────────────────────────────────────────
# Design: terminal aesthetic — monospace throughout, phosphor-tinted palette.
# JetBrains Mono + Fira Mono (fallback). Electric lime (#a3e635) on near-black.
# CRT scanline overlay. Blinking cursor in header prompt. 1080px wide column.
_REPORT_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DNS Briefing — {date_display}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500&family=Fira+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:           #080808;
  --surface:      #0e0e0e;
  --surface-2:    #141414;
  --border:       #1c1c1c;
  --border-hi:    #2a2a2a;
  --text:         #b4c4b0;
  --text-bright:  #e2f0de;
  --text-muted:   #3a4a36;
  --accent:       #a3e635;
  --accent-dim:   rgba(163,230,53,.07);
  --accent-bd:    rgba(163,230,53,.2);
  --red:          #f87171;
  --red-dim:      rgba(248,113,113,.07);
  --cyan:         #5eead4;
  --amber:        #f59e0b;
  --ff-mono:      'JetBrains Mono', 'Fira Mono', 'Courier New', monospace;
}}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

html {{ font-size: 16px; scroll-behavior: smooth; }}

body {{
  background: var(--bg);
  color: var(--text);
  font-family: var(--ff-mono);
  font-weight: 300;
  line-height: 1.75;
  min-height: 100vh;
  overflow-x: hidden;
  -webkit-text-size-adjust: 100%;
}}

main, header, footer, article {{ max-width: 100%; overflow-x: hidden; }}

/* CRT scanlines */
body::before {{
  content: '';
  position: fixed;
  inset: 0;
  background: repeating-linear-gradient(
    transparent 0px,
    transparent 2px,
    rgba(0,0,0,.06) 2px,
    rgba(0,0,0,.06) 3px
  );
  pointer-events: none;
  z-index: 900;
}}

/* Top accent line */
.top-bar {{
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--accent);
  opacity: .7;
  z-index: 999;
}}

/* ── Header ── */
header {{
  max-width: 1080px;
  margin: 0 auto;
  padding: 40px 40px 28px;
  border-bottom: 1px solid var(--border);
}}

/* ── Status bar ── */
.status-bar {{
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  align-items: center;
  font-size: .72rem;
  letter-spacing: .04em;
  margin-bottom: 22px;
  padding: 8px 12px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-left: 2px solid var(--border-hi);
}}

.stat-key {{
  color: var(--text-muted);
  letter-spacing: .12em;
  font-size: .62rem;
  text-transform: uppercase;
  margin-right: 5px;
}}

.stat-val {{
  color: var(--text-bright);
  font-weight: 500;
}}

.stat-sep {{ color: var(--border-hi); }}

.stat-domain {{ color: var(--accent); }}

.stat-count {{
  color: var(--text-muted);
  font-size: .88em;
}}

.term-prompt {{
  font-size: .8rem;
  color: var(--text-muted);
  margin-bottom: 20px;
  letter-spacing: .01em;
}}

.prompt-user   {{ color: var(--accent); font-weight: 500; }}
.prompt-at     {{ color: var(--text-muted); }}
.prompt-host   {{ color: var(--cyan); font-weight: 500; }}
.prompt-sep    {{ color: var(--text-muted); }}
.prompt-dir    {{ color: var(--accent); opacity: .6; }}
.prompt-dollar {{ color: var(--text-muted); margin: 0 .4em; }}

.cursor {{
  display: inline-block;
  width: .5em;
  height: .9em;
  background: var(--accent);
  vertical-align: text-bottom;
  margin-left: 2px;
  animation: blink 1.1s step-end infinite;
}}
@keyframes blink {{ 50% {{ opacity: 0; }} }}

.header-row {{
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}}

.header-left {{ flex: 1; }}

.network-tag {{
  font-size: .65rem;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-bottom: 8px;
  display: block;
}}

h1 {{
  font-family: var(--ff-mono);
  font-size: clamp(1.8rem, 4vw, 2.8rem);
  font-weight: 500;
  color: var(--text-bright);
  letter-spacing: -.02em;
  line-height: 1.05;
  margin-bottom: 6px;
}}

h1 .bracket {{ color: var(--accent); font-weight: 300; }}

header time {{
  font-size: .75rem;
  color: var(--text-muted);
  letter-spacing: .06em;
}}

.nav-link {{
  font-size: .65rem;
  letter-spacing: .1em;
  color: var(--text-muted);
  text-decoration: none;
  transition: color .15s;
  white-space: nowrap;
  margin-top: 4px;
  display: inline-block;
}}
.nav-link:hover {{ color: var(--accent); }}

/* ── Main content ── */
main {{
  max-width: 1080px;
  margin: 0 auto;
  padding: 36px 40px 72px;
}}

/* ── TL;DR card ── */
.tldr-card {{
  background: var(--surface);
  border: 1px solid var(--border-hi);
  border-left: 2px solid var(--accent);
  padding: 20px 24px;
  margin-bottom: 44px;
}}

.tldr-card h2 {{
  font-size: .65rem;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 14px;
  margin-top: 0;
  border: none;
}}

.tldr-card h2::before,
.tldr-card h2::after {{ display: none; }}

.tldr-card ul {{
  list-style: none;
  padding: 0;
  margin: 0;
}}

.tldr-card li {{
  font-size: .9rem;
  color: var(--text-bright);
  line-height: 1.65;
  padding: 8px 0 8px 24px;
  border-bottom: 1px solid var(--border);
  position: relative;
}}

.tldr-card li:last-child {{ border-bottom: none; }}

.tldr-card li::before {{
  content: '>';
  color: var(--accent);
  font-weight: 500;
  font-size: .85rem;
  line-height: 1;
  position: absolute;
  left: 0;
  top: 10px;
}}

/* ── Section headers (h2) ── */
.report h2 {{
  font-family: var(--ff-mono);
  font-size: .7rem;
  font-weight: 400;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-top: 48px;
  margin-bottom: 18px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}}

.report h2::before {{
  content: '── ';
  color: var(--accent);
  letter-spacing: 0;
}}

.report h2::after {{ display: none; }}

/* ── Body text ── */
.report {{
  overflow-wrap: break-word;
  word-break: break-word;
}}

.report p {{
  font-size: .9rem;
  line-height: 1.8;
  margin-bottom: 1em;
  color: var(--text);
}}

.report ul, .report ol {{
  padding-left: 1.6em;
  margin-bottom: 1em;
}}

.report li {{
  margin-bottom: .3em;
  line-height: 1.7;
  font-size: .9rem;
}}

.report strong {{
  color: var(--text-bright);
  font-weight: 500;
}}

.report em {{
  color: var(--text);
  font-style: italic;
}}

/* ── Inline code (domain names, IPs) ── */
.report code {{
  font-family: var(--ff-mono);
  font-size: .85em;
  color: var(--accent);
  background: var(--accent-dim);
  border: 1px solid var(--accent-bd);
  padding: .05em .28em;
  overflow-wrap: anywhere;
}}

.report pre {{
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-left: 2px solid var(--border-hi);
  padding: 1em 1.25em;
  overflow-x: auto;
  margin: 1.2em 0;
  white-space: pre-wrap;
  word-break: break-word;
}}

.report pre code {{
  background: none;
  border: none;
  padding: 0;
  font-size: .85em;
  color: var(--cyan);
}}

.report a {{
  color: var(--cyan);
  text-decoration: none;
  border-bottom: 1px solid rgba(94,234,212,.2);
  transition: border-color .15s;
}}
.report a:hover {{ border-color: var(--cyan); }}

/* ── Footer ── */
footer {{
  max-width: 1080px;
  margin: 0 auto;
  padding: 16px 40px 40px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 12px;
  font-size: .65rem;
  letter-spacing: .08em;
  color: var(--text-muted);
}}

footer .sep {{ color: var(--border-hi); }}

@media (max-width: 768px) {{
  html {{ font-size: 15px; }}
  header, main, footer {{ padding-left: 20px; padding-right: 20px; }}
  header {{ padding-top: 32px; padding-bottom: 20px; }}
  main {{ padding-top: 24px; padding-bottom: 48px; }}
  footer {{ padding-top: 14px; padding-bottom: 32px; flex-wrap: wrap; gap: 6px; }}
  h1 {{ font-size: 1.75rem; }}
  .header-row {{ flex-direction: column; }}
  .tldr-card {{ padding: 14px 16px; }}
  .tldr-card li {{ font-size: .85rem; }}
  .report h2 {{ margin-top: 36px; }}
  .cursor {{ display: none; }}
  .status-bar {{ display: none; }}
}}
</style>
</head>
<body>
<div class="top-bar"></div>
<header>
  <div class="term-prompt">
    <span class="prompt-user">ubuntu</span><span class="prompt-at">@</span><span class="prompt-host">mav</span><span class="prompt-sep">:</span><span class="prompt-dir">~/dns-briefing</span><span class="prompt-dollar">$</span><span> cat latest.log</span><span class="cursor"></span>
  </div>
  {stat_bar}
  <div class="header-row">
    <div class="header-left">
      <span class="network-tag">{network_name}</span>
      <h1><span class="bracket">[</span>dns-briefing<span class="bracket">]</span></h1>
      <time>{date_display}</time>
    </div>
    <a href="index.html" class="nav-link">archive &rarr;</a>
  </div>
</header>
<main>
  <article class="report">{content_html}</article>
</main>
<footer>
  <span>generated {generated_at} utc</span>
  <span class="sep">&middot;</span>
  <span>next: 08:00 mst</span>
</footer>
<script>
// Promote TL;DR into a card component
(function() {{
  var h2s = document.querySelectorAll('.report h2');
  if (!h2s.length || h2s[0].textContent.trim() !== 'TL;DR') return;
  var card = document.createElement('div');
  card.className = 'tldr-card';
  var anchor = h2s[0];
  anchor.parentNode.insertBefore(card, anchor);
  var node = anchor;
  while (node) {{
    var next = node.nextElementSibling;
    card.appendChild(node);
    if (!next || next.tagName === 'H2') break;
    node = next;
  }}
}})();
</script>
</body>
</html>"""

_INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DNS Briefing — {network_name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500&family=Fira+Mono:wght@400&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #080808; --surface: #0e0e0e; --border: #1c1c1c; --border-hi: #2a2a2a;
  --text: #b4c4b0; --text-bright: #e2f0de; --text-muted: #3a4a36;
  --accent: #a3e635; --accent-dim: rgba(163,230,53,.07); --accent-bd: rgba(163,230,53,.2);
  --cyan: #5eead4;
  --ff-mono: 'JetBrains Mono', 'Fira Mono', 'Courier New', monospace;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ font-size: 16px; }}
body {{
  background: var(--bg); color: var(--text);
  font-family: var(--ff-mono); font-weight: 300;
  min-height: 100vh; overflow-x: hidden;
}}
body::before {{
  content: '';
  position: fixed; inset: 0;
  background: repeating-linear-gradient(
    transparent 0px, transparent 2px,
    rgba(0,0,0,.06) 2px, rgba(0,0,0,.06) 3px
  );
  pointer-events: none; z-index: 900;
}}
.top-bar {{
  position: fixed; top: 0; left: 0; right: 0; height: 2px;
  background: var(--accent); opacity: .7; z-index: 999;
}}
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 0 40px; }}
header {{ padding: 40px 0 28px; border-bottom: 1px solid var(--border); }}
.term-prompt {{
  font-size: .8rem; color: var(--text-muted); margin-bottom: 20px; letter-spacing: .01em;
}}
.prompt-user {{ color: var(--accent); font-weight: 500; }}
.prompt-at, .prompt-sep {{ color: var(--text-muted); }}
.prompt-host {{ color: var(--cyan); font-weight: 500; }}
.prompt-dir {{ color: var(--accent); opacity: .6; }}
.prompt-dollar {{ color: var(--text-muted); margin: 0 .4em; }}
.cursor {{
  display: inline-block; width: .5em; height: .9em;
  background: var(--accent); vertical-align: text-bottom; margin-left: 2px;
  animation: blink 1.1s step-end infinite;
}}
@keyframes blink {{ 50% {{ opacity: 0; }} }}
.network-tag {{
  font-size: .65rem; letter-spacing: .18em; text-transform: uppercase;
  color: var(--text-muted); margin-bottom: 8px; display: block;
}}
h1 {{
  font-family: var(--ff-mono); font-size: clamp(1.8rem, 4vw, 2.8rem);
  font-weight: 500; color: var(--text-bright); letter-spacing: -.02em; line-height: 1.05;
  margin-bottom: 20px;
}}
h1 .bracket {{ color: var(--accent); font-weight: 300; }}
.latest-btn {{
  display: inline-block;
  font-size: .7rem; letter-spacing: .12em; text-transform: uppercase;
  color: var(--bg); background: var(--accent);
  padding: 8px 18px; text-decoration: none; transition: opacity .15s; font-weight: 500;
}}
.latest-btn:hover {{ opacity: .85; }}
main {{ padding: 36px 0 72px; }}
.section-label {{
  font-size: .7rem; letter-spacing: .16em; text-transform: uppercase;
  color: var(--text-muted); margin-bottom: 18px; padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}}
.section-label::before {{ content: '── '; color: var(--accent); letter-spacing: 0; }}
.report-list {{ list-style: none; }}
.report-list li {{ border-bottom: 1px solid var(--border); }}
.report-list a {{
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 0; color: var(--text); text-decoration: none;
  font-size: .8rem; letter-spacing: .04em; transition: color .12s;
}}
.report-list a::before {{ content: '>  '; color: var(--text-muted); transition: color .12s; }}
.report-list a:hover, .report-list a:hover::before {{ color: var(--accent); }}
.report-list .arrow {{ color: var(--text-muted); font-size: .7rem; }}
footer {{
  padding: 16px 0 40px; border-top: 1px solid var(--border);
  font-size: .65rem; letter-spacing: .08em; color: var(--text-muted);
}}
@media (max-width: 640px) {{
  html {{ font-size: 15px; }}
  .wrap {{ padding: 0 20px; }}
  header {{ padding: 32px 0 20px; }}
  h1 {{ font-size: 1.75rem; }}
  .latest-btn {{ display: block; text-align: center; }}
  .cursor {{ display: none; }}
  .report-list a {{ font-size: .75rem; }}
}}
</style>
</head>
<body>
<div class="top-bar"></div>
<header class="wrap">
  <div class="term-prompt">
    <span class="prompt-user">ubuntu</span><span class="prompt-at">@</span><span class="prompt-host">mav</span><span class="prompt-sep">:</span><span class="prompt-dir">~/dns-briefing</span><span class="prompt-dollar">$</span><span> ls -lt reports/</span><span class="cursor"></span>
  </div>
  <span class="network-tag">{network_name}</span>
  <h1><span class="bracket">[</span>dns-briefing<span class="bracket">]</span></h1>
  <a href="latest.html" class="latest-btn">latest report &rarr;</a>
</header>
<main class="wrap">
  <p class="section-label" style="margin-top:0">archive</p>
  <ul class="report-list">
{report_items}
  </ul>
</main>
<footer class="wrap">daily briefings &middot; runs 08:00 mst</footer>
</body>
</html>"""


def _render_stat_bar(stats: dict[str, Any] | None) -> str:
    if not stats:
        return ""
    total = stats.get("total_queries") or 0
    blocked = stats.get("total_blocked") or 0
    clients = stats.get("unique_clients") or 0
    top_domain = stats.get("top_blocked_domain") or ""
    top_count = stats.get("top_blocked_count") or 0
    pct = f"{blocked / total * 100:.1f}%" if total else "0.0%"

    parts = [
        f'<span class="stat"><span class="stat-key">QUERIES</span>'
        f' <span class="stat-val">{total:,}</span></span>',
        '<span class="stat-sep">&middot;</span>',
        f'<span class="stat"><span class="stat-key">BLOCKED</span>'
        f' <span class="stat-val">{pct}</span></span>',
        '<span class="stat-sep">&middot;</span>',
        f'<span class="stat"><span class="stat-key">CLIENTS</span>'
        f' <span class="stat-val">{clients}</span></span>',
    ]
    if top_domain:
        parts += [
            '<span class="stat-sep">&middot;</span>',
            f'<span class="stat"><span class="stat-key">TOP BLOCKED</span>'
            f' <span class="stat-val stat-domain">{top_domain}</span>'
            f' <span class="stat-count">({top_count:,})</span></span>',
        ]
    return f'<div class="status-bar">{"".join(parts)}</div>'


class ReportWriter:
    def __init__(
        self,
        local_dir: str,
        s3_bucket: str,
        network_name: str = "Home Network",
        s3_client: Any = None,
        dry_run: bool = False,
    ) -> None:
        self._local_dir = Path(local_dir)
        self._s3_bucket = s3_bucket
        self._network_name = network_name
        self._s3 = s3_client
        self._dry_run = dry_run

    @classmethod
    def from_config(
        cls,
        local_dir: str,
        s3_bucket: str,
        region: str,
        network_name: str = "Home Network",
        dry_run: bool = False,
    ) -> ReportWriter:
        return cls(
            local_dir=local_dir,
            s3_bucket=s3_bucket,
            network_name=network_name,
            s3_client=boto3.client("s3", region_name=region),
            dry_run=dry_run,
        )

    def write(self, report: str, report_date: date, stats: dict[str, Any] | None = None) -> None:
        self._write_local(report, report_date)
        html = self._render_html(report, report_date, stats=stats)
        self._write_html(html, report_date)
        self._update_index()
        if not self._dry_run:
            self._write_s3(report, report_date)
            self._write_s3_html(html, report_date)

    # ── Markdown (local) ─────────────────────────────────────────────────────

    def _write_local(self, report: str, report_date: date) -> None:
        self._local_dir.mkdir(parents=True, exist_ok=True)
        dated = self._local_dir / f"{report_date.isoformat()}.md"
        dated.write_text(report, encoding="utf-8")
        self._symlink(self._local_dir / "latest.md", dated.name)

    # ── HTML (local) ──────────────────────────────────────────────────────────

    def _render_html(
        self, report: str, report_date: date, stats: dict[str, Any] | None = None
    ) -> str:
        content_html = _md.markdown(report, extensions=["extra", "nl2br"])
        date_display = report_date.strftime("%A, %B %-d, %Y")
        generated_at = datetime.now(tz=UTC).strftime("%H:%M")
        return _REPORT_TEMPLATE.format(
            date_display=date_display,
            network_name=self._network_name,
            generated_at=generated_at,
            content_html=content_html,
            stat_bar=_render_stat_bar(stats),
        )

    def _write_html(self, html: str, report_date: date) -> None:
        dated_html = self._local_dir / f"{report_date.isoformat()}.html"
        dated_html.write_text(html, encoding="utf-8")
        self._symlink(self._local_dir / "latest.html", dated_html.name)

    def _update_index(self) -> None:
        html_files = sorted(
            [p for p in self._local_dir.glob("????-??-??.html")],
            reverse=True,
        )
        items = "\n".join(
            f'    <li><a href="{p.name}"><span>{p.stem}</span>'
            f'<span class="arrow">&rarr;</span></a></li>'
            for p in html_files
        )
        index_html = _INDEX_TEMPLATE.format(
            network_name=self._network_name,
            report_items=items,
        )
        (self._local_dir / "index.html").write_text(index_html, encoding="utf-8")

    # ── S3 ────────────────────────────────────────────────────────────────────

    def _write_s3(self, report: str, report_date: date) -> None:
        body = report.encode("utf-8")
        key = f"{report_date.year}/{report_date.month:02d}/{report_date.day:02d}.md"
        self._s3.put_object(Bucket=self._s3_bucket, Key=key, Body=body, ContentType="text/markdown")
        self._s3.put_object(
            Bucket=self._s3_bucket, Key="latest.md", Body=body, ContentType="text/markdown"
        )

    def _write_s3_html(self, html: str, report_date: date) -> None:
        html_body = html.encode("utf-8")
        key = f"{report_date.year}/{report_date.month:02d}/{report_date.day:02d}.html"
        self._s3.put_object(
            Bucket=self._s3_bucket, Key=key, Body=html_body, ContentType="text/html"
        )
        self._s3.put_object(
            Bucket=self._s3_bucket, Key="latest.html", Body=html_body, ContentType="text/html"
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _symlink(link: Path, target_name: str) -> None:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(target_name)
