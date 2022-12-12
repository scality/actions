# `@scality-actions/infra/pulumi/lib`

Library of reusable Pulumi component resources with multi-cloud support.

Each cloud provider will have to implement the following Pulumi components:

- [ ] `network` module

  - [ ] `network.Network` (extends `pulumi.ComponentResource`)

    - [ ] `constructor` all new
    - [ ] `constructor` all existing
    - [ ] `createPort(subnet)`
    - [ ] `createSubnet(args)`

  - [ ] `network.getNetwork` (finds an existing network)

- [ ] `secgroup` module

  - [ ] `secgroup.SecGroup` (extends `pulumi.ComponentResource`)

    - [ ] `constructor`
    - [ ] `addNode(node)`

- [ ] `node` module

  - [ ] `node.Node` (extends `pulumi.ComponentResource`)

    - [ ] `constructor`

- [ ] `volume` module

  - [ ] `volume.Volume` (extends `pulumi.ComponentResource`)

    - [ ] `constructor`
    - [ ] `attach(node)`
    - [ ] `snapshot`
