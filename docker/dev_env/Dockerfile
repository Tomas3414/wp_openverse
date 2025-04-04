# syntax=docker/dockerfile:1

FROM docker.io/library/fedora:41

# We want to keep all important things in `/opt` as we will preserve the
# `/opt` directory as a volume.

# Set HOME to /opt so XDG-respecting utilities automatically use it
# without additional configuration
# This gets chmodded with wide open permissions, so that
# on Linux hosts, the explicitly passed user (with docker group)
# is able to read/write from here, as well as the root user used by
# macOS hosts (who don't have Docker permissions or host filesystem
# permissions issues to contend with and as such run the container as root)
ENV HOME="/opt"

# location where PDM installs Python interpreters
ENV PDM_PYTHONS="${HOME}/pdm/bin"
# location where `n` installs Node.js versions
ENV N_PREFIX="${HOME}/n"

ENV PIPX_GLOBAL_HOME=/pipx

ENV PNPM_BIN="${HOME}/pnpm"

# Add tooling installed in custom locations to `PATH`.
ENV PATH="${PNPM_BIN}:${N_PREFIX}/bin:${PDM_PYTHONS}:${HOME}/.local/bin:${PATH}"

# Dependency explanations:
# - git: required by some python package; contributors should use git on their host
# - g++: required by some pre-commit hooks for node-gyp
# - just: command runner
# - jq: JSON processor
# - which: locate a program file in `PATH`
# - tree: list files in a tree
# - xdg-utils: added because Storybook wants to open in a browser
# - nodejs, npm: language runtime (does not include Corepack)
# - python*: required by some Python libraries for compilation during installation
# - pipx: Python CLI app installer
# - libffi*: required for the Python package cffi
# - docker*: used to interact with host Docker socket
# - unzip: used to extract zip files of visual regression patches from CI artifacts
# - postgresql*: required to connect to PostgreSQL databases
#
# System-specific dependencies:
# - k6: used for load testing (only installed on x86 architectures)
#
# pipx dependencies:
# - httpie: CLI HTTP client
# - pdm, pipenv: Python package managers
# - pre-commit: Git pre-commit and pre-push hook manager
# - pgcli: PostgreSQL CLI
#
# Node dependencies:
# - n: Node.js distribution manager
# - corepack: Node.js package-manager-manager
RUN mkdir -p $HOME/.local/bin \
  && mkdir /pipx \
  && dnf5 -y install dnf-plugins-core \
  && dnf5 -y config-manager addrepo --from-repofile=https://download.docker.com/linux/fedora/docker-ce.repo \
  && dnf5 -y install \
    git \
    g++ \
    just \
    jq \
    which \
    tree \
    xdg-utils \
    nodejs npm \
    python3.12 python3.12-devel \
    pipx \
    libffi-devel \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin \
    unzip \
    postgresql postgresql-devel \
  && if [ "$(uname -m)" = "x86_64" ]; then \
    dnf5 -y install https://dl.k6.io/rpm/repo.rpm \
    && dnf5 -y install k6; \
  fi \
  && dnf5 clean all \
  && pipx install --global \
    httpie \
    pdm pipenv  \
    pgcli \
    pre-commit \
  && npm install -g \
    n \
    corepack@0.31.0 \
  && corepack enable

# Avoid overwriting `.venv`'s from the host
ENV PDM_VENV_IN_PROJECT="False"

# The fedora container's default entrypoint + command behaviour is to keep running
# so we do not need to modify entrypoint and command to use the container as a
# persistent environment.
