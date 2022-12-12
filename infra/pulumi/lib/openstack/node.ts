// --- Nodes ---

export interface NodeProps {
  image: string;
  flavor: string;
  accessNetwork: Input<{ name: string; id: ID }>;
  extraNetworks?: Input<{ name: string; id: ID }[]>;
  secGroups?: Input<{ name: string; id: ID }[]>;
}

export class Node extends ComponentResource {
  instance: openstack.compute.Instance;

  public static readonly __pulumiType =
    "@scality-actions/infra:pulumi/lib/openstack:Node";

  /**
   * Create an Openstack instance and all its resource attachments as child resources.
   *
   * @param name The unique instance name
   * @param props Parameters for creating the instance
   * @param opts Optional settings to control the behaviour of this component
   */
  constructor(name: string, props?: NodeProps, opts?: ResourceOptions) {
    super(Node.__pulumiType, name, props, opts);

    if (opts?.id) {
      this.instance = openstack.compute.Instance.get(name, opts?.id);
    } else {
      // TODO: add basic creation args (include access network)
      this.instance = new openstack.compute.Instance(name, {}, opts);
    }

    // TODO: add network ports, volume attachments, and security groups

    // Register outputs, constructor has completed
    this.registerOutputs();
  }
}
