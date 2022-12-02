# `scality/actions/infra` action entrypoints

These files are the entrypoints for compiling the distributed vanilla Javascript
which gets executed when invoking the custom actions under `scality/actions/infra`.

They should not contain logic outside of input retrieval and a few other interactions
with the action execution context. All logic should be stored outside this directory,
and properly tested (while these entrypoints will not be tested).
