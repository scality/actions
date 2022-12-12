/**
 * Cloud providers configuration.
 *
 * @packageDocumentation
 */

import * as aws from "./aws"
import * as openstack from "./openstack"

const PROVIDERS = { aws, openstack }
export type CloudProvider = keyof typeof PROVIDERS;
export const DEFAULT_CLOUD: CloudProvider = "openstack";

export interface OpenstackProviderSettings {}

export interface AWSProviderSettings {}

export type CloudProviderSettings = OpenstackProviderSettings | AWSProviderSettings;

// --- Network ---

export 