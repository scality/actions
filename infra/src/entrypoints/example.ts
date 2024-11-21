/**
 * An example entrypoint.
 *
 * @packageDocumentation
 */

import * as core from "@actions/core";

/**
 * An example main routine, which extracts a required 'in' input from the
 * action execution context, and sets an 'out' output.
 */
function main() {
  const input = core.getInput("in", { required: true });
  console.log(`Got input: ${input}`);
  core.setOutput("out", "example-output");
}

main();
