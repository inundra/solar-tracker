"""Earth Engine init: project from env var EE_PROJECT, clear errors otherwise."""
import os


def init() -> str:
    project = os.environ.get("EE_PROJECT")
    if not project:
        raise RuntimeError("EE_PROJECT is not set: run `setx EE_PROJECT <gcp-project-id>` and open a new terminal")
    import ee  # late import so offline code and tests don't need earthengine-api

    try:
        ee.Initialize(project=project)
    except Exception as e:
        raise RuntimeError(f"ee.Initialize failed for project {project!r}: run `earthengine authenticate` ({e})") from e
    return project
