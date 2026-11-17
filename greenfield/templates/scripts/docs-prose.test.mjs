// SPDX-License-Identifier: MIT-0
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, describe, it } from 'node:test';
import { fileURLToPath } from 'node:url';

import { checkText, collectMarkdownFiles, needsDiagram, summary } from './docs-prose.mjs';

const SCRIPT = fileURLToPath(new URL('./docs-prose.mjs', import.meta.url));

/** A sentence of `n` plain words, ending with a full stop. */
const sentence = (n) => `${Array.from({ length: n }, (_, i) => `word${i}`).join(' ')}.`;

const codes = (issues) => issues.map((i) => `${i.code}:${i.severity}`);

describe('checkText: PL001 sentence length', () => {
    it('accepts a sentence of 25 words', () => {
        assert.deepEqual(checkText('a.md', sentence(25)), []);
    });

    it('gives a notice for 26 words', () => {
        const issues = checkText('a.md', sentence(26));
        assert.deepEqual(codes(issues), ['PL001:notice']);
        assert.equal(issues[0].message, 'sentence has 26 words (limit 25)');
        assert.equal(issues[0].line, 1);
    });

    it('gives a warning for more than 40 words', () => {
        assert.deepEqual(codes(checkText('a.md', sentence(41))), ['PL001:warning']);
        assert.deepEqual(codes(checkText('a.md', sentence(40))), ['PL001:notice']);
    });

    it('gives a warning for a numbered step of more than 20 words', () => {
        const issues = checkText('a.md', `1. ${sentence(21)}\n`);
        assert.deepEqual(codes(issues), ['PL001:warning']);
        assert.equal(issues[0].message, 'step has 21 words (limit 20)');
        assert.deepEqual(checkText('a.md', `1. ${sentence(20)}\n`), []);
    });

    it('holds a bullet to the sentence limit, not the step limit', () => {
        assert.deepEqual(checkText('a.md', `- ${sentence(21)}\n`), []);
    });

    it('counts a code span as one word and a link as its text', () => {
        // 23 plain words, a code span of 8 words and a link: 25 words, at the limit. Counting the words
        // inside the code span, or the URL parts after the spaces, takes the sentence over 25.
        const plain = Array.from({ length: 23 }, (_, i) => `word${i}`).join(' ');
        const markup = '`a b c d e f g h` [guide](https://example.com/a b c d e)';
        assert.deepEqual(checkText('a.md', `${plain} ${markup}.`), []);
        const issues = checkText('a.md', `${plain} more ${markup}.`);
        assert.deepEqual(codes(issues), ['PL001:notice']);
        assert.equal(issues[0].message, 'sentence has 26 words (limit 25)');
    });

    it('reports the line where the paragraph starts', () => {
        const issues = checkText('a.md', `# Title\n\n${sentence(26)}\n`);
        assert.equal(issues[0].line, 3);
    });
});

describe('checkText: PL002 vague words', () => {
    it('flags a vague word as a warning', () => {
        const issues = checkText('a.md', 'You can simply run the tests.\n');
        assert.deepEqual(codes(issues), ['PL002:warning']);
        assert.equal(issues[0].message, "vague word 'simply'");
    });

    it('flags a phrase and ignores a word that only contains one', () => {
        assert.deepEqual(codes(checkText('a.md', 'Use it in order to build.\n')), ['PL002:warning']);
        assert.deepEqual(checkText('a.md', 'The justice team met.\n'), []);
    });

    it('does not flag a vague word inside a code span', () => {
        assert.deepEqual(checkText('a.md', 'Run `just build` first.\n'), []);
    });
});

describe('checkText: skipped content', () => {
    it('skips fenced code', () => {
        const text = `\`\`\`\n${sentence(50)}\nsimply\n\`\`\`\n`;
        assert.deepEqual(checkText('a.md', text), []);
    });

    it('skips tables, headings and HTML comments', () => {
        const text = [
            `| simply | ${sentence(30)} |`,
            '|---|---|',
            `## Simply ${sentence(30)}`,
            `<!-- ${sentence(30)} simply -->`,
            '',
        ].join('\n');
        assert.deepEqual(checkText('a.md', text), []);
    });

    it('skips a region between the off and on markers, and reads on both sides', () => {
        const text = [
            'Obviously bad.',
            '',
            '<!-- prose-check off -->',
            '',
            'Simply bad, in order to show it.',
            '',
            '<!-- prose-check on -->',
            '',
            'Basically bad.',
            '',
        ].join('\n');
        const issues = checkText('a.md', text);
        assert.deepEqual(
            issues.map((i) => [i.line, i.message]),
            [
                [1, "vague word 'Obviously'"],
                [9, "vague word 'Basically'"],
            ],
        );
    });
});

describe('checkText: PL003 diagram', () => {
    const page = 'docs/explanation/how-it-works.md';

    it('warns on an explanation page without a Mermaid block', () => {
        const issues = checkText(page, 'It works.\n');
        assert.deepEqual(codes(issues), ['PL003:warning']);
        assert.equal(issues[0].line, 1);
    });

    it('accepts an explanation page with a Mermaid block', () => {
        const text = 'It works.\n\n```mermaid\nflowchart TD\n  A --> B\n```\n';
        assert.deepEqual(checkText(page, text), []);
    });

    it('does not ask for a diagram on other pages or on an index page', () => {
        assert.equal(needsDiagram('docs/how-to/deploy.md'), false);
        assert.equal(needsDiagram('docs/explanation/README.md'), false);
        assert.equal(needsDiagram('docs/tutorials/first.md'), true);
        assert.equal(needsDiagram('docs\\tutorials\\first.md'), true);
    });
});

describe('summary', () => {
    it('writes the summary line with plurals', () => {
        assert.equal(
            summary({ warning: 2, notice: 1 }, 3),
            'Summary: 3 issues in 3 files (2 warnings, 1 notice)',
        );
        assert.equal(summary({ warning: 0, notice: 0 }, 1), 'Summary: 0 issues in 1 file (0 warnings, 0 notices)');
    });
});

describe('command line', () => {
    /** @type {string} */
    let dir;

    before(() => {
        dir = fs.mkdtempSync(path.join(os.tmpdir(), 'docs-prose-'));
        fs.writeFileSync(path.join(dir, 'bad.md'), `You can simply do it.\n\n${sentence(30)}\n`);
        fs.writeFileSync(path.join(dir, 'good.md'), 'Run the tests.\n');
        fs.mkdirSync(path.join(dir, 'node_modules', 'pkg'), { recursive: true });
        fs.writeFileSync(path.join(dir, 'node_modules', 'pkg', 'skip.md'), 'Simply skipped.\n');
        fs.mkdirSync(path.join(dir, 'docs'));
        fs.writeFileSync(path.join(dir, 'docs', 'a.md'), 'Run the tests.\n');
    });

    after(() => {
        fs.rmSync(dir, { recursive: true, force: true });
    });

    const run = (args) => spawnSync(process.execPath, [SCRIPT, ...args], { cwd: dir, encoding: 'utf8' });

    it('exits 0 with findings and prints lines and a summary', () => {
        const result = run(['bad.md', 'good.md']);
        assert.equal(result.status, 0);
        const lines = result.stdout.trimEnd().split('\n');
        assert.deepEqual(lines, [
            "bad.md:1: PL002 warning: vague word 'simply'",
            'bad.md:3: PL001 notice: sentence has 30 words (limit 25)',
            'Summary: 2 issues in 2 files (1 warning, 1 notice)',
        ]);
    });

    it('hides notices with --min-severity warning', () => {
        const result = run(['--min-severity', 'warning', 'bad.md']);
        assert.equal(result.status, 0);
        assert.deepEqual(result.stdout.trimEnd().split('\n'), [
            "bad.md:1: PL002 warning: vague word 'simply'",
            'Summary: 1 issue in 1 file (1 warning, 0 notices)',
        ]);
    });

    it('reads every Markdown file except node_modules when given none', () => {
        const result = run([]);
        assert.equal(result.status, 0);
        assert.doesNotMatch(result.stdout, /node_modules/);
        assert.match(result.stdout, /^Summary: 2 issues in 3 files /m);
        assert.deepEqual(collectMarkdownFiles(dir), ['bad.md', 'docs/a.md', 'good.md']);
    });

    it('reports a file it cannot read as a warning and still exits 0', () => {
        const result = run(['missing.md', 'good.md']);
        assert.equal(result.status, 0);
        assert.match(result.stdout, /^missing\.md:1: READ warning: cannot read file: .*ENOENT/m);
        assert.match(result.stdout, /^Summary: 1 issue in 2 files \(1 warning, 0 notices\)$/m);
    });

    it('exits 0 on a bad option', () => {
        const result = run(['--nope', 'good.md']);
        assert.equal(result.status, 0);
        assert.match(result.stdout, /^Summary: 0 issues in 1 file /m);
    });
});
