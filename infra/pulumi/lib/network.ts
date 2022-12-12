/**
 * Cloud-agnostic definition of a "network" component (including subnets).
 *
 * @packageDocumentation
 */

import * as pulumi from "@pulumi/pulumi";

import { CloudProvider } from "./cloud";

/**
 * Properties for creating a Network component.
 *
 * Describe a network and its subnet(s).
 */
export interface NetworkProps {
  id?: pulumi.Input<pulumi.ID>;
  subnets?: pulumi.Input<string[]>;
}

/**
 * Manage a network and its subnets in any supported cloud provider.
 */
export class Network extends pulumi.ComponentResource {
  /** The main network resource represented by this component */
  public readonly network: openstack.networking.Network;

  /** All subnets in this network */
  public readonly subnets: openstack.networking.Subnet[];

  /** @internal */
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

export function getNetwork(
  name: string,
  cloud: CloudProvider
): pulumi.Output<{ id: pulumi.ID }> {
  switch (cloud) {
    case "openstack":
      return pulumi.output(openstack.getNetwork(name));
  }
}
