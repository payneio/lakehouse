# Lakehouse

## Intelligent computation platform

Lakehouse is a [daemon](./amplifierd/README.md) and [webapp](./webapp/README.md) that provide an intelligent agent experience on top of your personal data.

Read more about the vision and design  in [The Intelligent Computation Platform](./amplifierd/docs/the-amplifier-computation-platform.md).

## Amplifier

This app uses [amplifier-core](https://github.com/microsoft/amplifier-core) under the hood, which is a Python library for building LLM-backed agents.

There are some resources for learning more about Amplifier here:

- [`guides`](./guides/README.md): Docs about Amplifier.v2 (created by Amplifier.v1).
- [`notebooks/amplifier-core`](./notebooks/amplifier-core/README.md): Notebooks demonstrating how to use amplifier-core.
- [`notebooks/amplifierd`](./notebooks/amplifierd/README.md): Notebooks demonstrating how to use the amplifierd server.

To get a better handle on amplifier@v2, feel free to explore the guides and notebooks, or run the daemon and webapp locally to poke around.

## Quick start

```bash
# Clone the repo.
mkdir <somewhere>
cd <somewhere>
git clone https://github.com/payneio/lakehouse.git

# Initial setup.
# Prerequisites: Python 3.10+, Node.js 16+, pnpm, make, uv.
make install

# Run the daemon.
make daemon-dev

# Run the webapp dev server in a separate terminal.
make webapp-dev
```

Now visit http://localhost:5174 in your browser.

A directory named `.amplifierd` will be created wherever you run the daemon from. You can see some config in `amplifierd/.amplifierd/config/daemon.yaml`. The important one is `data_dir` which is the path to the "data root" of amplifier. Amplifier will have all access there. By default, it's set to your home directory (~) but you might want to change it to somewhere else where you aren't worried about your data getting messed up (this is an experiment).

Restart the daemon after changing config.
