from __future__ import print_function, division
from functools import partial, wraps
from IPython.kernel import KernelClient, KernelManager
from IPython.kernel.async import AsyncKernelClient

from IPython.core.application import BaseIPythonApplication
from IPython.consoleapp import IPythonConsoleApp

# haskell too much:
printer = partial(partial, print)

class IPythonVimApp(BaseIPythonApplication, IPythonConsoleApp):
    # don't use blocking client; we override call_handlers below
    kernel_client_class = AsyncKernelClient
    def init_kernel_client(self):
        self.kernel_client = self.kernel_manager.client()
        # NOT SURE if "monkey patching" or just "configuration"
        self.kernel_client.shell_channel.call_handlers = printer("shell:")
        self.kernel_client.iopub_channel.call_handlers = printer("iopub:")
        self.kernel_client.stdin_channel.call_handlers = printer("stdin:")
        self.kernel_client.hb_channel.call_handlers = printer("HB:")
        self.kernel_client.start_channels()

    def initialize(self, argv):
        super(IPythonVimApp, self).initialize(argv)
        IPythonConsoleApp.initialize(self, argv)

if __name__ == '__main__':
    a = IPythonVimApp()
    a.initialize([])
    kc = a.kernel_client
