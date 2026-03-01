import tomli
import tomli_w

with open('pyproject.toml', 'rb') as f:
    config = tomli.load(f)

new_config = {"project": {}}

poetry_tool = config.get("tool", {}).get("poetry", {})

new_config["project"]["name"] = poetry_tool.get("name")
new_config["project"]["version"] = poetry_tool.get("version")
new_config["project"]["description"] = poetry_tool.get("description", "")
if "readme" in poetry_tool:
    new_config["project"]["readme"] = poetry_tool["readme"]

authors = []
for author in poetry_tool.get("authors", []):
    parts = author.split("<")
    if len(parts) == 2:
        name = parts[0].strip()
        email = parts[1].strip(">").strip()
        authors.append({"name": name, "email": email})
    else:
        authors.append({"name": author})
if authors:
    new_config["project"]["authors"] = authors

dependencies = []
python_req = ">=3.8"
for dep, ver in poetry_tool.get("dependencies", {}).items():
    if dep == "python":
        if ver.startswith("^"):
            python_req = f">={ver[1:]}"
        else:
            python_req = ver
    else:
        if isinstance(ver, dict):
            pass
        elif ver == "*":
            dependencies.append(dep)
        else:
            if ver.startswith("^"):
                dependencies.append(f"{dep}>={ver[1:]}")
            else:
                dependencies.append(f"{dep}{ver}")

new_config["project"]["requires-python"] = python_req
new_config["project"]["dependencies"] = dependencies

new_config["build-system"] = {
    "requires": ["hatchling"],
    "build-backend": "hatchling.build"
}

if "tool" in config:
    if "poetry" in config["tool"]:
        del config["tool"]["poetry"]
    if config["tool"]:
        new_config["tool"] = config["tool"]

dev_deps = []
for dep, ver in poetry_tool.get("dev-dependencies", {}).items():
    if ver == "*":
        dev_deps.append(dep)
    else:
        if ver.startswith("^"):
            dev_deps.append(f"{dep}>={ver[1:]}")
        else:
            dev_deps.append(f"{dep}{ver}")

example_deps = []
for dep, ver in poetry_tool.get("group", {}).get("examples", {}).get("dependencies", {}).items():
    if ver == "*":
        example_deps.append(dep)

if "dependency-groups" not in new_config:
    new_config["dependency-groups"] = {}
new_config["dependency-groups"]["dev"] = dev_deps
new_config["dependency-groups"]["examples"] = example_deps


with open('pyproject.toml', 'wb') as f:
    tomli_w.dump(new_config, f)
