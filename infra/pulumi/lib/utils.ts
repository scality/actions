/**
 * Utility functions shared across the components.
 *
 * @packageDocumentation
 */

import * as crypto from "crypto";

/**
 * Generate a basic random string from the hex encoding of random bytes.
 *
 * @param len Length of the random string to generate
 */
export function generateRandomString(len: number): string {
  return crypto.randomBytes(len * 2).toString("hex");
}
