# nvim-ipy
This is a IPython/Jupyter front-end for Neovim, partially based on [ivanov/vim-ipython](https://github.com/ivanov/vim-ipython), but refactored for nvim's plugin architechture and improved async event handling. IPython 3.x or Jupyter 4.x is required. It uses python2 per default; see below for notes on using python3. It has full support for non-python kernels.

It doesn't have all features of `vim-ipython`, but it has better support for long-running commands that continously produce output, for instance this silly example:

    from time import sleep
    for i in range(10):
        sleep(0.5)
        print(i)

## Connecting/starting kernel
`:IPython <args>` is interpreted just like the command line `ipython console <args>`, for instance:

Action                  | command
----------------------- | -------
Start new python kernel |  `:IPython` <br> `:IPython3` (for python3 kernel)
Connect to existing kernel | `:IPython --existing`
Start kernel in different language | `:IPython --kernel julia-0.4`

Kernelspec can be used to launch a python3 kernel from nvim-ipy when running in the python2 host (default), the same way as from the Jupyter console and notebook. Use `:IPython --kernel python3` or the `:IPython3` shortcut. You might need to execute

    ipython3 kernelspec install-self --user

on beforehand for this to work.  I have tested that this plugin also supports IJulia and IHaskell, but ideally it should work with any Jupyter kernel.

This plugin runs in the python2 host by default, but it is also compatible with the python3 plugin host. There isn't yet any nice interface to configure this, but for now you can move `rplugin/python/nvim_ipy.py` to `rplugin/python3/nvim_ipy.py`, and then reexecute `:UpdateRemotePlugins`.  This will launch a python3 kernel per default.

## Keybindings

When kernel is running, following bindings can be used:

Generic                   | default     | Action
------------------------- | ----------  | ------
`<Plug>(IPy-Run)`         | `<F5>`      | Excecute current line or visual selection
`<Plug>(IPy-Complete)`    | `<C-F>`     | (insert mode) Kernel code completion
`<Plug>(IPy-WordObjInfo)` | `<leader>?` | Inspect variable under the cursor
`<Plug>(IPy-Interrupt)`   | `<F8>`      | Send interrupt to kernel
`<Plug>(IPy-Terminate)`   |             | Terminate kernel

### But... The default bindings suck!
Yes, they exist mainly to quickly test this plugin. Add

    let g:nvim_ipy_perform_mappings = 0

To your nvimrc and map to the generic bindings. For instance:

    map <silent> <c-s>   <Plug>(IPy-Run)

## Options
NB: the option system will soon be rewritten to allow changing options while the plugin is running,
but for now you can set:

Option                    | default     | Action
------------------------- | ----------  | ------
`g:ipy_set_ft`            | 0 (false)   | set filetype of output buffer to kernel language
`g:ipy_highlight`         | 1 (true)    | add highlights for ANSI sequences in the output
`g:ipy_truncate_input`    | 0           | when > 0, don't echo inputs larger than this number of lines
`g:ipy_shortprompt`       | 0 (false)   | use shorter prompts (TODO: let user set arbitrary format)

Note that the filetype syntax highlight could interact badly with the highlights sent from the kernel as ANSI sequences (in ipython tracebacks, for instance). Therefore both are not enabled by default. I might look into a better solution for this.

## Exported vimscript functions
Most useful is `IPyRun("string of code"[, silent])` which can be called to programmatically execute any code. The optional `silent` will avoid printing code and result to the console if nonzero. This is useful to bind common commands to a key. This will close all figures in matplotlib:

    nnoremap <Leader>c :call IPyRun('close("all")',1)<cr>

`IPyConnect(args...)` can likewise be used to connect with vimscript generated arguments.

`IPyOmniFunc` can be used as `&completefunc`/`&omnifunc` for use with a completer framework. Note that unlike `<Plug><IPy-Complete)` this is synchronous and waits for the kernel, so if the kernel hangs this might hang nvim! For use with async completion like Deoplete it would be better to create a dedicated source.
