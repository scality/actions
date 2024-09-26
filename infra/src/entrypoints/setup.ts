/**
 * Entrypoint for installing and configuring dependencies for cloud infrastructure
 * provisioning.
 *
 * Installs Pulumi, configures it to use a local state backend, and sets up the
 * selected cloud provider, with authentication and optional tooling.
 *
 * Inputs:
 *   - cloud (string)      The cloud provider to use
 *   - cloud-auth (string) A JSON containing authentication details for the chosen
 *                         cloud provider
 *   - state-path (string) The path to the local Pulumi state to use or create
 *
 * @packageDocumentation
 */
import * as path from "node:path";
import * as os from "node:os";

import * as core from "@actions/core";
import * as exec from "@actions/exec";
import * as io from "@actions/io";
import * as tc from "@actions/tool-cache";

import { init } from "../../pulumi";
import { CloudProvider } from "../../pulumi/lib";
import { Stack } from "@pulumi/pulumi/automation";

/**
 * A simplified version of `downloadCli` defined in
 * https://github.com/pulumi/actions/blob/master/src/libs/pulumi-cli.ts
 *
 * @param version The version of Pulumi to download
 */
export async function downloadCli(version: string) {
  const installDir = path.join(os.homedir(), ".pulumi");
  const binDir = path.join(installDir, "bin");
  await io.rmRF(binDir);
  const dowloaded = await tc.downloadTool(
    `https://get.pulumi.com/releases/sdk/pulumi-v${version}-linux-x64.tar.gz`
  );
  await io.mkdirP(installDir);
  await tc.extractTar(dowloaded, installDir);
  await io.mv(path.join(installDir, "pulumi"), binDir);
  const cached = await tc.cacheDir(binDir, "pulumi", version);
  core.addPath(cached);
}

export async function main() {
  const cloud = core.getInput("cloud", { required: true }) as CloudProvider;
  const sourceDir = core.getInput("source-dir", { required: true });
  const stackName = core.getInput("stack-name", { required: true });
  const pulumiVersion = core.getInput("pulumi-version") || "3.49.0";

  // Retrieve Pulumi CLI (todo: add pulumi-version input, default should come
  // from the action itself, to match the Pulumi programs)
  await downloadCli(pulumiVersion);
  core.exportVariable("PULUMI_CONFIG_PASSPHRASE", "password");
  const loginRes = await exec.getExecOutput("pulumi", ["login", "--local"]);
  console.log(loginRes);

  // Load the local state with Pulumi, and export the important env vars
  const stack = await init("artesca", stackName, sourceDir);
  console.log(stack);

  await stack.setConfig("cloud", { value: cloud });
  await stack.setConfig("nodes-count", { value: "1" });
  console.log(stack);

  const previewResult = await stack.preview({ onOutput: console.log });
  console.log(previewResult);

  const upResult = await stack.up({ onOutput: console.log });
  console.log(upResult);
  // Validate the cloud provider configuration and export what is necessary

  // Install necessary additional tools (e.g. openstack CLI when using an
  // Openstack provider) - make sure to use the tools-cache approach

  // Set useful outputs
  core.setOutput("workdir", stack.workspace.workDir);
  core.setOutput("stack-prefix", upResult.outputs.prefix);
}

try {
  main();
} catch (error) {
  core.setFailed(error as Error);
}
