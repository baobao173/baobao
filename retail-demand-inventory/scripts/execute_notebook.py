"""执行阅读 notebook 并保存输出，使用当前 Python 的内核。"""

import os
from pathlib import Path
import sys

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from jupyter_client.kernelspec import KernelSpec

root = Path(__file__).resolve().parents[1]
os.environ["IPYTHONDIR"] = str(root / ".cache/ipython")
os.environ["JUPYTER_RUNTIME_DIR"] = str(root / ".cache/jupyter")
Path(os.environ["JUPYTER_RUNTIME_DIR"]).mkdir(parents=True, exist_ok=True)
path = root / "notebooks/01_exploration.ipynb"
nb = nbformat.read(path, as_version=4)
manager = KernelManager()
manager._kernel_spec = KernelSpec(
    argv=[sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"],
    display_name="Python 3",
    language="python",
)
client = NotebookClient(
    nb, km=manager, timeout=120, resources={"metadata": {"path": str(root)}}
)
try:
    client.execute()
    nbformat.write(nb, path)
finally:
    if manager.has_kernel:
        manager.shutdown_kernel(now=True)
print("Notebook executed and saved: all code cells passed.")
