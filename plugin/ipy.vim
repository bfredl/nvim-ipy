function! IPyConnect(...)
    :call call('rpcnotify', [0, "ipy_connect"] + a:000)
endfunction

command! -nargs=* IPython :call IPyConnect(<f-args>)
command! -nargs=* IJulia :call IPyConnect("--profile", "julia")

function! IPyRun(code)
    call rpcnotify(0, "ipy_run", a:code)
endfunction

function! IPyRunSel(sel)
    "this is blocking so that selection could be deleted, for instance
    call rpcrequest(g:ipy_channel, "ipy_run_selection", a:sel)
endfunction


nnoremap <Plug>(IPy-RunLine) :call IPyRunSel('line')<cr>
vnoremap <Plug>(IPy-RunLine) :<c-u>call IPyRunSel('vline')<cr>
inoremap <Plug>(IPy-Complete) <c-o>:<c-u>call rpcnotify(0, "ipy_complete")<cr>
noremap <Plug>(IPy-Interrupt) :call rpcnotify(0, "ipy_interrupt")<cr>


function! IPyObjinfo()
    let isk_save = &isk
    let &isk = '@,48-57,_,192-255,.'
    let word = expand("<cword>")
    let &isk = isk_save
    call rpcnotify(0, "ipy_objinfo", word)
endfunction

if !exists('g:nvim_ipy_perform_mappings')
    let g:nvim_ipy_perform_mappings = 1
endif

let g:ipy_status = ""

if g:nvim_ipy_perform_mappings
    map <silent> <F5>           <Plug>(IPy-RunLine)
    imap <silent> <C-Space> <Plug>(IPy-Complete)
    map <silent> <F8> <Plug>(IPy-Interrupt)
    map <silent> <Leader>d :call IPyObjinfo()
    set titlestring=%t%(\ %M%)%(\ (%{expand(\"%:p:h\")})%)%(\ %a%)%(\ -\ %{g:ipy_status}%)
endif


