# Benchmarks

This directory holds reproducible coverage and latency benchmarks for truesignal, measured
against comparable OSS solutions in this category.

v0.1 ships no benchmark numbers yet -- they are measured and published in a later pass of this
project's build pipeline, once there is real usage to measure against. No benchmark claim is
ever stated in the README or anywhere else in this repo without a command whose output
reproduces it.

To add a benchmark script, drop a runnable `.ts` file in this directory (e.g. `latency.ts`) that
prints its result to stdout, and document the exact command to reproduce it here.
