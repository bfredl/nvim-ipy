import os, sys
import neovim
import IPython
from IPython.kernel import KernelManager, find_connection_file
class IPythonPlugin(object):
    def __init__(self, vim):
        self.vim = vim
        self.create_outbuf()
        self.vim.subscribe("ipy_runline")
        self.has_connection = False

    # TODO: subclass IPythonConsoleApp for flexibe launch/reconnetion to kernels
    # only support connect to exisitng for now
    def connect(self, path, profile=None):
        fullpath = find_connection_file(path)
        self.km = KernelManager(connection_file = fullpath)
        self.km.load_connection_file()
        self.kc = self.km.client()
        self.kc.start_channels()
        self.has_connection = True

    def create_outbuf(self):
        vim = self.vim
        for b in vim.buffers:
            if "[ipython]" in b.name:
                self.buf = b
                return
        vim.command(":new")
        buf = vim.current.buffer
        buf.options["buflisted"] = False
        buf.options["swapfile"] = False
        buf.options["buftype"] = "nofile"
        try:
            buf.name = "[ipython]"
        except:
            #FIXME: this is not unique either
            buf.name = "[ipy-{}]".format(os.getpid())
        self.buf = buf

    def append_outbuf(self, data):
        # FIXME: encoding
        print(repr(data))
        lastline = self.buf[-1]
        txt = lastline + data
        self.buf[-1:] = txt.split("\n") # not splitlines

    def get_selection(self, kind):
        vim = self.vim
        if kind == "visual":
            b = vim.current.buffer
            start = b.mark('<')
            end = b.mark('>')
            lines = b[start[0]-1:end[0]]
            txt = '\n'.join(lines) + '\n'
            return txt
        elif kind == "line":
            return vim.current.line + '\n'

    def on_ipy_runline(self, msg):
        line = self.get_selection('line')
        self.kc.shell_channel.execute(line)

    def do_nvim_ev(self,timeout=None):
        try:
            msg = self.vim.next_message(timeout)
        except NameError: #FIXME: upstream should emit TimeoutError
            return
        method = "on_" + msg.name
        if hasattr(self, method):
            getattr(self, method)(msg)
        else:
            print("warning: ignore", msg.name)
        return 0 #inputhook shall return 0

    def do_kernel_ev(self):
        while self.kc.iopub_channel.msg_ready():
            msg = self.kc.iopub_channel.get_msg()
            self.append_outbuf(repr(msg)+'\n')

        while self.kc.shell_channel.msg_ready():
            msg = self.kc.shell_channel.get_msg()
            self.append_outbuf("shell: " + repr(msg)+'\n')

    def do_ev(self):
        self.do_nvim_ev(0)
        if self.has_connection: self.do_kernel_ev()
        return 0

    def run(self):
        while True: #FIXME: select instead
            self.do_ev()
            sleep(0.005)

    # debug ipython client plugint using ipython console...
    def ipython_inputhook_register(self):
        from IPython.lib.inputhook import inputhook_manager
        inputhook_manager.set_inputhook(lambda: self.do_ev())
        
def test_ipython(path):
    vim = neovim.connect(path)
    p = IPythonPlugin(vim)
    p.ipython_inputhook_register()
    return vim, p

if __name__ == "__main__":
    vim = neovim.connect(sys.argv[1])
    IPythonPlugin(vim).run()

        
