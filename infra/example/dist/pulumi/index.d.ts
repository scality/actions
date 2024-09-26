import { LocalWorkspace } from "@pulumi/pulumi/automation";
export type Product = "artesca" | "ring";
export declare function init(product: Product, baseDir?: string, stack?: string): Promise<LocalWorkspace>;
