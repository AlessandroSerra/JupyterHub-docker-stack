FROM quay.io/jupyter/minimal-notebook:python-3.12

USER root

COPY register-conda-kernel.py /usr/local/bin/register-conda-kernel
RUN chown root:root /usr/local/bin/register-conda-kernel \
    && chmod 755 /usr/local/bin/register-conda-kernel

# Per ora niente sudo e niente pacchetti extra di sistema.
# Torniamo all'utente non-root standard delle Jupyter Docker Stacks.
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
