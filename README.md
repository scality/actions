# actions

Set of GitHub Actions actions used a cross the Scality organization.

## action-crons
Call different workflows running on defined hour with specific arguments.

## actions-docker-upload
Bunch of step to upload an image speed up with `actions@cache`.

## setup-rdma-runner
Set up SoftRoCE on a RHEL-family runner: install the RDMA userspace tools,
load `rdma_rxe`, attach a link to a netdev and check it with an RC ping-pong,
enable io_uring (biziod refuses to start without it), and output the address
to bind RDMA endpoints to.

## start-miniring
Spawn a miniring cluster in the background as the caller, with the memlock
limit RDMA needs lifted, wait until it reports readiness, and record its pid.
Stopping it is left to the caller. RDMA GETs read the biziod data device, so
the caller must be able to read it, as the scality user must in production;
pass `--disk-paths` to a directory on such a device.
