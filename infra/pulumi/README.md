# Pulumi Projects for Scality

Configuration from code for spawning cloud infrastructure intended for deploying various
flavours of Scality products.

## Goals

**Modularity**: Split infrastructure into logical composable units (e.g. "a network with
subnets and a bastion", "a node with disks", ...)

**Multi-cloud**: provide a single interface for "infrastructure" and handle the backend
selection at runtime

## Organization

Pulumi has the concept of [projects][pulumi-projects] and [stacks][pulumi-stacks].

[pulumi-projects]: https://www.pulumi.com/docs/intro/concepts/project/
[pulumi-stacks]: https://www.pulumi.com/docs/intro/concepts/stack/

A project defines a configurable Pulumi program, and stacks are instances of this
program with independent configurations.

Since they will likely require drastically different infrastructure layouts, we will
separate Scality products (RING and ARTESCA) into distinct projects.

However, Pulumi also exposes a concept of [components][pulumi-components] which can
be shared in a reusable library. We will use to provide basic building blocks and
standard implementations for known cloud providers.

The project is thus structured as follows:

```
infra/pulumi

