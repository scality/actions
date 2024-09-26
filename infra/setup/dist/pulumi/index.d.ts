import { main as artescaProgram } from "./artesca";
import { main as ringProgram } from "./ring";
declare const programs: {
    artesca: typeof artescaProgram;
    ring: typeof ringProgram;
};
export type Product = keyof typeof programs;
export declare function init(product: Product, stackName: string, sourceDir?: string, workDir?: string): Promise<import("@pulumi/pulumi/automation").Stack>;
export {};
