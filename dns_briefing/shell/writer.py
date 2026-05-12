from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import boto3
import markdown as _md

# ── HTML template ──────────────────────────────────────────────────────────────
# Design: dark intelligence-briefing aesthetic.
# Cormorant Garamond (authoritative serif) + Crimson Pro (body) + Fira Mono (data).
# Electric lime (#a3e635) accent on deep navy. Grain texture overlay.
_REPORT_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DNS Briefing — {date_display}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=Crimson+Pro:ital,wght@0,300;0,400;0,500;1,400&family=Fira+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:           #06070d;
  --surface:      #0a0c15;
  --surface-2:    #0e1020;
  --border:       #181e30;
  --border-hi:    #252d45;
  --text:         #aab4c8;
  --text-bright:  #d4dcea;
  --text-muted:   #3e4a62;
  --accent:       #a3e635;
  --accent-dim:   rgba(163,230,53,.1);
  --accent-bd:    rgba(163,230,53,.25);
  --red:          #f87171;
  --red-dim:      rgba(248,113,113,.08);
  --cyan:         #67e8f9;
  --amber:        #fcd34d;
  --ff-display:   'Cormorant Garamond', Georgia, serif;
  --ff-body:      'Crimson Pro', Georgia, serif;
  --ff-mono:      'Fira Mono', 'Courier New', monospace;
}}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

html {{ font-size: 18px; scroll-behavior: smooth; }}

body {{
  background: var(--bg);
  color: var(--text);
  font-family: var(--ff-body);
  font-weight: 300;
  line-height: 1.78;
  min-height: 100vh;
  overflow-x: hidden;
  -webkit-text-size-adjust: 100%;
}}

/* Prevent any element from blowing out the layout */
main, header, footer, article {{ max-width: 100%; overflow-x: hidden; }}

/* Grain overlay */
body::after {{
  content: '';
  position: fixed;
  inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.035'/%3E%3C/svg%3E");
  pointer-events: none;
  z-index: 1000;
  opacity: .6;
}}

/* Top accent line */
.top-bar {{
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--accent) 0%, rgba(163,230,53,.35) 55%, transparent 100%);
  z-index: 999;
}}

/* ── Header ── */
header {{
  max-width: 720px;
  margin: 0 auto;
  padding: 52px 32px 36px;
  border-bottom: 1px solid var(--border);
}}

.header-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
}}

.classification {{
  font-family: var(--ff-mono);
  font-size: .6rem;
  letter-spacing: .24em;
  text-transform: uppercase;
  color: var(--text-muted);
}}

.nav-link {{
  font-family: var(--ff-mono);
  font-size: .6rem;
  letter-spacing: .12em;
  color: var(--text-muted);
  text-decoration: none;
  transition: color .2s;
}}
.nav-link:hover {{ color: var(--accent); }}

.network-tag {{
  display: inline-block;
  font-family: var(--ff-mono);
  font-size: .58rem;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--accent);
  border: 1px solid var(--accent-bd);
  background: var(--accent-dim);
  padding: 3px 10px;
  margin-bottom: 14px;
}}

h1 {{
  font-family: var(--ff-display);
  font-size: clamp(3rem, 7vw, 5rem);
  font-weight: 600;
  color: var(--text-bright);
  letter-spacing: -.015em;
  line-height: 1;
  margin-bottom: 10px;
}}

header time {{
  font-family: var(--ff-display);
  font-style: italic;
  font-size: 1.05rem;
  color: var(--text-muted);
}}

/* ── Main content ── */
main {{
  max-width: 720px;
  margin: 0 auto;
  padding: 44px 32px 72px;
}}

/* ── TL;DR card ── */
.tldr-card {{
  background: var(--surface);
  border: 1px solid var(--border-hi);
  border-left: 3px solid var(--accent);
  padding: 24px 28px;
  margin-bottom: 48px;
  position: relative;
}}

.tldr-card h2 {{
  font-family: var(--ff-mono);
  font-size: .6rem;
  letter-spacing: .22em;
  text-transform: uppercase;
  color: var(--accent);
  margin-bottom: 16px;
  margin-top: 0;
  border: none;
}}

.tldr-card h2::after {{ display: none; }}

.tldr-card ul {{
  list-style: none;
  padding: 0;
  margin: 0;
}}

.tldr-card li {{
  font-family: var(--ff-body);
  font-size: 1.05rem;
  color: var(--text-bright);
  line-height: 1.65;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
  display: flex;
  gap: 12px;
}}

.tldr-card li:last-child {{ border-bottom: none; }}

.tldr-card li::before {{
  content: '·';
  color: var(--accent);
  font-size: 1.4rem;
  line-height: 1.2;
  flex-shrink: 0;
}}

/* ── Section headers (h2) ── */
.report h2 {{
  font-family: var(--ff-mono);
  font-size: .62rem;
  font-weight: 500;
  letter-spacing: .2em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-top: 52px;
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
  position: relative;
}}

.report h2::after {{
  content: '';
  position: absolute;
  bottom: -1px; left: 0;
  width: 28px; height: 1px;
  background: var(--accent);
}}

/* ── Body text ── */
.report {{
  overflow-wrap: break-word;
  word-break: break-word;
}}

.report p {{
  font-size: 1rem;
  line-height: 1.82;
  margin-bottom: 1.1em;
  color: var(--text);
}}

.report ul, .report ol {{
  padding-left: 1.4em;
  margin-bottom: 1.1em;
}}

.report li {{
  margin-bottom: .35em;
  line-height: 1.72;
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
  font-size: .78em;
  color: var(--accent);
  background: var(--accent-dim);
  border: 1px solid var(--accent-bd);
  padding: .1em .32em;
  border-radius: 2px;
  word-break: break-all;       /* long domains wrap instead of overflow */
  overflow-wrap: anywhere;
}}

.report pre {{
  background: var(--surface-2);
  border: 1px solid var(--border);
  padding: 1.25em 1.5em;
  overflow-x: auto;
  margin: 1.4em 0;
  white-space: pre-wrap;
  word-break: break-word;
}}

.report pre code {{
  background: none;
  border: none;
  padding: 0;
  font-size: .82em;
  color: var(--cyan);
}}

.report a {{
  color: var(--cyan);
  text-decoration: none;
  border-bottom: 1px solid rgba(103,232,249,.25);
  transition: border-color .2s;
}}
.report a:hover {{ border-color: var(--cyan); }}

/* ── Footer ── */
footer {{
  max-width: 720px;
  margin: 0 auto;
  padding: 20px 32px 48px;
  border-top: 1px solid var(--border);
  display: flex;
  gap: 10px;
  font-family: var(--ff-mono);
  font-size: .6rem;
  letter-spacing: .1em;
  color: var(--text-muted);
}}

footer .sep {{ color: var(--border-hi); }}

@media (max-width: 640px) {{
  html {{ font-size: 16px; }}
  header, main, footer {{ padding-left: 18px; padding-right: 18px; }}
  header {{ padding-top: 36px; padding-bottom: 24px; }}
  main {{ padding-top: 24px; padding-bottom: 48px; }}
  footer {{ padding-top: 16px; padding-bottom: 32px; flex-wrap: wrap; gap: 6px; }}
  h1 {{ font-size: 2.5rem; }}
  .header-row {{ flex-direction: column; align-items: flex-start; gap: 6px; margin-bottom: 18px; }}
  .classification {{ white-space: normal; word-break: break-word; }}
  .tldr-card {{ padding: 16px 14px; }}
  .tldr-card li {{ font-size: .95rem; }}
  .report h2 {{ margin-top: 32px; }}
  .network-tag {{ font-size: .52rem; }}
}}
</style>
</head>
<body>
<div class="top-bar"></div>
<header>
  <div class="header-row">
    <span class="classification">Internal &middot; Network Intelligence</span>
    <a href="index.html" class="nav-link">Archive &rarr;</a>
  </div>
  <div>
    <span class="network-tag">{network_name}</span>
    <h1>DNS Briefing</h1>
    <time>{date_display}</time>
  </div>
</header>
<main>
  <article class="report">{content_html}</article>
</main>
<footer>
  <span>Generated {generated_at} UTC</span>
  <span class="sep">&middot;</span>
  <span>Next: 08:00 MST</span>
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
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,600;1,400&family=Crimson+Pro:wght@300;400&family=Fira+Mono:wght@400&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #06070d; --surface: #0a0c15; --border: #181e30; --border-hi: #252d45;
  --text: #aab4c8; --text-bright: #d4dcea; --text-muted: #3e4a62;
  --accent: #a3e635; --accent-dim: rgba(163,230,53,.1); --accent-bd: rgba(163,230,53,.25);
  --ff-display: 'Cormorant Garamond', Georgia, serif;
  --ff-body: 'Crimson Pro', Georgia, serif;
  --ff-mono: 'Fira Mono', 'Courier New', monospace;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ font-size: 18px; }}
body {{
  background: var(--bg); color: var(--text);
  font-family: var(--ff-body); font-weight: 300;
  min-height: 100vh; overflow-x: hidden;
}}
body::after {{
  content: '';
  position: fixed; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='300'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.035'/%3E%3C/svg%3E");
  pointer-events: none; z-index: 1000; opacity: .6;
}}
.top-bar {{
  position: fixed; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, var(--accent) 0%, rgba(163,230,53,.35) 55%, transparent 100%);
  z-index: 999;
}}
.wrap {{ max-width: 720px; margin: 0 auto; padding: 0 32px; }}
header {{ padding: 52px 0 36px; border-bottom: 1px solid var(--border); }}
.classification {{
  font-family: var(--ff-mono); font-size: .6rem; letter-spacing: .24em;
  text-transform: uppercase; color: var(--text-muted); margin-bottom: 28px; display: block;
}}
h1 {{
  font-family: var(--ff-display); font-size: clamp(2.8rem, 6vw, 4.5rem);
  font-weight: 600; color: var(--text-bright); letter-spacing: -.015em; line-height: 1;
  margin-bottom: 10px;
}}
.subtitle {{
  font-family: var(--ff-display); font-style: italic; font-size: 1.05rem; color: var(--text-muted);
}}
.latest-btn {{
  display: inline-block; margin-top: 28px;
  font-family: var(--ff-mono); font-size: .65rem; letter-spacing: .15em;
  text-transform: uppercase; color: var(--bg); background: var(--accent);
  padding: 10px 20px; text-decoration: none; transition: opacity .2s;
}}
.latest-btn:hover {{ opacity: .85; }}
main {{ padding: 44px 0 72px; }}
.section-label {{
  font-family: var(--ff-mono); font-size: .6rem; letter-spacing: .2em;
  text-transform: uppercase; color: var(--text-muted); margin-bottom: 20px;
  padding-bottom: 12px; border-bottom: 1px solid var(--border); position: relative;
}}
.section-label::after {{
  content: ''; position: absolute; bottom: -1px; left: 0;
  width: 28px; height: 1px; background: var(--accent);
}}
.report-list {{ list-style: none; }}
.report-list li {{
  border-bottom: 1px solid var(--border);
}}
.report-list a {{
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 0; color: var(--text); text-decoration: none;
  font-family: var(--ff-mono); font-size: .72rem; letter-spacing: .06em;
  transition: color .15s;
}}
.report-list a:hover {{ color: var(--accent); }}
.report-list .arrow {{ color: var(--text-muted); font-size: .65rem; }}
footer {{
  padding: 20px 0 48px; border-top: 1px solid var(--border);
  font-family: var(--ff-mono); font-size: .6rem; letter-spacing: .1em; color: var(--text-muted);
}}
@media (max-width: 600px) {{
  html {{ font-size: 16px; }}
  .wrap {{ padding: 0 20px; }}
  header {{ padding: 36px 0 24px; }}
  h1 {{ font-size: 2.6rem; }}
  .latest-btn {{ display: block; text-align: center; margin-top: 20px; }}
  .report-list a {{ font-size: .68rem; }}
}}
</style>
</head>
<body>
<div class="top-bar"></div>
<header class="wrap">
  <span class="classification">Internal &middot; Network Intelligence</span>
  <h1>DNS Briefing</h1>
  <p class="subtitle">{network_name}</p>
  <a href="latest.html" class="latest-btn">Latest Report &rarr;</a>
</header>
<main class="wrap">
  <p class="section-label" style="margin-top:0">Archive</p>
  <ul class="report-list">
{report_items}
  </ul>
</main>
<footer class="wrap">Daily briefings &middot; Runs 08:00 MST</footer>
</body>
</html>"""


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

    def write(self, report: str, report_date: date) -> None:
        self._write_local(report, report_date)
        html = self._render_html(report, report_date)
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

    def _render_html(self, report: str, report_date: date) -> str:
        content_html = _md.markdown(report, extensions=["extra", "nl2br"])
        date_display = report_date.strftime("%A, %B %-d, %Y")
        generated_at = datetime.now(tz=UTC).strftime("%H:%M")
        return _REPORT_TEMPLATE.format(
            date_display=date_display,
            network_name=self._network_name,
            generated_at=generated_at,
            content_html=content_html,
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
            f'<span class="arrow">&#8599;</span></a></li>'
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
