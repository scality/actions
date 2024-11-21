/**
 * Pulumi project for spawning cloud infrastructure to deploy RING.
 *
 * @packageDocumentation
 */

import * as pulumi from "@pulumi/pulumi";

export async function main() {
  let config = new pulumi.Config();
  let cloud = config.require("cloud");
  console.log(`This stack will use the "${cloud}" provider.`);
}
