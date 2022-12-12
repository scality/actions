// --- Networks ---

interface NetworkProps {
  cidr?: string;
  subnets?: Input<ID[]>;
}

export class Network extends ComponentResource {
  public readonly network: Output<openstack.networking.Network>;
  public readonly subnets: Output<openstack.networking.Subnet[]>;

  public static readonly __pulumiType =
    "@scality-actions/infra:pulumi/lib/openstack:Network";

  /**
   * Get an existing Openstack network with the given name, ID, and optional extra
   * properties.
   *
   * @param name The unique network name
   * @param id The unique provider ID to lookup
   * @param props Any extra properties to filter
   * @param opts Optional settings to control the behaviour of this component
   */
  public static get(
    name: string,
    id: Input<ID>,
    props?: NetworkProps,
    opts?: ResourceOptions
  ) {
    return new Network(name, props, { ...opts, id });
  }

  /**
   * Create an Openstack network and optional subnet and other child resources.
   *
   * @param name The unique network name
   * @param opts Parameters for creating the network and optional subnet
   */
  constructor(name: string, props?: NetworkProps, opts?: ResourceOptions) {
    super(Network.__pulumiType, name, {}, opts);

    if (opts?.id) {
      this.network = openstack.networking.Network.get(
        name,
        opts?.id,
        { adminStateUp: true },
        { ...opts, parent: this }
      );
    } else {
      this.network = new openstack.networking.Network(
        name,
        { adminStateUp: true },
        { ...opts, parent: this }
      );
    }

    this.subnets = [];
    if (props?.subnets) {
      const foundSubnets = output(props.subnets).apply((subnets) =>
        subnets.map((subnetID) =>
          openstack.networking.getSubnet({ subnetId: subnetID })
        )
      );
      foundSubnets.apply((subnet) => {
        this.subnets.push(openstack.networking.Subnet.get(subnet));
      });
    }
    this.subnets = [];
    // TODO: create and/or find subnet(s)

    // Register outputs, constructor has completed
    for (let subnetID of this.network.subnets) this.registerOutputs();
  }
}

export function getNetwork(name: string): Network {
  const found = output(openstack.networking.getNetwork({ name }));
  if (!found) throw new Error(`Couldn't find Openstack network named "${name}"`);
  return Network.get(name, found.id, { subnets: found.subnets });
}
