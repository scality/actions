/**
 * Pulumi project for spawning cloud infrastructure to deploy ARTESCA.
 *
 * @packageDocumentation
 */

import * as pulumi from "@pulumi/pulumi";
import * as random from "@pulumi/random";

export async function main() {
  const config = new pulumi.Config();
  const cloud = config.require("cloud");
  const nodesCount = config.requireNumber("nodes-count");
  const stack = pulumi.getStack();
  const project = pulumi.getProject();

  const randomID = new random.RandomId("random-stack-id", {
    byteLength: 10,  // 10 bytes to get 5 characters in hex
    keepers: { stackName: stack },
  });

  const prefix = pulumi.interpolate`${project}-${randomID.hex}`;
  console.log(
    `This stack (${stack}, from project ${project}) will create ${nodesCount} nodes ` +
      `with the "${cloud}" provider.`
  );

  // attempt getting outputs, can't export from a function
  return { prefix };
}
