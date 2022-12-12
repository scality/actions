/**
 * Library of reusable Pulumi component resources with multi-cloud support.
 *
 * To do:
 *   - generic parent to hold all other resources and store shared variables
 *   - private network (with subnet(s), fixed IPs, security groups...)
 *   - node (VM with ports and volume attachments)
 *   - cluster (group of nodes with network(s), with shared identity)
 *
 * @packagedocumentation
 */

import * as pulumi from "@pulumi/pulumi";

import * as openstack from "./openstack";
import * as utils from "./utils";

const CLOUD_PROVIDERS = { openstack };
export type CloudProvider = keyof typeof CLOUD_PROVIDERS;
export const DEFAULT_CLOUD: CloudProvider = "openstack";

export interface CloudProviderAuthSettings {};

export interface CloudEnvProps {
  cloud: CloudProvider;
  product: "artesca" | "ring";
  prefix?: pulumi.Input<string>;
  networks: { name: string; exists?: boolean }[];
  nodes: { name: string; networks: string[] }[];
}

export class CloudEnv extends pulumi.ComponentResource {
  prefix: string;
  cloud: CloudProvider;
  networks: Network[];

  public static readonly __pulumiType = "@scality-actions/infra:pulumi/lib:CloudEnv";

  constructor(name: string, props?: CloudEnvProps, opts?: pulumi.ResourceOptions) {
    super(CloudEnv.__pulumiType, name, {}, opts);

    this.cloud = props?.cloud || DEFAULT_CLOUD;

    // Generate (or just store) a name prefix for all child resources
    this.prefix = CloudEnv.generatePrefix(name, props);

    // Build networks first (they should not depend on other resources)
    this.networks = (props?.networks || []).map((net) =>
      net.exists
        ? getNetwork(net.name, cloud)
        : new Network(
            this.generateName(net.name),
            { cloud: this.cloud },
            { ...opts, parent: this }
          )
    );

    this.registerOutputs();
  }

  public static generatePrefix(name: string, props?: CloudEnvProps): string {
    if (props === undefined) return `${name}-${utils.generateRandomString(5)}`;
    if (props.prefix !== undefined) return props.prefix;
    return `${props.product}-${utils.generateRandomString(5)}`;
  }

  public generateName(baseName: string): string {
    return `${this.prefix}-${baseName}`;
  }
}

export interface NetworkProps {
  id?: pulumi.Input<pulumi.ID>;
  cloud: CloudProvider;
}

export class Network extends pulumi.ComponentResource {
  network: openstack.Network;

  public static readonly __pulumiType = "@scality-actions/infra:pulumi/lib:Network";

  constructor(name: string, props?: NetworkProps, opts?: pulumi.ResourceOptions) {
    super(Network.__pulumiType, name, {}, opts);

    if (props === undefined) props = { cloud: "openstack" };
    switch (props.cloud) {
      case "openstack":
        this.network = new openstack.Network(name, { ...opts, parent: this });
        break;
    }

    this.registerOutputs();
  }

  public static get(
    name: string,
    id: pulumi.Input<pulumi.ID>,
    props?: NetworkProps,
    opts?: pulumi.ResourceOptions
  ) {
    if (props === undefined) props = { cloud: "openstack" };
    return new Network(name, { ...props, id }, opts);
  }
}

export function getNetwork(name: string, cloud: CloudProvider): pulumi.Output<{id: pulumi.ID}> {
  switch (cloud) {
    case "openstack":
      return pulumi.output(openstack.getNetwork(name))
  }
}

export interface NodeProps {
  id?: number;
}

export class Node extends pulumi.ComponentResource {
  public static readonly __pulumiType = "@scality-actions/infra:pulumi/lib:Node";

  constructor(name: string, props?: NodeProps, opts?: pulumi.ResourceOptions) {
    super(Node.__pulumiType, name, {}, opts);
  }
}
