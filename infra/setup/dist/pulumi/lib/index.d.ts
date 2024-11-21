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
declare const CLOUD_PROVIDERS: {
    openstack: undefined;
};
export type CloudProvider = keyof typeof CLOUD_PROVIDERS;
export {};
