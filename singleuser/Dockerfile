FROM quay.io/jupyter/minimal-notebook:python-3.12

USER root

COPY register-conda-kernel.py /usr/local/bin/register-conda-kernel
RUN chown root:root /usr/local/bin/register-conda-kernel \
    && chmod 755 /usr/local/bin/register-conda-kernel

# No sudo or additional system packages for now.
# Switch back to the standard non-root Jupyter Docker Stacks user.
USER ${NB_UID}

RUN mamba install -y \
    numpy \
    scipy \
    matplotlib \
    pandas \
    sympy \
    ipykernel \
    root \
    && mamba clean -afy

WORKDIR /home/jovyan/work
