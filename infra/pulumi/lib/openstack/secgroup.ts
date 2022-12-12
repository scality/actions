// --- Security groups ---

export interface SecGroupRule {
  remote: { cidr: string } | { secGroup: string };
  protocol?: "TCP" | "UDP" | "ICMP";
  ports?: { from?: number[]; to?: number[] };
}

export interface SecGroupProps {
  ingress?: SecGroupRule[];
  egress?: SecGroupRule[];
}

export class SecGroup extends ComponentResource {
  secGroup: openstack.networking.SecGroup;

  public static readonly __pulumiType =
    "@scality-actions/infra:pulumi/lib/openstack:SecGroup";

  /**
   * Create an Openstack security group and all its rules as child resources.
   *
   * @param name The unique security group name
   * @param props Parameters for creating the security group rules
   * @param opts Optional settings to control the behaviour of this component
   */
  constructor(name: string, props?: SecGroupProps, opts?: ResourceOptions) {
    super(SecGroup.__pulumiType, name, props, opts);

    if (opts?.id) {
      this.secGroup = openstack.networking.SecGroup.get(name, opts?.id);
    } else {
      // TODO: add basic creation args
      this.secGroup = new openstack.networking.SecGroup(name, {}, opts);
    }

    // TODO: create/check rules

    // Register outputs, constructor has completed
    this.registerOutputs();
  }
}
