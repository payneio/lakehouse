# Amplifier Daemon

FastAPI daemon serving the Amplifier API. Primarily intended to expose amplifier library functionality over HTTP for use by the [Amplifier app](../webapp/README.md) and other clients.

The daemon uses the [amplifier_library](../amplifier_library/README.md), a Python library for interacting with the Amplifier system. The library uses [Amplifier Core](https://github.com/microsoft/amplifier-core) under the hood to provide higher-level abstractions for building applications on top of Amplifier Core.
