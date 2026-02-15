FROM public.ecr.aws/lambda/python:3.13

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency definition
COPY pyproject.toml .

# Install dependencies
# --system: Install into the system python environment (Lambda's environment)
# --no-dev: Production build doesn't need dev dependencies
RUN uv pip install --system -r pyproject.toml

# Copy application code
COPY api/ ${LAMBDA_TASK_ROOT}/api/

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "api.handler.main" ]
