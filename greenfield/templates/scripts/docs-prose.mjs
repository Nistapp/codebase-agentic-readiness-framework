#!/usr/bin/env node
// SPDX-License-Identifier: MIT-0
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

/**
 * Warn-only prose check for Markdown. It applies three plain-language rules and prints each finding
 * as `path:line: CODE severity: message`. It never fails on what it finds: the exit code is 0.
 *
 *   node scripts/docs-prose.mjs [--min-severity notice|warning] [--quiet] [FILE...]
 *
 * With no file it reads every `.md` file under the working directory, except `node_modules/`,
 * `dist/`, `coverage/` and `.git/`.
 *
 * Rules:
 *   PL001  a sentence has more than 25 words (a notice), more than 40 words (a warning), or a
 *          numbered step has more than 20 words (a warning).
 *   PL002  a vague or padded word from VAGUE (a warning).
 *   PL003  an explanation or tutorial page has no Mermaid block (a warning).
 *
 * Only prose is read: paragraphs, list items and blockquotes. Fenced code, tables, headings, HTML
 * comments and inline code spans are skipped. A region between `<!-- prose-check off -->` and
 * `<!-- prose-check on -->` is skipped, for a deliberate bad example. A file that cannot be read is
 * reported as a warning line (code READ).
 * The last line is `Summary: N issues in M files (W warnings, K notices)`.
 */

export const MAX_WORDS = 25;
export const MAX_WORDS_STEP = 20;
// A sentence this long is hard to follow even for a patient reader, so it is a warning, not a
// notice.
export const MAX_WORDS_WARNING = 40;

export const WARNING = 'warning';
export const NOTICE = 'notice';
export const SEVERITIES = [NOTICE, WARNING];

export const VAGUE = [
  'simply',
  'just',
  'obviously',
  'clearly',
  'basically',
  'easily',
  'utilize',
  'utilise',
  'leverage',
  'in order to',
  'and/or',
  'etc',
];

// Directories whose pages must carry a diagram. Index pages (README.md) are exempt.
export const DIAGRAM_DIRS = ['docs/explanation/', 'docs/tutorials/'];

export const SKIPPED_DIRS = ['node_modules', 'dist', 'coverage', '.git'];

const escapeRegExp = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const VAGUE_RE = new RegExp(
  `(?<![\\p{L}\\p{N}_/-])(${VAGUE.map(escapeRegExp).join('|')})(?![\\p{L}\\p{N}_/-])`,
  'giu',
);

const FENCE = /^\s*(```|~~~)/;
const MERMAID = /^\s*(```|~~~)\s*mermaid\b/;
const OFF = '<!-- prose-check off -->';
const ON = '<!-- prose-check on -->';
const LIST_ITEM = /^\s*(?:[-*+]|(\d+)[.)])\s+/;
const CODE_SPAN = /(`+)(.+?)\1/g;
const IMAGE = /!\[[^\]]*\]\([^)]*\)/g;
const LINK = /\[([^\]]*)\]\([^)]*\)/g;
const REF_LINK = /\[([^\]]*)\]\[[^\]]*\]/g;
const URL_RE = /<?https?:\/\/\S+>?/g;
const HTML_TAG = /<\/?[a-zA-Z][^>]*>/g;
const ALERT = /^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*/;
const SENTENCE_END = /(?<=[.!?])["')\]]*\s+(?=[A-Z0-9`(["*_])/;
const WORD = /[A-Za-z0-9]/;
const RULE_LINE = /^[-*_=\s]{3,}$/;

/**
 * @typedef {{ path: string, line: number, code: string, severity: string, message: string }} Issue
 */

/**
 * Format one issue as `path:line: CODE severity: message`.
 *
 * @param {Issue} issue
 * @returns {string}
 */
export function formatIssue(issue) {
  return `${issue.path}:${issue.line}: ${issue.code} ${issue.severity}: ${issue.message}`;
}

/**
 * True for an explanation page or a tutorial (not an index `README.md`).
 *
 * @param {string} filePath
 * @returns {boolean}
 */
export function needsDiagram(filePath) {
  const posix = filePath.split(path.sep).join('/').replaceAll('\\', '/');
  if (posix.split('/').pop() === 'README.md') return false;
  return DIAGRAM_DIRS.some((dir) => `/${posix}`.includes(`/${dir}`));
}

/** Prose without markup: a code span or a URL counts as one word, a link as its text. */
function clean(text) {
  return text
    .replace(CODE_SPAN, ' CODE ')
    .replace(IMAGE, ' ')
    .replace(LINK, '$1')
    .replace(REF_LINK, '$1')
    .replace(URL_RE, ' URL ')
    .replace(HTML_TAG, ' ')
    .replaceAll('**', '')
    .replaceAll('__', '');
}

/**
 * Prose blocks (paragraphs, list items, blockquote paragraphs) and whether a Mermaid block exists.
 *
 * @param {string[]} lines
 * @returns {{ blocks: { line: number, text: string, step: boolean }[], hasMermaid: boolean }}
 */
function readBlocks(lines) {
  const blocks = [];
  let hasMermaid = false;
  let inFence = false;
  let inComment = false;
  let off = false;
  let current = null;

  const close = () => {
    if (current !== null && current.text.trim() !== '') blocks.push(current);
    current = null;
  };

  for (let index = 0; index < lines.length; index++) {
    const number = index + 1;
    const line = lines[index];
    let stripped = line.trim();
    if (FENCE.test(line)) {
      if (!inFence && MERMAID.test(line)) hasMermaid = true;
      inFence = !inFence;
      close();
      continue;
    }
    if (inFence) continue;
    if (stripped === OFF) {
      off = true;
      close();
      continue;
    }
    if (stripped === ON) {
      off = false;
      continue;
    }
    if (off) continue;
    if (inComment) {
      if (line.includes('-->')) inComment = false;
      continue;
    }
    if (stripped.startsWith('<!--')) {
      if (!stripped.includes('-->')) inComment = true;
      close();
      continue;
    }
    let quote = false;
    while (stripped.startsWith('>')) {
      quote = true;
      stripped = stripped.slice(1).trim();
    }
    if (quote) stripped = stripped.replace(ALERT, '');
    if (
      stripped === '' ||
      stripped.startsWith('#') ||
      stripped.startsWith('|') ||
      RULE_LINE.test(stripped)
    ) {
      close();
      continue;
    }
    const item = LIST_ITEM.exec(stripped);
    if (item) {
      close();
      current = { line: number, text: stripped.slice(item[0].length), step: item[1] !== undefined };
      continue;
    }
    if (current === null) {
      current = { line: number, text: stripped, step: false };
    } else {
      current.text += ` ${stripped}`;
    }
  }
  close();
  return { blocks, hasMermaid };
}

function sentences(text) {
  return text.split(SENTENCE_END).filter((s) => s.trim() !== '');
}

function countWords(sentence) {
  return sentence.split(/\s+/).filter((token) => WORD.test(token)).length;
}

/**
 * All issues in one file's text.
 *
 * @param {string} filePath
 * @param {string} content
 * @returns {Issue[]}
 */
export function checkText(filePath, content) {
  /** @type {Issue[]} */
  const issues = [];
  const { blocks, hasMermaid } = readBlocks(content.split(/\r\n|\r|\n/));
  for (const block of blocks) {
    const prose = clean(block.text);
    const limit = block.step ? MAX_WORDS_STEP : MAX_WORDS;
    for (const sentence of sentences(prose)) {
      const words = countWords(sentence);
      if (words > limit) {
        const kind = block.step ? 'step' : 'sentence';
        const severity = block.step || words > MAX_WORDS_WARNING ? WARNING : NOTICE;
        issues.push({
          path: filePath,
          line: block.line,
          code: 'PL001',
          severity,
          message: `${kind} has ${words} words (limit ${limit})`,
        });
      }
    }
    for (const match of prose.matchAll(VAGUE_RE)) {
      issues.push({
        path: filePath,
        line: block.line,
        code: 'PL002',
        severity: WARNING,
        message: `vague word '${match[1]}'`,
      });
    }
  }
  if (needsDiagram(filePath) && !hasMermaid) {
    issues.push({
      path: filePath,
      line: 1,
      code: 'PL003',
      severity: WARNING,
      message: 'explanation or tutorial page without a Mermaid diagram',
    });
  }
  return issues;
}

/**
 * Every `.md` file under `root`, as sorted POSIX paths relative to `root`. It skips `SKIPPED_DIRS`.
 *
 * @param {string} root
 * @returns {string[]}
 */
export function collectMarkdownFiles(root) {
  const found = [];
  const walk = (relative) => {
    let entries;
    try {
      entries = readdirSync(path.join(root, relative), { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      const child = relative === '' ? entry.name : `${relative}/${entry.name}`;
      if (entry.isDirectory()) {
        if (!SKIPPED_DIRS.includes(entry.name)) walk(child);
      } else if (entry.isFile() && entry.name.endsWith('.md')) {
        found.push(child);
      }
    }
  };
  walk('');
  return found.sort();
}

const plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

/**
 * `Summary: N issues in M files (W warnings, K notices)`.
 *
 * @param {{ warning: number, notice: number }} counts
 * @param {number} files
 * @returns {string}
 */
export function summary(counts, files) {
  const total = counts.warning + counts.notice;
  const detail = `${plural(counts.warning, 'warning')}, ${plural(counts.notice, 'notice')}`;
  return `Summary: ${plural(total, 'issue')} in ${plural(files, 'file')} (${detail})`;
}

function errorMessage(err) {
  return err instanceof Error ? err.message : String(err);
}

/**
 * Split the arguments into options and files. A bad option is reported on stderr and ignored: the
 * check never fails.
 *
 * @param {string[]} argv
 */
function parseArgs(argv) {
  const files = [];
  let quiet = false;
  let minSeverity = NOTICE;
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--quiet' || arg === '-q') {
      quiet = true;
    } else if (arg === '--min-severity' || arg.startsWith('--min-severity=')) {
      const value = arg.includes('=') ? arg.slice(arg.indexOf('=') + 1) : argv[++i];
      if (SEVERITIES.includes(value)) {
        minSeverity = value;
      } else {
        console.error(`docs-prose: ignoring bad --min-severity '${value}' (use notice or warning)`);
      }
    } else if (arg.startsWith('--')) {
      console.error(`docs-prose: ignoring unknown option '${arg}'`);
    } else {
      files.push(arg);
    }
  }
  return { files, quiet, minSeverity };
}

/**
 * Entry point. It prints the findings and the summary, and returns 0 whatever it finds.
 *
 * @param {string[]} [argv]
 * @param {string} [cwd]
 * @returns {number}
 */
export function main(argv = process.argv.slice(2), cwd = process.cwd()) {
  const { files: given, quiet, minSeverity } = parseArgs(argv);
  const files = given.length > 0 ? given : collectMarkdownFiles(cwd);
  const shown = SEVERITIES.slice(SEVERITIES.indexOf(minSeverity));
  const counts = { warning: 0, notice: 0 };
  for (const file of files) {
    const display = file.split(path.sep).join('/');
    let issues;
    try {
      const content = readFileSync(path.resolve(cwd, file), 'utf8');
      issues = checkText(display, content);
    } catch (err) {
      issues = [
        {
          path: display,
          line: 1,
          code: 'READ',
          severity: WARNING,
          message: `cannot read file: ${errorMessage(err)}`,
        },
      ];
    }
    for (const issue of issues.filter((i) => shown.includes(i.severity))) {
      counts[issue.severity] += 1;
      if (!quiet) console.log(formatIssue(issue));
    }
  }
  console.log(summary(counts, files.length));
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    process.exitCode = main();
  } catch (err) {
    console.error(`docs-prose: ${errorMessage(err)}`);
    process.exitCode = 0;
  }
}
