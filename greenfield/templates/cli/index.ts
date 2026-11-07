#!/usr/bin/env node
/**
 * CLI entry point (wired as the package `bin` in package.json).
 *
 * Argument parsing and process.env reads belong here — never in src/core/
 * (see AGENTS.md §2). Core behaviour must stay callable without a process.
 */

const USAGE = `Usage: <package-name> [options]

Options:
  -h, --help     Show this help and exit.
`;

function main(argv: readonly string[]): number {
  if (argv.length === 0 || argv.includes('--help') || argv.includes('-h')) {
    process.stdout.write(USAGE);
    return 0;
  }
  process.stderr.write(`Unknown argument: ${argv.join(' ')}\n${USAGE}`);
  return 1;
}

process.exitCode = main(process.argv.slice(2));
