// src/core/interfaces.ts
// ============================================================================
// DI Port Interfaces — Single Source of Truth
// ============================================================================
// All infrastructure dependencies are defined here as interfaces.
// src/core/ must NEVER import from src/infrastructure/ or src/cli/.
// Implementations live in src/infrastructure/ and are wired in src/cli/.
// ============================================================================

export interface ILogger {
  info(msg: string, context?: Record<string, unknown>): void;
  warn(msg: string, context?: Record<string, unknown>): void;
  error(msg: string, context?: Record<string, unknown>): void;
  debug(msg: string, context?: Record<string, unknown>): void;
  child(bindings: Record<string, unknown>): ILogger;
}

export interface IFileSystem {
  readFile(path: string): Promise<string>;
  writeFile(path: string, content: string): Promise<void>;
  exists(path: string): Promise<boolean>;
  mkdir(path: string): Promise<void>;
  readDir(path: string): Promise<string[]>;
  unlink(path: string): Promise<void>;
}

// Add more interfaces as the project evolves:
// IGitService, ICommandRunner, IStateStore, IAgentRunner, etc.
