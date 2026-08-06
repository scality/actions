/**
 * Entrypoints for provisioning cloud infrastructure with Pulumi Automation API.
 *
 * These entrypoints replicate some Pulumi CLI commands, and add state management
 * helpers for use with Scality Artifacts.
 *
 * @packageDocumentation
 */
import * as os from "node:os";
import * as path from "node:path";
import * as fs from "node:fs/promises";

import { LocalWorkspace } from "@pulumi/pulumi/automation";

import { main as artescaProgram } from "./artesca";
import { main as ringProgram } from "./ring";

const programs = { artesca: artescaProgram, ring: ringProgram };
export type Product = keyof typeof programs;

export async function init(
  product: Product,
  stackName: string,
  sourceDir?: string,
  workDir?: string
) {
  // Create (or validate) the workDir
  if (workDir === undefined)
    workDir = await fs.mkdtemp(path.join(os.tmpdir(), "scality-pulumi-"));
  await fs.mkdir(workDir, { recursive: true });

  // Copy project (and optional stack) settings from known paths
  if (sourceDir === undefined) sourceDir = __dirname;
  await fs.cp(path.join(sourceDir, product), workDir, { recursive: true });

  // (maybe, add configuration hooks here as well, but can be done with the resulting
  // workspace, so no rush)

  // Return a local workspace
  return await LocalWorkspace.createOrSelectStack(
    { stackName, projectName: `scality-infra-${product}`, program: programs[product] },
    { workDir }
  );
}
