/**
 * Entrypoint for installing and configuring dependencies for cloud infrastructure
 * provisioning.
 *
 * Installs Pulumi, configures it to use a local state backend, and sets up the
 * selected cloud provider, with authentication and optional tooling.
 *
 * Inputs:
 *   - cloud (string)      The cloud provider to use
 *   - cloud-auth (string) A JSON containing authentication details for the chosen
 *                         cloud provider
 *   - state-path (string) The path to the local Pulumi state to use or create
 *
 * @packageDocumentation
 */
export declare function main(): Promise<void>;
