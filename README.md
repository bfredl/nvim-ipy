This is a IPython/Jupyter front-end for Neovim, partially based on [ivanov/vim-ipython](https://github.com/ivanov/vim-ipython), but refactored for nvim's plugin architechture and improved async event handling. It supports IPython 2.x and 3.x (including support for non-python kernels).

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

On IPython2.x, python3 is supported through a hack that assumes `python3` is in `$PATH`. On IPython3 kernelspec is used to launch a python3 kernel from nvim-ipy. I have tested that it's usable at least for IJulia and IHaskell, but ideally it should work with any Jupyter kernel.

See plugin/ipy.vim for keybindings (you might want to override these)
