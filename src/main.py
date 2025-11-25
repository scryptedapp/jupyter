from __future__ import annotations
import os
from typing import Any
import scrypted_sdk
import asyncio
import json
from jupyter_client import KernelManager
from typing import TypedDict
import sys

class Kernel(TypedDict):
    manager: KernelManager
    client: BlockingKernelClient

from scrypted_sdk.types import DeviceProvider, OnOff, ScryptedDeviceType, ScryptedInterface, Scriptable
from typing import TypedDict
from jupyter_client import BlockingKernelClient

class JupyterPlugin(scrypted_sdk.ScryptedDeviceBase, DeviceProvider, Scriptable):
    def __init__(self):
        super().__init__()
        self.kernels: dict[str, Kernel] = {}
        
    async def eval(self, source, variables = None):
        script: str = source.get("script", "")
        kernel_name = source.get("filename")
        kernel = self.kernels.get(kernel_name)
        if not kernel:
            manager = KernelManager(kernel_name='python3')
            python_path = os.pathsep.join(sys.path.copy())
            env = os.environ.copy()
            env['PYTHONPATH'] = python_path
            manager.start_kernel(env=env)
            client = manager.client()
            client.start_channels()
            kernel = {
                "manager": manager,
                "client": client,
            }
            self.kernels[kernel_name] = kernel
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._execute_code, kernel["client"], script)
        return result

    def _execute_code(self, client: BlockingKernelClient, code: str):
        msg_id = client.execute(code)
        msg = client.get_shell_msg()
        
        status = msg['content'].get('status')
        if status == 'error':
            return "\n".join(msg['content'].get('traceback', []))
        # Capture outputs
        std = ""

        while True:
            try:
                msg = client.get_iopub_msg(timeout=1)
                if msg['parent_header'].get('msg_id') == msg_id:
                    msg_type = msg['header']['msg_type']
                    content = msg['content']

                    if msg_type == 'status' and content['execution_state'] == 'idle':
                        break
                    elif msg_type == 'stream':
                        stream_name = content['name']
                        text = content['text']
                        if stream_name == 'stdout':
                            std += text
                        elif stream_name == 'stderr':
                            std += text
            except Exception as e:
                print("Timeout or error receiving messages:", e)
                break

        return std

    def loadScripts(self):
        try:
            script = json.loads(self.storage.getItem("script"))
            script_str = script.get("script")
        except:
            script_str = ""
        return {
            "main.py": {
                "name": "Script",
                "language": "python",
                "script": script_str,
            }
        }

    def saveScript(self, script):
        return self.storage.setItem("script", json.dumps(script))

def create_scrypted_plugin():
    return JupyterPlugin()
