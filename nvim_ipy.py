import os
import neovim
class IPythonPlugin(object):
    def __init__(self, vim):
        self.vim = vim

    def create_outbuf(self):
        vim = self.vim
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
        lastline = self.buf[-1]
        txt = lastline + data
        self.buf[-1:] = txt.splitlines()
