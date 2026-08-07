import { readFileSync, readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import ts from "typescript";
import { describe, expect, it } from "vitest";

const repoRoot = resolve(process.cwd(), "../..");

function collectTypeScriptFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) return collectTypeScriptFiles(path);
    return /\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

describe("platform client source packages", () => {
  it("transpiles every native mobile TypeScript source file", () => {
    const files = collectTypeScriptFiles(join(repoRoot, "mobile", "src"));
    expect(files.length).toBeGreaterThanOrEqual(6);
    for (const file of files) {
      const result = ts.transpileModule(readFileSync(file, "utf8"), {
        fileName: file,
        reportDiagnostics: true,
        compilerOptions: {
          jsx: ts.JsxEmit.ReactJSX,
          module: ts.ModuleKind.ESNext,
          target: ts.ScriptTarget.ES2022,
        },
      });
      const diagnostics = result.diagnostics ?? [];
      expect(diagnostics, `${file}: ${diagnostics.map((item) => ts.flattenDiagnosticMessageText(item.messageText, "\n")).join("\n")}`).toEqual([]);
    }
  });

  it("keeps the browser extension permission-minimal and syntactically valid", () => {
    const extensionRoot = join(repoRoot, "apps", "extension");
    const manifest = JSON.parse(readFileSync(join(extensionRoot, "manifest.json"), "utf8")) as {
      manifest_version: number;
      permissions: string[];
    };
    expect(manifest.manifest_version).toBe(3);
    expect(manifest.permissions.sort()).toEqual(["activeTab", "storage"]);

    const popup = readFileSync(join(extensionRoot, "popup.js"), "utf8");
    expect(() => new Function(popup)).not.toThrow();
    expect(popup).not.toMatch(/fetch\s*\(/);
  });
});
