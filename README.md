This is a IPython/Jupyter front-end for Neovim, partially based on [ivanov/vim-ipython](https://github.com/ivanov/vim-ipython), but refactored for nvim's plugin architechture and improved async event handling. It supports IPython 2.x and 3.x, including support for non-python kernels. (Using IPython 3.x is recommended, as it is the main platform for development, and 2.x will likely be dropped before this plugin is updated for Jupyter 4.x). It uses python2 per default; see below for notes on using python3.

It doesn't have all features of `vim-ipython`, but it has better support for long-running commands that continously produce output, for instance this silly example:

    from time import sleep
    for i in range(10):
        sleep(0.5)
        print(i)

Another difference is that `:IPython <args>` is interpreted just like the command line `ipython console <args>`, for instance:

Action                  | command
----------------------- | -------
Start new python kernel |  `:IPython` <br> `:IPython3` (for python3 kernel)
Connect to existing kernel | `:IPython --existing`
Start kernel in different language | `:IPython --profile julia` (IPython 2) <br> `:IPython --kernel julia` (IPython 3)

On IPython3 kernelspec can be used to launch a python3 kernel from nvim-ipy when running in the python2 host (default), the same way as from the Jupyter console and notebook. Use `:IPython --kernel python3` or the `:IPython3` shortcut. You might need to execute

    ipython3 kernelspec install-self --user

on beforehand for this to work.  I have tested that this plugin also supports IJulia and IHaskell, but ideally it should work with any Jupyter kernel.

This plugin runs in the python2 host by default, but it is also compatible with the python3 plugin host. There isn't yet any nice interface to configure this, but for now you can either move `rplugin/python/nvim_ipy.py` to `rplugin/python3/nvim_ipy.py` (and then reexecute `:UpdateRemotePlugins`) or alternatively,
edit `~/.nvim/.nvimrc-rplugin~` manually and change the first `'python'` to `'python3'` on the line

    call remote#host#RegisterPlugin('python', '.../nvim-ipy/rplugin/python/nvim_ipy.py', [

(_after_ executing `:UpdateRemotePlugins`) This will launch a python3 kernel per default.

See `plugin/ipy.vim` for keybindings (you might want to override these)
