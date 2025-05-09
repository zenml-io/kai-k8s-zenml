from zenml import step, pipeline
from zenml.config import DockerSettings

docker_settings = DockerSettings(
    python_package_installer="uv",
)


@step
def my_step():
    print("Hello, world!")


@pipeline(settings={"docker": docker_settings})
def my_pipeline():
    my_step()


if __name__ == "__main__":
    my_pipeline()
