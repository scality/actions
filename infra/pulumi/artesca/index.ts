/**
 * Pulumi project for spawning cloud infrastructure to deploy ARTESCA.
 *
 * @packageDocumentation
 */

import * as pulumi from "@pulumi/pulumi";
import { all } from "@pulumi/pulumi";
import * as random from "@pulumi/random";
import { Product } from "..";
import { CloudEnv, CloudEnvProps, CloudProvider, getNetwork, Network, SecGroup } from "../lib";

export const product: Product = "artesca";

export async function main() {
  const config = new pulumi.Config();
  const cloud = config.require("cloud") as CloudProvider;
  const nodesCount = config.requireNumber("nodes-count");
  const stack = pulumi.getStack();
  const project = pulumi.getProject();

  const randomID = new random.RandomId("random-stack-id", {
    byteLength: 3, // result in hex is twice as long, for some reason
    keepers: { stackName: stack },
  });

  const prefix = pulumi.interpolate`${product}-${randomID.hex}`;
  console.log(
    `This stack (${stack}, from project ${project}) will create ${nodesCount} nodes ` +
      `with the "${cloud}" provider.`
  );

  const accessNet = getNetwork(`${prefix}-access-network`, cloud);
  const controlNet = new Network(`${prefix}-control-plane-network`, {
    cidr: "192.168.1.0/24", cloud
  });
  const workloadNet = new Network(`${prefix}-workload-plane-network`, {
    cidr: "192.168.12.0/24", cloud
  });

  const ingressSecGroup = new SecGroup()
  const secGroups: CloudEnvProps["secGroups"] = [
    {
      name: "ingress",
      rules: {
        ingress: [
          { protocol: "TCP", ports: [22], allowedRemotes: { cidr: "0.0.0.0/0" } },
          { protocol: "ICMP", allowedRemotes: { cidr: "0.0.0.0/0" } },
          { allowedRemotes: { secGroup: "__self__" } },
        ],
      },
    },
    {
      name: "open-egress",
      rules: { egress: [{ allowedRemotes: { cidr: "0.0.0.0/0" } }] },
    },
    {
      name: "restricted-egress",
      rules: {
        egress: [
          { allowedRemotes: { secGroup: "__self__" } },
          { protocol: "UDP", ports: [53], allowedRemotes: { cidr: "0.0.0.0/0" } },
        ],
      },
    },
  ];

  const nodes: CloudEnvProps["nodes"] = [{ name: "bastion", networks: allNets }];
  for (let i = 0; i++; i < nodesCount) {
    nodes.push({ name: `node-${i + 1}`, networks: allNets });
  }

  const cloudEnv = new CloudEnv("cloud-env", {
    cloud,
    product,
    prefix,
    networks,
    nodes,
  });

  // attempt getting outputs, can't export from a function
  return { prefix, ips: cloudEnv.accessIPs };
}
